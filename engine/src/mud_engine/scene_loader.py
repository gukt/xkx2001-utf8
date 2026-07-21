"""场景数据 YAML 加载器：把一份 YAML 文件读成 ``(world, player_id)``。

这是 06 号票落地的"M1 内部过渡格式"加载逻辑（见 M1 spec「场景数据与引擎能力
的边界」2026-07-18 修订）--目标是非工程师也能改场景数据、跑通闭环优先，不是
M3 要交给创作者的正式 UGC DSL。覆盖范围：房间 / 物品 / 静态展示型 NPC / 门与
锁状态（04 号票）。

加载逻辑与命令调度（commands）/ ECS 存储（world）保持分离：本模块只依赖
components + world + PyYAML，不 import commands，也不把加载逻辑写进 world.py
或 commands.py（06 号票 acceptance 第 5 条）。YAML 里引用了不存在的房间键、
缺必需字段等结构性错误，抛 ``SceneLoadError``（消息带文件路径与出错的数据键），
而不是让裸 Python 异常堆栈糊到启动者脸上--这是"加载期数据校验"，与 05 号票
"崩溃恢复级"的运行时存档语义是两件不同的事，不要混着实现。
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml

from mud_engine.ai import SpawnerBlueprint, attach_ai_system, spawn_from_blueprint
from mud_engine.capabilities import (
    CAPABILITIES,
    NPC_CAPABILITIES,
    ROOM_CAPABILITIES,
    CapabilitySpec,
)
from mud_engine.combat_system import attach_combat_system
from mud_engine.death_flow import parse_death_policy, parse_loot_table
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
from mud_engine.entity_gate import attach_entry_guards
from mud_engine.errors import SceneLoadError
from mud_engine.factions import FACTIONS, load_factions_from_mapping, replace_factions_registry
from mud_engine.ferry import attach_ferries
from mud_engine.nature import attach_nature
from mud_engine.skills import load_skills_from_mapping, replace_skills_registry
from mud_engine.world import EntityId, World

# ``SceneLoadError`` 规范在 ``mud_engine.errors``；本模块再导出以保持
# ``from mud_engine.scene_loader import SceneLoadError`` 向后兼容。


def load_scene(scene_path: Path) -> tuple[World, EntityId]:
    """从一份 YAML 场景文件构造 ``(world, player_id)``。

    任何结构性错误（YAML 语法、缺字段、引用不存在的房间键）都收口成
    ``SceneLoadError``，消息含文件路径与大致出错的条目键。先建全部房间，再摆
    物品、连出口/门、放 NPC、放玩家--物品先于出口是因为出口的门锁可引用物品
    作为钥匙（04 号票），建出口时需要物品的 entity id 已就绪。
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
    item_ids = _build_items(world, items, room_ids, scene_path)
    _build_exits(world, rooms, room_ids, item_ids, scene_path)
    _build_npcs(world, npcs, room_ids, scene_path)
    _validate_shop_inventories(world, scene_path)
    _validate_faction_refs(world, scene_path)
    player_id = _build_player(world, player, room_ids, scene_path)
    _capture_top_level_unknown_sections(world, data)
    # Nature（13 号票）：从透传的 nature 段（若有）挂载时辰循环；无配置则用默认四相。
    # nature 仍留在 extension_data（透传不丢），attach_nature 只读不删。
    attach_nature(world)
    # NPC AI（25 号票）：挂 on_tick 遍历 AIController；幂等，无行为 NPC 时为空转。
    attach_ai_system(world)
    # 渡口（M2-09）：按周期翻转两岸出口；幂等。
    attach_ferries(world)
    # 交战（M2-12）：Engaged tick 结算；幂等。
    attach_combat_system(world)
    # 门槏（M2-11）：EntryGuard on_before_enter_room；幂等。
    attach_entry_guards(world)
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
_ROOM_INTRINSIC_FIELDS = frozenset({"name", "aliases", "short", "long", "exits"})
_ROOM_KNOWN_FIELDS = frozenset(
    _ROOM_INTRINSIC_FIELDS | {field for spec in ROOM_CAPABILITIES for field in spec.known_fields}
)
# 物品能力字段（18/21/22/24 号票 + 31 号票注册表）：从 ``CAPABILITIES``
# 聚合每个能力的 known_fields，避免新增能力时漏改 _ITEM_KNOWN_FIELDS 导致透传误吞字段。
_ITEM_KNOWN_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "placed_in",
    }
    | {field for spec in CAPABILITIES for field in spec.known_fields}
)
_NPC_INTRINSIC_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "in_room",
        "startroom",
        "count",
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


