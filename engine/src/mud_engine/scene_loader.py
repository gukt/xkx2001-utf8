"""场景数据 YAML 加载器：把一份 YAML 文件读成 ``(world, player_id)``。

本模块实现**现行创作契约 v0**（对外承诺见仓库根 ``docs/creator-contract-v0.md``）：
冻结的顶层段与实体字段集合、只做加法的兼容承诺，以及已知集合之外的透传语义。
覆盖范围：房间 / 物品 / NPC / 玩家初值 / 技能与门派注册表 / 死亡策略，以及门与
锁等能力字段。

加载逻辑与命令调度（commands）/ ECS 存储（world）保持分离：本模块只依赖
components + world + PyYAML，不 import commands，也不把加载逻辑写进 ``world.py``
或 ``commands.py``。YAML 里引用了不存在的房间键、缺必需字段等结构性错误，抛
``SceneLoadError``（消息带文件路径与出错的数据键），而不是让裸 Python 异常堆栈
糊到启动者脸上——这是"加载期数据校验"，与存档崩溃恢复的运行时语义是两件不同的事，
不要混着实现。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from mud_engine.ai import SpawnerBlueprint, spawn_from_blueprint
from mud_engine.capabilities import (
    CAPABILITIES,
    NPC_CAPABILITIES,
    ROOM_CAPABILITIES,
    CapabilitySpec,
)
from mud_engine.components import (
    AIController,
    Behaviors,
    Container,
    Description,
    Door,
    Doors,
    DoorState,
    Exit,
    Exits,
    Faction,
    Ferry,
    Identity,
    Inquiry,
    Mount,
    PlayerSession,
    Position,
    ShopInventory,
)
from mud_engine.death_flow import parse_death_policy, parse_loot_table
from mud_engine.errors import SceneLoadError
from mud_engine.factions import FACTIONS, load_factions_from_mapping, replace_factions_registry
from mud_engine.runtime import wire_runtime
from mud_engine.skills import load_skills_from_mapping, replace_skills_registry
from mud_engine.world import EntityId, World

# ``SceneLoadError`` 规范在 ``mud_engine.errors``；本模块再导出以保持
# ``from mud_engine.scene_loader import SceneLoadError`` 向后兼容。


def load_scene(scene_path: Path) -> tuple[World, EntityId]:
    """从一份 YAML 场景文件构造 ``(world, player_id)``。

    任何结构性错误（YAML 语法、缺字段、引用不存在的房间键）都收口成
    ``SceneLoadError``，消息含文件路径与大致出错的条目键。先建全部房间，再按
    房间 ``objects`` 摆物品、连出口/门、放 NPC、放玩家--物品先于出口是因为出口
    的门锁可引用物品作为钥匙（04 号票），建出口时需要物品的 entity id 已就绪。
    放置权威是房间 ``objects``（ADR-0010）；``placed_in`` / ``in_room`` 一律拒绝。
    """
    data = _read_yaml(scene_path)
    rooms = _expect_mapping(data, scene_path, "rooms")
    items = _expect_mapping(data, scene_path, "items", default={})
    npcs = _expect_mapping(data, scene_path, "npcs", default={})
    player = _expect_mapping(data, scene_path, "player")

    world = World()
    world.scene_path = scene_path.resolve()
    # skills:/factions: 是全局注册表（非实体）；每次加载清空重建，避免两次加载互相污染。
    replace_skills_registry(load_skills_from_mapping(data.get("skills"), scene_path))
    replace_factions_registry(load_factions_from_mapping(data.get("factions"), scene_path))
    room_ids = _build_rooms(world, rooms, scene_path)
    world.room_ids = dict(room_ids)
    world.death_policy = parse_death_policy(data.get("death_policy"))
    _resolve_ferry_refs(world, room_ids, scene_path)
    _reject_legacy_placement_fields(items, npcs, scene_path)
    placements = _collect_room_objects(rooms, items, npcs, scene_path)
    item_ids = _build_items(world, items, placements, room_ids, scene_path)
    _build_exits(world, rooms, room_ids, item_ids, scene_path)
    _build_npcs(world, npcs, placements, room_ids, scene_path)
    _validate_shop_inventories(world, scene_path)
    _validate_faction_refs(world, scene_path)
    player_id = _build_player(world, player, room_ids, scene_path)
    _capture_top_level_unknown_sections(world, data)
    # 运行时子系统（nature/AI/渡口/交战/门禁/昏迷苏醒）统一接线；与 restore 共用。
    wire_runtime(world, scene_path)
    return world, player_id


def read_nature_config(scene_path: Path | str) -> dict | None:
    """从场景 YAML 读取顶层 ``nature:`` 段（场景 I/O 属本模块，不放 nature 运行时）。

    Nature 运行时态不进存档；崩溃恢复后 ``extension_data`` 为空，须从
    ``world.scene_path`` 指向的场景文件再读配置。文件缺失 / 无段 / 非 mapping
    时返回 ``None``（调用方回退默认四相）。
    """
    path = Path(scene_path)
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("nature")
    return raw if isinstance(raw, dict) else None


# 引擎认识的顶层段与每类实体的字段：不在这些集合里的段/字段是"未识别"的，
# 原样透传到扩展数据容器留着不丢，M1 不解析不执行（11 号票）。透传不是设计、
# 只是不丢弃，故不违反"M1 不预支 M3 设计"--M3 引入规则引擎时旧场景数据不必重写。
# nature 顶层段继续走透传（不列入已知段），由 attach_nature 消费 extension_data。
#
# M2-01：房间/NPC 能力字段从 ROOM_CAPABILITIES / NPC_CAPABILITIES 聚合（同物品
# CAPABILITIES）。以下两项**刻意不**扫平进能力注册表：
# - ``_PLAYER_KNOWN_FIELDS``：player 段字段少，后续 Currency/Faction 初值直接加
#   进本集合即可，不为个别字段建注册表。
# - ``_TOP_LEVEL_KNOWN_SECTIONS``：``skills:`` / ``factions:`` 是全局注册表模式，
#   不是实体能力（M2-03 / M2-08）。
_TOP_LEVEL_KNOWN_SECTIONS = frozenset(
    {"rooms", "items", "npcs", "player", "skills", "factions", "death_policy"}
)
_ROOM_INTRINSIC_FIELDS = frozenset({"name", "aliases", "short", "long", "exits", "objects"})
_ROOM_KNOWN_FIELDS = frozenset(
    _ROOM_INTRINSIC_FIELDS | {field for spec in ROOM_CAPABILITIES for field in spec.known_fields}
)
# 物品能力字段（18/21/22/24 号票 + 31 号票注册表）：从 ``CAPABILITIES``
# 聚合每个能力的 known_fields，避免新增能力时漏改 _ITEM_KNOWN_FIELDS 导致透传误吞字段。
# 放置由房间 ``objects`` 声明（ADR-0010），模板段不再含 ``placed_in``。
_ITEM_KNOWN_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
    }
    | {field for spec in CAPABILITIES for field in spec.known_fields}
)
# NPC 数量由房间 ``objects`` 推导；``in_room``/``count`` 已退役（ADR-0010）。
# ``startroom`` 仅作补刷出生房（缺省=objects 房间）；``respawn`` 仍在模板段。
_NPC_INTRINSIC_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "startroom",
        "respawn",
        "loot",
    }
)
_NPC_KNOWN_FIELDS = frozenset(
    _NPC_INTRINSIC_FIELDS | {field for spec in NPC_CAPABILITIES for field in spec.known_fields}
)
# 玩家段：能力字段与 NPC 注册表对齐（vitals/attributes/skills/currency/faction），
# 不为玩家单独建注册表（M2-01 docstring）。
_PLAYER_KNOWN_FIELDS = frozenset(
    {"name", "start_room"} | {field for spec in NPC_CAPABILITIES for field in spec.known_fields}
)


def _capture_top_level_unknown_sections(world: World, data: Mapping) -> None:
    """顶层未识别段（rules/world_rules/nature 等）原样透传到 ``world.extension_data``。

    M1 引擎只认识 rooms/items/npcs/player 四个顶层段，其余顶层段（未来规则引擎、
    Nature、世界级触发器等）一概不识别。透传留底而非报错，供 M3 消费。透传数据是
    声明式静态数据、非运行时可变态，挂在 ``World.extension_data`` 上天然不进存档
    （save.py 只序列化 entities/components）。
    """
    for key, value in data.items():
        if key not in _TOP_LEVEL_KNOWN_SECTIONS:
            world.extension_data[key] = value


def _capture_entity_unknown_fields(
    world: World, entity: EntityId, data: Mapping, known: frozenset[str]
) -> None:
    """实体级未识别字段（物品 on_use/effect、NPC dialogue/behaviors 等）透传到
    该实体的扩展数据容器。与顶层透传同语义（11 号票）：只在有未识别字段时才填。"""
    extras = {k: v for k, v in data.items() if k not in known}
    if extras:
        world.entity_extension_data(entity).update(extras)


def _read_yaml(scene_path: Path) -> dict:
    """读 YAML 文件，语法错误与读盘错误收口成 SceneLoadError。"""
    try:
        with scene_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise SceneLoadError(f"无法解析 YAML 文件 {scene_path}：{exc}") from exc
    except OSError as exc:
        raise SceneLoadError(f"无法读取场景文件 {scene_path}：{exc}") from exc
    if not isinstance(data, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 顶层应是映射（rooms/items/...），实际是 {type(data).__name__}"
        )
    return dict(data)


def _expect_mapping(
    data: Mapping, scene_path: Path, key: str, *, default: dict | None = None
) -> dict:
    """取顶层某个段；缺失时返回 default（None 表示必需，缺失报错）。"""
    if key not in data:
        if default is not None:
            return default
        raise SceneLoadError(f"场景文件 {scene_path} 缺少必需的顶层段 '{key}'")
    section = data[key]
    if not isinstance(section, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 '{key}' 段应是映射，实际是 {type(section).__name__}"
        )
    return dict(section)


def _as_mapping(data: object, *, label: str, scene_path: Path) -> dict:
    """断言某条目是映射并返回 dict；不是则抛定位明确的 SceneLoadError。"""
    if not isinstance(data, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}应是映射，实际是 {type(data).__name__}"
        )
    return dict(data)


def _build_rooms(world: World, rooms: Mapping, scene_path: Path) -> dict[str, EntityId]:
    """建全部房间实体（Identity+Description+Exits+Container），返回 key->entity id。"""
    room_ids: dict[str, EntityId] = {}
    for room_key, raw in rooms.items():
        data = _as_mapping(raw, label=f"房间 '{room_key}'", scene_path=scene_path)
        room = world.create_entity()
        label = f"房间 '{room_key}'"
        _attach_identity_and_description(
            world,
            room,
            data,
            label=label,
            scene_path=scene_path,
            outdoors=bool(data.get("outdoors", False)),
        )
        world.add_component(room, Exits())
        world.add_component(room, Container())
        _attach_capability_specs(
            world, room, data, ROOM_CAPABILITIES, label=label, scene_path=scene_path
        )
        _capture_entity_unknown_fields(world, room, data, _ROOM_KNOWN_FIELDS)
        room_ids[room_key] = room
    return room_ids


def _build_exits(
    world: World,
    rooms: Mapping,
    room_ids: dict[str, EntityId],
    item_ids: dict[str, EntityId],
    scene_path: Path,
) -> None:
    """把每个房间的 exits 段连成 Exit 组件条目，校验目标房间键都已定义。

    出口可选挂门状态（``door``/``key`` 字段）：带门的出口同时往该房间的 ``Doors``
    组件里记一条 ``Door``（04 号票）。``Doors`` 组件按需创建--只有至少一个出口
    带门时才挂到房间上，纯通行出口的房间不挂空 ``Doors``。
    """
    for room_key, raw in rooms.items():
        data = _as_mapping(raw, label=f"房间 '{room_key}'", scene_path=scene_path)
        exits_data = data.get("exits")
        if exits_data is None:
            continue
        if not isinstance(exits_data, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 'exits' 应是映射，"
                f"实际是 {type(exits_data).__name__}"
            )
        room = room_ids[room_key]
        exits = world.require_component(room, Exits)
        doors: Doors | None = None
        for direction, exit_data in exits_data.items():
            target_key = _exit_target(exit_data, room_key, direction, scene_path)
            if target_key not in room_ids:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 "
                    f"'{direction}' 指向未定义的房间 '{target_key}'"
                )
            aliases = _exit_aliases(exit_data, room_key, direction, scene_path)
            exits.by_direction[str(direction)] = Exit(target=room_ids[target_key], aliases=aliases)
            door = _exit_door(exit_data, room_key, direction, item_ids, scene_path)
            if door is not None:
                if doors is None:
                    doors = Doors()
                    world.add_component(room, doors)
                doors.by_direction[str(direction)] = door


def _exit_target(exit_data: object, room_key: str, direction: object, scene_path: Path) -> str:
    """取出口目标房间键：``{ to: <key> }`` 映射或裸字符串键都接受。"""
    if isinstance(exit_data, Mapping):
        target = exit_data.get("to")
        if not target:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' 缺少 'to'"
            )
        return str(target)
    if isinstance(exit_data, str):
        return exit_data
    raise SceneLoadError(
        f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' "
        f"应是映射或目标房间键字符串，实际是 {type(exit_data).__name__}"
    )


def _exit_aliases(
    exit_data: object, room_key: str, direction: object, scene_path: Path
) -> tuple[str, ...]:
    """取出口的方向别名；非映射形态（裸字符串键）的出口没有别名位。"""
    if not isinstance(exit_data, Mapping):
        return ()
    aliases = exit_data.get("aliases") or ()
    if not isinstance(aliases, (list, tuple)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' "
            f"的 'aliases' 应是列表，实际是 {type(aliases).__name__}"
        )
    return tuple(str(a) for a in aliases)


def _exit_door(
    exit_data: object,
    room_key: str,
    direction: object,
    item_ids: dict[str, EntityId],
    scene_path: Path,
) -> Door | None:
    """取出口可选的门状态：``door`` 字段缺失返回 None（该出口无门）。"""
    if not isinstance(exit_data, Mapping):
        return None
    raw_state = exit_data.get("door")
    if raw_state is None:
        return None
    state = _door_state(raw_state, room_key, direction, scene_path)
    key_item_id = _door_key_item_id(exit_data.get("key"), room_key, direction, item_ids, scene_path)
    return Door(state=state, key_item_id=key_item_id)


def _door_state(raw_state: object, room_key: str, direction: object, scene_path: Path) -> DoorState:
    """把 ``door`` 字段值映射成 DoorState；非法值抛定位明确的 SceneLoadError。"""
    try:
        return DoorState(str(raw_state).lower())
    except ValueError:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' "
            f"的 'door' 应是 open/closed/locked，实际是 {raw_state!r}"
        ) from None


def _door_key_item_id(
    raw_key: object,
    room_key: str,
    direction: object,
    item_ids: dict[str, EntityId],
    scene_path: Path,
) -> EntityId | None:
    """把门锁的 ``key`` 物品引用解析成 entity id；引用未定义物品时报错。"""
    if raw_key is None:
        return None
    key = str(raw_key)
    if key not in item_ids:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' "
            f"的 'key' 引用未定义的物品 '{key}'"
        )
    return item_ids[key]


def _reject_legacy_placement_fields(
    items: Mapping, npcs: Mapping, scene_path: Path
) -> None:
    """拒绝已退役的权威放置字段（ADR-0010）：``placed_in`` / ``in_room`` / 模板 ``count``。"""
    for item_key, raw in items.items():
        data = _as_mapping(raw, label=f"物品 '{item_key}'", scene_path=scene_path)
        if "placed_in" in data:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的物品 '{item_key}' 使用了已退役字段 "
                f"'placed_in'；请改为在目标房间的 objects 中声明 "
                f"（见 docs/adr/0010-room-centric-objects-placement.md）"
            )
    for npc_key, raw in npcs.items():
        data = _as_mapping(raw, label=f"NPC '{npc_key}'", scene_path=scene_path)
        if "in_room" in data:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 使用了已退役字段 "
                f"'in_room'；请改为在目标房间的 objects 中声明 "
                f"（见 docs/adr/0010-room-centric-objects-placement.md）"
            )
        if "count" in data:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 使用了已退役字段 "
                f"'count'；数量请写在房间 objects 里 "
                f"（见 docs/adr/0010-room-centric-objects-placement.md）"
            )


def _collect_room_objects(
    rooms: Mapping,
    items: Mapping,
    npcs: Mapping,
    scene_path: Path,
) -> dict[str, list[tuple[str, int]]]:
    """收集房间 ``objects``：返回 template_key -> [(room_key, count), ...]。

    物品模板可出现在多个房间；NPC 模板受单蓝图约束，只能出现在一个房间。
    """
    placements: dict[str, list[tuple[str, int]]] = {}
    item_keys = {str(k) for k in items}
    npc_keys = {str(k) for k in npcs}
    for room_key, raw in rooms.items():
        data = _as_mapping(raw, label=f"房间 '{room_key}'", scene_path=scene_path)
        objects = data.get("objects")
        if objects is None:
            continue
        if not isinstance(objects, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 'objects' 应是映射，"
                f"实际是 {type(objects).__name__}"
            )
        for template_key, raw_count in objects.items():
            key = str(template_key)
            if key not in item_keys and key not in npc_keys:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的房间 '{room_key}' 的 objects "
                    f"引用未定义的模板 '{key}'"
                )
            count = _parse_positive_int(raw_count, "objects", key, scene_path)
            if key in npc_keys and key in placements:
                prev_room, _ = placements[key][0]
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的 NPC '{key}' 在房间 '{prev_room}' 与 "
                    f"'{room_key}' 的 objects 中重复出现；每个 NPC 模板只能放在一个房间"
                )
            placements.setdefault(key, []).append((str(room_key), count))
    return placements


def _build_items(
    world: World,
    items: Mapping,
    placements: Mapping[str, list[tuple[str, int]]],
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> dict[str, EntityId]:
    """登记物品模板，并按房间 ``objects`` 在地面生成实例。

    返回 item key -> 首个实例 entity id，供出口的 ``door.key`` 引用（04 号票）。
    仅出现在 ``items``、未写入任何 ``objects`` 的键仍可作为商店模板（不生成实体）。
    """
    item_ids: dict[str, EntityId] = {}
    for item_key, raw in items.items():
        data = _as_mapping(raw, label=f"物品 '{item_key}'", scene_path=scene_path)
        key = str(item_key)
        # 商店 buy 按模板键实例化：保留原始 YAML（M2-07）。
        world.item_templates[key] = dict(data)
        room_placements = placements.get(key)
        if not room_placements:
            continue
        first_item: EntityId | None = None
        for room_key, count in room_placements:
            room_container = world.require_component(room_ids[room_key], Container)
            for _ in range(count):
                item = world.create_entity()
                _attach_identity_and_description(
                    world, item, data, label=f"物品 '{item_key}'", scene_path=scene_path
                )
                _attach_item_capabilities(
                    world, item, data, label=f"物品 '{item_key}'", scene_path=scene_path
                )
                room_container.items.add(item)
                _capture_entity_unknown_fields(world, item, data, _ITEM_KNOWN_FIELDS)
                if first_item is None:
                    first_item = item
        assert first_item is not None
        item_ids[key] = first_item
    return item_ids


def _attach_item_capabilities(
    world: World,
    item: EntityId,
    data: Mapping,
    *,
    label: str,
    scene_path: Path,
) -> None:
    """按 YAML 声明挂载物品能力组件（31 号票改走统一注册表 CAPABILITIES）。"""
    _attach_capability_specs(world, item, data, CAPABILITIES, label=label, scene_path=scene_path)


def _attach_capability_specs(
    world: World,
    entity: EntityId,
    data: Mapping,
    specs: list[CapabilitySpec],
    *,
    label: str,
    scene_path: Path,
) -> None:
    """遍历能力注册表，调用每条 spec 的 from_yaml；返回非 None 则挂载。

    ``attached`` 记录已挂载组件，供互斥/依赖判定（如 Weight↔Stackable、
    AIController 依赖 Behaviors）。注册表顺序重要。
    """
    attached: dict[type, object] = {}
    for spec in specs:
        component = spec.from_yaml(data, label, scene_path, attached)
        if component is not None:
            world.add_component(entity, component)
            attached[type(component)] = component


def _build_npcs(
    world: World,
    npcs: Mapping,
    placements: Mapping[str, list[tuple[str, int]]],
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> None:
    """建 NPC：解析一次能力 → 注册 SpawnerBlueprint → 经 spawn_from_blueprint 实例化。

    初始位置与期望数量来自房间 ``objects``；模板 ``respawn`` 控制补刷；``startroom``
    若声明则须与 objects 房间一致（补刷落点），缺省即 objects 房间。同一 template
    的多个实例只注册一条蓝图（M2-04）。加载与重生共用 ``spawn_from_blueprint``。
    """
    for npc_key, raw in npcs.items():
        data = _as_mapping(raw, label=f"NPC '{npc_key}'", scene_path=scene_path)
        key = str(npc_key)
        room_placements = placements.get(key)
        if not room_placements:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 未出现在任何房间的 "
                f"objects 中（见 docs/adr/0010-room-centric-objects-placement.md）"
            )
        room_key, count = room_placements[0]
        start_key = data.get("startroom") or room_key
        if str(start_key) not in room_ids:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 startroom "
                f"'{start_key}' 不是已定义的房间"
            )
        if str(start_key) != room_key:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 startroom "
                f"'{start_key}' 与 objects 房间 '{room_key}' 不一致；"
                f"objects 决定初始位置，startroom 仅作补刷出生房且须相同"
            )
        respawn = bool(data.get("respawn", False))
        room_id = room_ids[room_key]
        startroom_id = room_ids[str(start_key)]
        label = f"NPC '{npc_key}'"
        # name 必需：与 _attach_identity_and_description 同校验，提前到蓝图登记前。
        name = data.get("name")
        if not name:
            raise SceneLoadError(f"场景文件 {scene_path} 的{label}缺少必需字段 'name'")
        aliases_raw = data.get("aliases") or ()
        if not isinstance(aliases_raw, (list, tuple)):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}'aliases' 应是列表，"
                f"实际是 {type(aliases_raw).__name__}"
            )
        capability_seed = _parse_npc_capabilities(data, label=label, scene_path=scene_path)
        # Inquiry/Behaviors/AIController 有专属蓝图字段；其余进 extras.capabilities。
        _SPECIAL_NPC = {Inquiry, Behaviors, AIController}
        extra_caps = tuple(
            component for ctype, component in capability_seed.items() if ctype not in _SPECIAL_NPC
        )
        extras: dict[str, object] = {}
        if extra_caps:
            extras["capabilities"] = extra_caps
        loot = parse_loot_table(data.get("loot"))
        if loot is not None:
            extras["loot"] = loot
        blueprint = SpawnerBlueprint(
            template_key=key,
            name=str(name),
            aliases=tuple(str(a) for a in aliases_raw),
            short=str(data.get("short", name)),
            long=str(data.get("long", "")),
            startroom=startroom_id,
            desired_count=count,
            respawn=respawn,
            inquiry=capability_seed.get(Inquiry),  # type: ignore[arg-type]
            behaviors=capability_seed.get(Behaviors),  # type: ignore[arg-type]
            tick_interval=(
                capability_seed[AIController].tick_interval  # type: ignore[index]
                if AIController in capability_seed
                else 1
            ),
            extras=extras,
        )
        world.spawners[key] = blueprint
        for _ in range(count):
            npc = spawn_from_blueprint(world, blueprint, room=room_id)
            # 商店 NPC 需要 Container 才能走 transfer 收货/发货。
            if world.has_component(npc, ShopInventory) and not world.has_component(npc, Container):
                world.add_component(npc, Container())
            _capture_entity_unknown_fields(world, npc, data, _NPC_KNOWN_FIELDS)


def _parse_npc_capabilities(data: Mapping, *, label: str, scene_path: Path) -> dict[type, object]:
    """解析 NPC 能力组件一次，供蓝图登记（挂载由 spawn_from_blueprint 负责）。"""
    attached: dict[type, object] = {}
    for spec in NPC_CAPABILITIES:
        component = spec.from_yaml(data, label, scene_path, attached)
        if component is not None:
            attached[type(component)] = component
    return attached


def _parse_positive_int(raw: object, field: str, key: object, scene_path: Path) -> int:
    """解析正整数字段（objects 数量等）：须为 >= 1 的整数。"""
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 '{key}' 的 '{field}' 应是正整数，实际是 {raw!r}"
        ) from None
    if value < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 '{key}' 的 '{field}' 应 >= 1，实际是 {value}"
        )
    return value


def _build_player(
    world: World,
    player: Mapping,
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> EntityId:
    """建玩家实体（Identity+Position+Container+PlayerSession + 可选成长/经济能力）。"""
    name = player.get("name")
    if not name:
        raise SceneLoadError(f"场景文件 {scene_path} 的 player 缺少必需字段 'name'")
    start_room = player.get("start_room")
    if not start_room:
        raise SceneLoadError(f"场景文件 {scene_path} 的 player 缺少 'start_room'")
    if str(start_room) not in room_ids:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 player.start_room '{start_room}' 不是已定义的房间"
        )
    player_id = world.create_entity()
    world.add_component(player_id, Identity(name=str(name)))
    world.add_component(player_id, Position(room=room_ids[str(start_room)]))
    world.add_component(player_id, Container())
    world.add_component(player_id, PlayerSession())
    world.primary_player_id = player_id
    # 复用 NPC 能力注册表解析 vitals/attributes/skills/currency/faction 等。
    _attach_capability_specs(
        world,
        player_id,
        player,
        NPC_CAPABILITIES,
        label="player",
        scene_path=scene_path,
    )
    faction = world.get_component(player_id, Faction)
    if (
        faction is not None
        and faction.faction_id is not None
        and faction.faction_id not in FACTIONS
    ):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 player.faction '{faction.faction_id}' 不是已声明的门派"
        )
    _capture_entity_unknown_fields(world, player_id, player, _PLAYER_KNOWN_FIELDS)
    return player_id


def _attach_identity_and_description(
    world: World,
    entity: EntityId,
    data: Mapping,
    *,
    label: str,
    scene_path: Path,
    outdoors: bool = False,
) -> None:
    """给实体挂 Identity + Description：name 必需、short 缺省取 name、long 缺省空。

    房间/物品/NPC 共用这一份"名字+描述"装配（玩家除外，玩家不挂 Description）。
    ``outdoors`` 仅房间路径传 True（spec US 20 限定户外标记只挂房间 Description）；
    物品/NPC 不读 YAML 的 ``outdoors`` 键到 Description，避免无消费者的冗余字段
    （物品/NPC YAML 的 ``outdoors`` 键仍按未识别段透传进 entity_extension_data）。
    """
    name = data.get("name")
    if not name:
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}缺少必需字段 'name'")
    aliases = data.get("aliases") or ()
    if not isinstance(aliases, (list, tuple)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}'aliases' 应是列表，实际是 {type(aliases).__name__}"
        )
    world.add_component(
        entity,
        Identity(name=str(name), aliases=tuple(str(a) for a in aliases)),
    )
    world.add_component(
        entity,
        Description(
            short=str(data.get("short", name)),
            long=str(data.get("long", "")),
            outdoors=outdoors,
        ),
    )


def _resolve_ferry_refs(world: World, room_ids: dict[str, EntityId], scene_path: Path) -> None:
    """把 Ferry._far_bank_key 解析为 EntityId，并校验两岸互相指向。"""
    key_by_id = {eid: key for key, eid in room_ids.items()}
    for room in list(world.entities_with(Ferry)):
        ferry = world.require_component(room, Ferry)
        key = ferry._far_bank_key
        if not key:
            continue
        if key not in room_ids:
            room_key = key_by_id.get(room, str(room))
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 ferry.far_bank "
                f"'{key}' 不是已定义的房间"
            )
        far = room_ids[key]
        far_ferry = world.get_component(far, Ferry)
        if far_ferry is None:
            room_key = key_by_id.get(room, str(room))
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 ferry.far_bank "
                f"'{key}' 未挂 Ferry 组件"
            )
        ferry.far_bank = far
        ferry._far_bank_key = None
    # 互指校验（两端 far_bank 必须互相指向）。
    for room in list(world.entities_with(Ferry)):
        ferry = world.require_component(room, Ferry)
        far_ferry = world.require_component(ferry.far_bank, Ferry)
        if far_ferry.far_bank != room:
            room_key = key_by_id.get(room, str(room))
            far_key = key_by_id.get(ferry.far_bank, str(ferry.far_bank))
            raise SceneLoadError(
                f"场景文件 {scene_path} 的渡口 '{room_key}' 与 '{far_key}' "
                f"的 ferry.far_bank 未互相指向"
            )


def _validate_shop_inventories(world: World, scene_path: Path) -> None:
    """商店引用：物品须有 Valuable；坐骑须在 spawners 且蓝图带 Mount。"""
    for npc in world.entities_with(ShopInventory):
        shop = world.require_component(npc, ShopInventory)
        npc_name = world.require_component(npc, Identity).name
        for entry in shop.entries:
            if entry.mount_template_key:
                key = entry.mount_template_key
                blueprint = world.spawners.get(key)
                if blueprint is None:
                    raise SceneLoadError(
                        f"场景文件 {scene_path} 的商店 NPC '{npc_name}' "
                        f"引用未定义的坐骑模板 '{key}'"
                    )
                caps = blueprint.extras.get("capabilities", ())
                has_mount = isinstance(caps, (list, tuple)) and any(
                    isinstance(c, Mount) for c in caps
                )
                if not has_mount:
                    raise SceneLoadError(
                        f"场景文件 {scene_path} 的商店 NPC '{npc_name}' "
                        f"引用的坐骑模板 '{key}' 未声明 mount:"
                    )
                continue
            key = entry.item_template_key
            if not key or key not in world.item_templates:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的商店 NPC '{npc_name}' 引用未定义的物品模板 '{key}'"
                )
            raw = world.item_templates[key]
            if "valuable" not in raw and "value" not in raw:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的商店 NPC '{npc_name}' "
                    f"引用的物品模板 '{key}' 未声明 Valuable（valuable/value）"
                )


def _validate_faction_refs(world: World, scene_path: Path) -> None:
    """NPC Faction 引用必须在 FACTIONS 中声明。"""
    for entity in world.entities_with(Faction):
        faction = world.require_component(entity, Faction)
        if faction.faction_id is None:
            continue
        if faction.faction_id not in FACTIONS:
            name = world.require_component(entity, Identity).name
            raise SceneLoadError(
                f"场景文件 {scene_path} 的实体 '{name}' 的 faction "
                f"'{faction.faction_id}' 不是已声明的门派"
            )


def instantiate_item(world: World, template_key: str) -> EntityId:
    """按 ``world.item_templates`` 实例化一件新物品（商店 buy 用）。"""
    data = world.item_templates.get(template_key)
    if data is None:
        raise KeyError(f"未知物品模板：{template_key}")
    item = world.create_entity()
    # scene_path 仅用于报错文案；模板已在加载期校验过。
    scene_path = world.scene_path or Path("<memory>")
    _attach_identity_and_description(
        world, item, data, label=f"物品模板 '{template_key}'", scene_path=scene_path
    )
    _attach_item_capabilities(
        world, item, data, label=f"物品模板 '{template_key}'", scene_path=scene_path
    )
    return item


__all__ = [
    "SceneLoadError",
    "instantiate_item",
    "load_scene",
    "read_nature_config",
]
