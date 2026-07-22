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

import random
from collections.abc import Mapping
from pathlib import Path

import yaml

from mud_engine.ai import (
    ItemSpawnerBlueprint,
    SpawnerBlueprint,
    spawn_from_blueprint,
    spawn_item_from_blueprint,
)
from mud_engine.capabilities import (
    CAPABILITIES,
    NPC_CAPABILITIES,
    ROOM_CAPABILITIES,
    CapabilitySpec,
)
from mud_engine.components import (
    AIController,
    Behaviors,
    BlockExits,
    Container,
    Description,
    Door,
    Doors,
    DoorState,
    Exit,
    Exits,
    Faction,
    Ferry,
    HiddenExit,
    HiddenExits,
    Identity,
    Inquiry,
    ItemTemplateKey,
    Mount,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    QuestProgress,
    RoomHookBinding,
    ShopInventory,
)
from mud_engine.death_flow import parse_death_policy, parse_loot_table
from mud_engine.errors import SceneLoadError
from mud_engine.factions import FACTIONS, load_factions_from_mapping, replace_factions_registry
from mud_engine.library import parse_book_catalog, resolve_library_books
from mud_engine.quest import QuestDef
from mud_engine.runtime import wire_runtime
from mud_engine.semantic_color import validate_markup
from mud_engine.skills import load_skills_from_mapping, replace_skills_registry
from mud_engine.world import EntityId, World

# ``SceneLoadError`` 规范在 ``mud_engine.errors``；本模块再导出以保持
# ``from mud_engine.scene_loader import SceneLoadError`` 向后兼容。


def load_scene(
    scene_path: Path,
    *,
    pack_track: bool = False,
    rng: random.Random | None = None,
) -> tuple[World, EntityId]:
    """从一份 YAML 场景文件构造 ``(world, player_id)``。

    任何结构性错误（YAML 语法、缺字段、引用不存在的房间键）都收口成
    ``SceneLoadError``，消息含文件路径与大致出错的条目键。先建全部房间，再按
    房间 ``objects`` 摆物品、连出口/门、放 NPC、放玩家--物品先于出口是因为出口
    的门锁可引用物品作为钥匙（04 号票），建出口时需要物品的 entity id 已就绪。
    放置权威是房间 ``objects``（ADR-0010）；``placed_in`` / ``in_room`` 一律拒绝。

    ``pack_track=True``（内容包轨道，由 ``load_pack`` 传入）时禁止房间 ``hooks``
    字段——与旁路检测到同级 ``manifest.yaml`` 一样 fail-closed（ADR-0012）。

    ``rng`` 供加载期 ``random_of`` 出口原语选定目标；缺省用系统 ``Random()``。
    """
    scene_path = Path(scene_path)
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
    reject_hooks = pack_track or (scene_path.parent / "manifest.yaml").is_file()
    room_ids = _build_rooms(world, rooms, scene_path, reject_hooks=reject_hooks)
    world.room_ids = dict(room_ids)
    catalog = parse_book_catalog(data.get("books"), scene_path)
    resolve_library_books(world, catalog, scene_path)
    world.death_policy = parse_death_policy(data.get("death_policy"))
    _resolve_ferry_refs(world, room_ids, scene_path)
    _reject_legacy_placement_fields(items, npcs, scene_path)
    placements = _collect_room_objects(rooms, items, npcs, scene_path)
    _reject_door_key_slot_conflicts(rooms, items, placements, scene_path)
    item_ids = _build_items(world, items, placements, room_ids, scene_path)
    exit_rng = rng if rng is not None else random.Random()
    _build_exits(world, rooms, room_ids, item_ids, scene_path, rng=exit_rng)
    _build_npcs(world, npcs, placements, room_ids, scene_path)
    _validate_shop_inventories(world, scene_path)
    _validate_faction_refs(world, scene_path)
    _load_quests(world, data.get("quests"), npcs, items, scene_path)
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
    {
        "rooms",
        "items",
        "npcs",
        "player",
        "skills",
        "factions",
        "death_policy",
        "quests",
        "books",
    }
)
_ROOM_INTRINSIC_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "exits",
        "objects",
        "block_exits",
        "hooks",  # 官方轨专属；内容包轨见 _attach_room_hook_binding 拒绝
    }
)
_ROOM_KNOWN_FIELDS = frozenset(
    _ROOM_INTRINSIC_FIELDS | {field for spec in ROOM_CAPABILITIES for field in spec.known_fields}
)
# 物品能力字段（18/21/22/24 号票 + 31 号票注册表）：从 ``CAPABILITIES``
# 聚合每个能力的 known_fields，避免新增能力时漏改 _ITEM_KNOWN_FIELDS 导致透传误吞字段。
# 放置由房间 ``objects`` 声明（ADR-0010），模板段不再含 ``placed_in``。
# ``respawn`` 与 NPC 对齐：控制 objects 槽位销毁后是否补刷（pre-m4-04）。
_ITEM_KNOWN_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "respawn",
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