def _build_items(
    world: World,
    items: Mapping,
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> dict[str, EntityId]:
    """建物品实体（Identity+Description+按需能力组件）并放进 placed_in 房间地面。

    返回 item key -> entity id 映射，供出口的 ``door.key`` 引用钥匙物品（04 号票）。
    能力组件（18/21/22/24 号票）按 YAML 字段按需挂载，未声明不挂。
    """
    item_ids: dict[str, EntityId] = {}
    for item_key, raw in items.items():
        data = _as_mapping(raw, label=f"物品 '{item_key}'", scene_path=scene_path)
        placed_in = data.get("placed_in")
        if not placed_in:
            raise SceneLoadError(f"场景文件 {scene_path} 的物品 '{item_key}' 缺少 'placed_in'")
        if str(placed_in) not in room_ids:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的物品 '{item_key}' 的 placed_in "
                f"'{placed_in}' 不是已定义的房间"
            )
        item = world.create_entity()
        _attach_identity_and_description(
            world, item, data, label=f"物品 '{item_key}'", scene_path=scene_path
        )
        _attach_item_capabilities(
            world, item, data, label=f"物品 '{item_key}'", scene_path=scene_path
        )
        room_container = world.require_component(room_ids[str(placed_in)], Container)
        room_container.items.add(item)
        _capture_entity_unknown_fields(world, item, data, _ITEM_KNOWN_FIELDS)
        item_ids[str(item_key)] = item
        # 商店 buy 按模板键实例化：保留原始 YAML（M2-07）。
        world.item_templates[str(item_key)] = dict(data)
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
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> None:
    """建 NPC：解析一次能力 → 注册 SpawnerBlueprint → 经 spawn_from_blueprint 实例化。

    ``count`` 控制实例数（默认 1）；``startroom`` 可作 ``in_room`` 别名，也可
    单独声明出生房（与 in_room 并存时：位置用 in_room，spawn meta 用 startroom）。
    同一 template 的多个 count 实例只注册一条蓝图（M2-04）。加载与重生共用
    ``spawn_from_blueprint``，避免双路径装配分叉。
    """
    for npc_key, raw in npcs.items():
        data = _as_mapping(raw, label=f"NPC '{npc_key}'", scene_path=scene_path)
        room_key = data.get("in_room") or data.get("startroom")
        if not room_key:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 缺少 'in_room'（或 startroom）"
            )
        if str(room_key) not in room_ids:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的房间 '{room_key}' 不是已定义的房间"
            )
        start_key = data.get("startroom") or room_key
        if str(start_key) not in room_ids:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 startroom "
                f"'{start_key}' 不是已定义的房间"
            )
        count = _npc_count(data.get("count", 1), npc_key, scene_path)
        respawn = bool(data.get("respawn", False))
        room_id = room_ids[str(room_key)]
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
            template_key=str(npc_key),
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
        world.spawners[str(npc_key)] = blueprint
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


def _parse_positive_int(raw: object, field: str, npc_key: object, scene_path: Path) -> int:
    """解析正整数字段（count 等）：须为 >= 1 的整数。"""
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 '{field}' 应是正整数，实际是 {raw!r}"
        ) from None
    if value < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 '{field}' 应 >= 1，实际是 {value}"
        )
    return value


def _npc_count(raw: object, npc_key: object, scene_path: Path) -> int:
    """解析 count：默认 1，须为正整数。"""
    return _parse_positive_int(raw, "count", npc_key, scene_path)


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
