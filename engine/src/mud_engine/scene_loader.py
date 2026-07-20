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

from mud_engine.ai import attach_ai_system
from mud_engine.components import (
    AIController,
    Behaviors,
    BehaviorSpec,
    Consumable,
    Container,
    Description,
    Door,
    Doors,
    DoorState,
    Equippable,
    Exit,
    Exits,
    Identity,
    Inquiry,
    ItemFlags,
    NpcSpawnMeta,
    PlayerSession,
    Position,
    Stackable,
    Valuable,
    Weight,
)
from mud_engine.nature import attach_nature
from mud_engine.world import EntityId, World


class SceneLoadError(Exception):
    """场景数据加载/校验失败：消息带文件路径与出错的数据键定位。"""


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
    room_ids = _build_rooms(world, rooms, scene_path)
    item_ids = _build_items(world, items, room_ids, scene_path)
    _build_exits(world, rooms, room_ids, item_ids, scene_path)
    _build_npcs(world, npcs, room_ids, scene_path)
    player_id = _build_player(world, player, room_ids, scene_path)
    _capture_top_level_unknown_sections(world, data)
    # Nature（13 号票）：从透传的 nature 段（若有）挂载时辰循环；无配置则用默认四相。
    # nature 仍留在 extension_data（透传不丢），attach_nature 只读不删。
    attach_nature(world)
    # NPC AI（25 号票）：挂 on_tick 遍历 AIController；幂等，无行为 NPC 时为空转。
    attach_ai_system(world)
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
_TOP_LEVEL_KNOWN_SECTIONS = frozenset({"rooms", "items", "npcs", "player"})
_ROOM_KNOWN_FIELDS = frozenset({"name", "aliases", "short", "long", "exits", "outdoors"})
# 物品能力字段（18/21/22/24 号票）：stackable/valuable/equippable/consumable/
# no_take/no_drop/container/weight 等按需挂载；未声明不挂对应组件。
_ITEM_KNOWN_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "placed_in",
        "stackable",
        "amount",
        "unit_weight",
        "valuable",
        "value",
        "equippable",
        "consumable",
        "no_take",
        "no_drop",
        "no_drop_message",
        "container",
        "max_capacity",
        "max_weight",
        "weight",
    }
)
_NPC_KNOWN_FIELDS = frozenset(
    {
        "name",
        "aliases",
        "short",
        "long",
        "in_room",
        "startroom",
        "count",
        "respawn",
        "inquiry",
        "behaviors",
        "tick_interval",
    }
)
_PLAYER_KNOWN_FIELDS = frozenset({"name", "start_room"})


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
        _attach_identity_and_description(
            world,
            room,
            data,
            label=f"房间 '{room_key}'",
            scene_path=scene_path,
            outdoors=bool(data.get("outdoors", False)),
        )
        world.add_component(room, Exits())
        world.add_component(room, Container())
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
    return item_ids


def _attach_item_capabilities(
    world: World,
    item: EntityId,
    data: Mapping,
    *,
    label: str,
    scene_path: Path,
) -> None:
    """按 YAML 声明挂载 Stackable/Valuable/Equippable/Consumable/ItemFlags/Container/Weight。"""
    stackable = _parse_stackable(data, label=label, scene_path=scene_path)
    if stackable is not None:
        world.add_component(item, stackable)

    valuable = _parse_valuable(data, label=label, scene_path=scene_path)
    if valuable is not None:
        world.add_component(item, valuable)

    equippable = _parse_equippable(data, label=label, scene_path=scene_path)
    if equippable is not None:
        world.add_component(item, equippable)

    consumable = _parse_consumable(data, label=label, scene_path=scene_path)
    if consumable is not None:
        world.add_component(item, consumable)

    flags = _parse_item_flags(data, label=label, scene_path=scene_path)
    if flags is not None:
        world.add_component(item, flags)

    item_container = _parse_item_container(data, label=label, scene_path=scene_path)
    if item_container is not None:
        world.add_component(item, item_container)

    if "weight" in data and stackable is None:
        try:
            world.add_component(item, Weight(value=float(data["weight"])))
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 'weight' 应是数字，实际是 {data['weight']!r}"
            ) from exc