def _build_rooms(
    world: World,
    rooms: Mapping,
    scene_path: Path,
    *,
    reject_hooks: bool = False,
) -> dict[str, EntityId]:
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
        _attach_room_hook_binding(
            world, room, data, room_key, scene_path, reject_hooks=reject_hooks
        )
        _capture_entity_unknown_fields(world, room, data, _ROOM_KNOWN_FIELDS)
        room_ids[room_key] = room
    return room_ids


def _attach_room_hook_binding(
    world: World,
    room: EntityId,
    data: Mapping,
    room_key: str,
    scene_path: Path,
    *,
    reject_hooks: bool,
) -> None:
    """解析 ``hooks: {hook_id, params?}``；内容包轨或未注册 id 一律 ``SceneLoadError``。"""
    raw = data.get("hooks")
    if raw is None:
        return
    if reject_hooks:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 声明了 hooks，"
            f"但内容包轨道禁止房间钩子（hooks 为官方轨专属，见 ADR-0012）"
        )
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的 'hooks' 应是映射，"
            f"实际是 {type(raw).__name__}"
        )
    hook_id = raw.get("hook_id")
    if hook_id is None or hook_id == "":
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的 hooks 缺少必需字段 'hook_id'"
        )
    hook_id_s = str(hook_id)
    from mud_engine.room_hooks import get_room_hook

    if get_room_hook(hook_id_s) is None:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 引用了未注册的 hook_id "
            f"'{hook_id_s}'"
        )
    params_raw = raw.get("params", {})
    if params_raw is None:
        params_raw = {}
    if not isinstance(params_raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的 hooks.params 应是映射，"
            f"实际是 {type(params_raw).__name__}"
        )
    world.add_component(
        room,
        RoomHookBinding(hook_id=hook_id_s, params=dict(params_raw)),
    )


def _build_exits(
    world: World,
    rooms: Mapping,
    room_ids: dict[str, EntityId],
    item_ids: dict[str, EntityId],
    scene_path: Path,
    *,
    rng: random.Random,
) -> None:
    """把每个房间的 exits 段连成 Exit 组件条目，校验目标房间键都已定义。

    出口可选挂门状态（``door``/``key``/``consume_key`` 字段）：带门的出口同时往
    该房间的 ``Doors`` 组件里记一条 ``Door``。``hidden_until_unlocked: true`` 的
    出口进入 ``HiddenExits``（不进 ``Exits``），解锁后由命令层揭示。

    ``random_of``：加载期从候选目标中随机选定一个，落地为普通 ``to`` 出口（无运行时
    副作用；不进钩子注册表）。
    """
    for room_key, raw in rooms.items():
        data = _as_mapping(raw, label=f"房间 '{room_key}'", scene_path=scene_path)
        exits_data = data.get("exits")
        if exits_data is None:
            _attach_block_exits(world, room_ids[room_key], data, room_key, scene_path)
            continue
        if not isinstance(exits_data, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 'exits' 应是映射，"
                f"实际是 {type(exits_data).__name__}"
            )
        room = room_ids[room_key]
        exits = world.require_component(room, Exits)
        doors: Doors | None = None
        hidden: HiddenExits | None = None
        for direction, exit_data in exits_data.items():
            target_key = _exit_target(exit_data, room_key, direction, scene_path, rng=rng)
            if target_key not in room_ids:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 "
                    f"'{direction}' 指向未定义的房间 '{target_key}'"
                )
            aliases = _exit_aliases(exit_data, room_key, direction, scene_path)
            direction_s = str(direction)
            target_id = room_ids[target_key]
            door = _exit_door(exit_data, room_key, direction, item_ids, scene_path)
            hidden_flag = (
                isinstance(exit_data, Mapping) and bool(exit_data.get("hidden_until_unlocked"))
            )
            if hidden_flag:
                if door is None or door.state is not DoorState.LOCKED:
                    raise SceneLoadError(
                        f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 "
                        f"'{direction}' 声明 hidden_until_unlocked 时必须 door: locked"
                    )
                if hidden is None:
                    hidden = HiddenExits()
                    world.add_component(room, hidden)
                hidden.by_direction[direction_s] = HiddenExit(target=target_id, aliases=aliases)
            else:
                exits.by_direction[direction_s] = Exit(target=target_id, aliases=aliases)
            if door is not None:
                if doors is None:
                    doors = Doors()
                    world.add_component(room, doors)
                doors.by_direction[direction_s] = door
        _attach_block_exits(world, room, data, room_key, scene_path)


def _attach_block_exits(
    world: World,
    room: EntityId,
    data: Mapping,
    room_key: str,
    scene_path: Path,
) -> None:
    """解析 ``block_exits: {dir: {npc: template_key}}``。"""
    raw = data.get("block_exits")
    if raw is None:
        return
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的 'block_exits' 应是映射"
        )
    by_dir: dict[str, str] = {}
    for direction, spec in raw.items():
        if not isinstance(spec, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 block_exits['{direction}'] "
                f"应是映射（含 npc）"
            )
        npc = spec.get("npc")
        if not npc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的 block_exits['{direction}'] "
                f"缺少 'npc'（NPC 模板键）"
            )
        by_dir[str(direction)] = str(npc)
    if by_dir:
        world.add_component(room, BlockExits(by_direction=by_dir))


def _exit_target(
    exit_data: object,
    room_key: str,
    direction: object,
    scene_path: Path,
    *,
    rng: random.Random,
) -> str:
    """取出口目标房间键：``{ to: <key> }`` / ``{ random_of: [...] }`` 映射或裸字符串键。"""
    if isinstance(exit_data, Mapping):
        has_to = "to" in exit_data and exit_data.get("to") not in (None, "")
        has_random = "random_of" in exit_data
        if has_to and has_random:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' "
                f"不能同时声明 'to' 与 'random_of'"
            )
        if has_random:
            return _exit_random_of_target(
                exit_data["random_of"], room_key, direction, scene_path, rng
            )
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


def _exit_random_of_target(
    raw: object,
    room_key: str,
    direction: object,
    scene_path: Path,
    rng: random.Random,
) -> str:
    """加载期从 ``random_of`` 候选列表选定一个目标房间键。"""
    if not isinstance(raw, (list, tuple)) or not raw:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的房间 '{room_key}' 的出口 '{direction}' "
            f"的 'random_of' 应是非空列表"
        )
    candidates = [str(c) for c in raw]
    return rng.choice(candidates)


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
    consume_key = bool(exit_data.get("consume_key", False))
    return Door(state=state, key_item_id=key_item_id, consume_key=consume_key)


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
            # 允许 0：登记蓝图/槽位但不首刷（劫匪刷拦等「进房再生成」机关）。
            count = _parse_non_negative_int(raw_count, "objects", key, scene_path)
            if key in npc_keys and key in placements:
                prev_room, _ = placements[key][0]
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的 NPC '{key}' 在房间 '{prev_room}' 与 "
                    f"'{room_key}' 的 objects 中重复出现；每个 NPC 模板只能放在一个房间"
                )
            placements.setdefault(key, []).append((str(room_key), count))
    return placements


def _collect_door_key_templates(rooms: Mapping, scene_path: Path) -> set[str]:
    """收集出口 ``key`` 引用的物品模板键（门锁唯一实体引用）。"""
    keys: set[str] = set()
    for room_key, raw in rooms.items():
        data = _as_mapping(raw, label=f"房间 '{room_key}'", scene_path=scene_path)
        exits_data = data.get("exits")
        if not isinstance(exits_data, Mapping):
            continue
        for _direction, exit_data in exits_data.items():
            if not isinstance(exit_data, Mapping):
                continue
            raw_key = exit_data.get("key")
            if raw_key is not None:
                keys.add(str(raw_key))
    return keys