def _parse_stackable(
    data: Mapping, *, label: str, scene_path: Path
) -> Stackable | None:
    """``stackable: true|{amount, unit_weight}`` 或顶层 ``amount`` / ``unit_weight``。"""
    raw = data.get("stackable")
    amount = data.get("amount")
    unit_weight = data.get("unit_weight")
    if raw is None and amount is None and unit_weight is None:
        return None
    if isinstance(raw, Mapping):
        amount = raw.get("amount", amount)
        unit_weight = raw.get("unit_weight", unit_weight)
    elif raw is False:
        return None
    # raw is True / None with top-level amount / mapping already handled
    if amount is None:
        amount = 1
    try:
        amt = int(amount)
        uw = 1.0 if unit_weight is None else float(unit_weight)
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 stackable 字段非法：{exc}"
        ) from exc
    if amt < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 stackable.amount 应 >= 1，实际是 {amt}"
        )
    return Stackable(amount=amt, unit_weight=uw)


def _parse_valuable(data: Mapping, *, label: str, scene_path: Path) -> Valuable | None:
    """``valuable: <int>`` / ``valuable: {value: N}`` / 顶层 ``value: N``。"""
    raw = data.get("valuable", data.get("value") if "valuable" not in data else None)
    if "valuable" not in data and "value" not in data:
        return None
    if "valuable" in data:
        raw = data["valuable"]
    elif "value" in data:
        raw = data["value"]
    else:
        return None
    if isinstance(raw, Mapping):
        raw = raw.get("value")
    if raw is None or raw is False:
        return None
    try:
        return Valuable(value=int(raw))
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的 valuable/value 应是整数，实际是 {raw!r}"
        ) from exc


def _parse_equippable(
    data: Mapping, *, label: str, scene_path: Path
) -> Equippable | None:
    """``equippable: true|{slot, apply_hook}`` 占位。"""
    raw = data.get("equippable")
    if raw is None or raw is False:
        return None
    if raw is True:
        return Equippable()
    if isinstance(raw, Mapping):
        slot = str(raw.get("slot", "") or "")
        apply_hook = raw.get("apply_hook")
        hook = None if apply_hook is None else str(apply_hook)
        return Equippable(slot=slot, apply_hook=hook)
    raise SceneLoadError(
        f"场景文件 {scene_path} 的{label}的 'equippable' 应是 true 或映射，"
        f"实际是 {type(raw).__name__}"
    )


def _parse_consumable(
    data: Mapping, *, label: str, scene_path: Path
) -> Consumable | None:
    """``consumable: true|{uses}`` 占位。"""
    raw = data.get("consumable")
    if raw is None or raw is False:
        return None
    if raw is True:
        return Consumable()
    if isinstance(raw, Mapping):
        uses = raw.get("uses", 1)
        try:
            return Consumable(uses=int(uses))
        except (TypeError, ValueError) as exc:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的{label}的 consumable.uses 应是整数，实际是 {uses!r}"
            ) from exc
    raise SceneLoadError(
        f"场景文件 {scene_path} 的{label}的 'consumable' 应是 true 或映射，"
        f"实际是 {type(raw).__name__}"
    )


def _parse_item_flags(
    data: Mapping, *, label: str, scene_path: Path
) -> ItemFlags | None:
    """``no_take`` / ``no_drop`` / ``no_drop_message``；全缺省则不挂组件。"""
    if not any(k in data for k in ("no_take", "no_drop", "no_drop_message")):
        return None
    no_take = bool(data.get("no_take", False))
    no_drop = bool(data.get("no_drop", False))
    msg = data.get("no_drop_message")
    if msg is not None:
        msg = str(msg)
    if not no_take and not no_drop and msg is None:
        return None
    return ItemFlags(no_take=no_take, no_drop=no_drop, no_drop_message=msg)


def _parse_item_container(
    data: Mapping, *, label: str, scene_path: Path
) -> Container | None:
    """``container: true|{max_capacity, max_weight}`` 或顶层 max_* 且 container 真。"""
    raw = data.get("container")
    max_capacity = data.get("max_capacity")
    max_weight = data.get("max_weight")
    if raw is None and max_capacity is None and max_weight is None:
        return None
    if raw is False:
        return None
    if isinstance(raw, Mapping):
        max_capacity = raw.get("max_capacity", max_capacity)
        max_weight = raw.get("max_weight", max_weight)
    elif raw is None and (max_capacity is not None or max_weight is not None):
        # 仅顶层上限、未写 container: 不自动变容器（避免误挂）。
        return None
    # raw is True / mapping / 显式 container
    if raw is None:
        return None
    try:
        cap = None if max_capacity is None else int(max_capacity)
        w = None if max_weight is None else float(max_weight)
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}的容器上限字段非法：{exc}"
        ) from exc
    return Container(max_capacity=cap, max_weight=w)