def _reject_door_key_slot_conflicts(
    rooms: Mapping,
    items: Mapping,
    placements: Mapping[str, list[tuple[str, int]]],
    scene_path: Path,
) -> None:
    """门锁 ``key`` 绑定的物品不得 ``count>1`` 或 ``respawn: true``（唯一实体引用）。"""
    key_templates = _collect_door_key_templates(rooms, scene_path)
    for key in key_templates:
        if key not in items:
            # 未定义键由 _door_key_item_id 在建出口时报错。
            continue
        data = _as_mapping(items[key], label=f"物品 '{key}'", scene_path=scene_path)
        total = sum(count for _, count in placements.get(key, ()))
        respawn = bool(data.get("respawn", False))
        if total > 1:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的物品 '{key}' 被门锁 key 唯一引用，"
                f"但房间 objects 合计数量为 {total}（>1）；唯一引用物品不得多份"
            )
        if respawn:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的物品 '{key}' 被门锁 key 唯一引用，"
                f"但声明了 respawn: true；唯一引用物品不可补刷"
            )


def _build_items(
    world: World,
    items: Mapping,
    placements: Mapping[str, list[tuple[str, int]]],
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> dict[str, EntityId]:
    """登记物品模板，并按房间 ``objects`` 在地面生成槽位实例。

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
        respawn = bool(data.get("respawn", False))
        first_item: EntityId | None = None
        for room_key, count in room_placements:
            blueprint = ItemSpawnerBlueprint(
                template_key=key,
                room_key=room_key,
                startroom=room_ids[room_key],
                desired_count=count,
                respawn=respawn,
            )
            world.item_spawners[(room_key, key)] = blueprint
            for _ in range(count):
                item = spawn_item_from_blueprint(world, blueprint)
                blueprint.slots.append(item)
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
        short, long = _validated_description_texts(
            data, name=str(name), label=label, scene_path=scene_path
        )
        blueprint = SpawnerBlueprint(
            template_key=key,
            name=str(name),
            aliases=tuple(str(a) for a in aliases_raw),
            short=short,
            long=long,
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
            blueprint.slots.append(npc)
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


def _parse_non_negative_int(
    raw: object, field: str, key: object, scene_path: Path
) -> int:
    """解析非负整数字段（房间 ``objects`` 数量）：须为 >= 0 的整数。

    ``0`` 表示登记模板/蓝图但不生成初始实例（供钩子运行时 ``ensure_npc``）。
    """
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 '{key}' 的 '{field}' 应是非负整数，"
            f"实际是 {raw!r}"
        ) from None
    if value < 0:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 '{key}' 的 '{field}' 应 >= 0，实际是 {value}"
        )
    return value


def _parse_positive_int(raw: object, field: str, key: object, scene_path: Path) -> int:
    """解析正整数字段：须为 >= 1 的整数。"""
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
    world.add_component(player_id, QuestProgress())
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
    short, long = _validated_description_texts(
        data, name=str(name), label=label, scene_path=scene_path
    )
    world.add_component(
        entity,
        Description(
            short=short,
            long=long,
            outdoors=outdoors,
        ),
    )


def _validated_description_texts(
    data: Mapping, *, name: str, label: str, scene_path: Path
) -> tuple[str, str]:
    """取 short/long 并做语义色校验（房间/物品/NPC 蓝图共用，ADR-0011）。"""
    short = str(data.get("short", name))
    long = str(data.get("long", ""))
    validate_markup(short, location=f"场景文件 {scene_path} 的{label}.short")
    validate_markup(long, location=f"场景文件 {scene_path} 的{label}.long")
    return short, long


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


def _load_quests(
    world: World,
    raw_quests: object,
    npcs: Mapping,
    items: Mapping,
    scene_path: Path,
) -> None:
    """解析顶层 ``quests:``，登记 ``world.quests``，并为交物目标 NPC 挂 Container。"""
    if raw_quests is None:
        return
    if not isinstance(raw_quests, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 'quests' 段应是映射，实际是 {type(raw_quests).__name__}"
        )
    npc_keys = {str(k) for k in npcs}
    item_keys = {str(k) for k in items}
    for quest_id, raw in raw_quests.items():
        data = _as_mapping(raw, label=f"任务 '{quest_id}'", scene_path=scene_path)
        qid = str(quest_id)
        name = str(data.get("name") or qid)
        accept = data.get("accept") or {}
        if accept is not None and not isinstance(accept, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的任务 '{qid}' 的 accept 应是映射"
            )
        accept_map = dict(accept) if isinstance(accept, Mapping) else {}
        require_npc = accept_map.get("require_npc")
        if require_npc is not None:
            require_npc = str(require_npc)
            if require_npc not in npc_keys:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的任务 '{qid}' 的 accept.require_npc "
                    f"'{require_npc}' 不是已定义的 NPC 模板"
                )
        complete = data.get("complete") or {}
        if complete is not None and not isinstance(complete, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的任务 '{qid}' 的 complete 应是映射"
            )
        complete_map = dict(complete) if isinstance(complete, Mapping) else {}
        give_item = complete_map.get("give_item")
        to_npc = complete_map.get("to_npc")
        if give_item is not None:
            give_item = str(give_item)
            if give_item not in item_keys:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的任务 '{qid}' 的 complete.give_item "
                    f"'{give_item}' 不是已定义的物品模板"
                )
        if to_npc is not None:
            to_npc = str(to_npc)
            if to_npc not in npc_keys:
                raise SceneLoadError(
                    f"场景文件 {scene_path} 的任务 '{qid}' 的 complete.to_npc "
                    f"'{to_npc}' 不是已定义的 NPC 模板"
                )
        if (give_item is None) ^ (to_npc is None):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的任务 '{qid}' 的 complete.give_item 与 "
                f"complete.to_npc 须同时声明或同时省略"
            )
        flags_raw = complete_map.get("flags") or {}
        if flags_raw and not isinstance(flags_raw, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的任务 '{qid}' 的 complete.flags 应是映射"
            )
        required_flags = frozenset(
            (str(k), bool(v)) for k, v in dict(flags_raw).items()
        ) if isinstance(flags_raw, Mapping) else frozenset()
        if give_item is None and not required_flags:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的任务 '{qid}' 须声明 complete.give_item+to_npc "
                f"或 complete.flags 之一"
            )
        reward = data.get("reward") or {}
        if reward is not None and not isinstance(reward, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的任务 '{qid}' 的 reward 应是映射"
            )
        reward_map = dict(reward) if isinstance(reward, Mapping) else {}
        reward_currency = int(reward_map.get("currency", 0) or 0)
        messages = data.get("messages") or {}
        msg_map = dict(messages) if isinstance(messages, Mapping) else {}
        world.quests[qid] = QuestDef(
            quest_id=qid,
            name=name,
            require_npc=require_npc,
            give_item=give_item,
            to_npc=to_npc,
            required_flags=required_flags,
            reward_currency=reward_currency,
            accept_message=str(msg_map["accept"]) if "accept" in msg_map else None,
            complete_message=str(msg_map["complete"]) if "complete" in msg_map else None,
        )
        if to_npc is not None:
            _ensure_npc_template_has_container(world, to_npc)


def _ensure_npc_template_has_container(world: World, template_key: str) -> None:
    """交物目标 NPC 须有 Container，否则 give 无法完成任务。"""
    for entity in world.entities_with(NpcSpawnMeta):
        meta = world.require_component(entity, NpcSpawnMeta)
        if meta.template_key != template_key:
            continue
        if not world.has_component(entity, Container):
            world.add_component(entity, Container())


def instantiate_item(world: World, template_key: str) -> EntityId:
    """按 ``world.item_templates`` 实例化一件新物品（商店 buy / 槽位补刷共用）。"""
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
    world.add_component(item, ItemTemplateKey(key=template_key))
    return item


__all__ = [
    "SceneLoadError",
    "instantiate_item",
    "load_scene",
    "read_nature_config",
]