def _build_npcs(
    world: World,
    npcs: Mapping,
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> None:
    """建 NPC：基础组件 + 可选 Inquiry/AIController/Behaviors + Spawn meta（25~27）。

    ``count`` 控制实例数（默认 1）；``startroom`` 可作 ``in_room`` 别名，也可
    单独声明出生房（与 in_room 并存时：位置用 in_room，spawn meta 用 startroom）。
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
        inquiry = _parse_inquiry(data.get("inquiry"), npc_key, scene_path)
        behaviors = _parse_behaviors(data.get("behaviors"), npc_key, scene_path)
        tick_interval = _npc_tick_interval(data.get("tick_interval", 1), npc_key, scene_path)
        for _ in range(count):
            npc = world.create_entity()
            _attach_identity_and_description(
                world, npc, data, label=f"NPC '{npc_key}'", scene_path=scene_path
            )
            world.add_component(npc, Position(room=room_id))
            world.add_component(
                npc,
                NpcSpawnMeta(
                    template_key=str(npc_key),
                    startroom=startroom_id,
                    desired_count=count,
                    respawn=respawn,
                ),
            )
            if inquiry is not None:
                world.add_component(npc, inquiry)
            if behaviors is not None:
                world.add_component(npc, AIController(tick_interval=tick_interval))
                world.add_component(npc, behaviors)
            _capture_entity_unknown_fields(world, npc, data, _NPC_KNOWN_FIELDS)


def _parse_positive_int(
    raw: object, field: str, npc_key: object, scene_path: Path
) -> int:
    """解析正整数字段（count / tick_interval 共用）：须为 >= 1 的整数。"""
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 '{field}' 应是正整数，"
            f"实际是 {raw!r}"
        ) from None
    if value < 1:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 '{field}' 应 >= 1，"
            f"实际是 {value}"
        )
    return value


def _npc_count(raw: object, npc_key: object, scene_path: Path) -> int:
    """解析 count：默认 1，须为正整数。"""
    return _parse_positive_int(raw, "count", npc_key, scene_path)


def _npc_tick_interval(raw: object, npc_key: object, scene_path: Path) -> int:
    """解析 tick_interval：默认 1，须为正整数。"""
    return _parse_positive_int(raw, "tick_interval", npc_key, scene_path)


def _parse_inquiry(raw: object, npc_key: object, scene_path: Path) -> Inquiry | None:
    """解析 inquiry：``{ topic: 文案, default: 兜底, handler: 钩子名 }``；缺省 None。"""
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 'inquiry' 应是映射，"
            f"实际是 {type(raw).__name__}"
        )
    topics: dict[str, str] = {}
    default: str | None = None
    handler: str | None = None
    for key, value in raw.items():
        key_s = str(key)
        if key_s == "default":
            default = str(value)
            continue
        if key_s == "handler":
            handler = None if value is None else str(value)
            continue
        topics[key_s] = str(value)
    return Inquiry(topics=topics, default=default, handler=handler)


def _parse_behaviors(raw: object, npc_key: object, scene_path: Path) -> Behaviors | None:
    """解析 behaviors 列表为 ``Behaviors`` 组件；缺省 / 空列表返回 None。"""
    if raw is None:
        return None
    if not isinstance(raw, (list, tuple)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 'behaviors' 应是列表，"
            f"实际是 {type(raw).__name__}"
        )
    entries: list[BehaviorSpec] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 behaviors[{index}] "
                f"应是映射，实际是 {type(entry).__name__}"
            )
        kind = str(entry.get("kind", ""))
        if not kind:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 behaviors[{index}] 缺少 'kind'"
            )
        # Chatter 字段：chat_msgs / chat_chance（spec D5 约定键名，不兼容旧别名）。
        msgs_raw = entry.get("chat_msgs", ())
        if not isinstance(msgs_raw, (list, tuple)):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 behaviors[{index}] "
                f"的消息列表应是列表，实际是 {type(msgs_raw).__name__}"
            )
        chance_raw = entry.get("chat_chance", 0.0)
        try:
            chance = float(chance_raw)
        except (TypeError, ValueError):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 behaviors[{index}] "
                f"的概率应是数字，实际是 {chance_raw!r}"
            ) from None
        when = entry.get("when")
        if when is not None and not isinstance(when, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 behaviors[{index}] "
                f"的 'when' 应是映射，实际是 {type(when).__name__}"
            )
        entries.append(
            BehaviorSpec(
                kind=kind,
                chat_msgs=tuple(str(m) for m in msgs_raw),
                chat_chance=chance,
                when=dict(when) if when is not None else None,
            )
        )
    if not entries:
        return None
    return Behaviors(entries=entries)


def _build_player(
    world: World,
    player: Mapping,
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> EntityId:
    """建玩家实体（Identity+Position+Container+PlayerSession）。玩家不挂 Description。"""
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


__all__ = ["SceneLoadError", "load_scene", "read_nature_config"]
