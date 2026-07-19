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

from mud_engine.components import (
    Container,
    Description,
    Door,
    Doors,
    DoorState,
    Exit,
    Exits,
    Identity,
    Position,
)
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
    room_ids = _build_rooms(world, rooms, scene_path)
    item_ids = _build_items(world, items, room_ids, scene_path)
    _build_exits(world, rooms, room_ids, item_ids, scene_path)
    _build_npcs(world, npcs, room_ids, scene_path)
    player_id = _build_player(world, player, room_ids, scene_path)
    _capture_top_level_unknown_sections(world, data)
    return world, player_id


# 引擎认识的顶层段与每类实体的字段：不在这些集合里的段/字段是"未识别"的，
# 原样透传到扩展数据容器留着不丢，M1 不解析不执行（11 号票）。透传不是设计、
# 只是不丢弃，故不违反"M1 不预支 M3 设计"--M3 引入规则引擎时旧场景数据不必重写。
_TOP_LEVEL_KNOWN_SECTIONS = frozenset({"rooms", "items", "npcs", "player"})
_ROOM_KNOWN_FIELDS = frozenset({"name", "aliases", "short", "long", "exits"})
_ITEM_KNOWN_FIELDS = frozenset({"name", "aliases", "short", "long", "placed_in"})
_NPC_KNOWN_FIELDS = frozenset({"name", "aliases", "short", "long", "in_room"})
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
            world, room, data, label=f"房间 '{room_key}'", scene_path=scene_path
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
    """建物品实体（Identity+Description）并放进 placed_in 房间的地面容器。

    返回 item key -> entity id 映射，供出口的 ``door.key`` 引用钥匙物品（04 号票）。
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
        container = world.require_component(room_ids[str(placed_in)], Container)
        container.items.add(item)
        _capture_entity_unknown_fields(world, item, data, _ITEM_KNOWN_FIELDS)
        item_ids[str(item_key)] = item
    return item_ids


def _build_npcs(
    world: World,
    npcs: Mapping,
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> None:
    """建静态展示型 NPC（Identity+Description+Position），无任何行为组件。"""
    for npc_key, raw in npcs.items():
        data = _as_mapping(raw, label=f"NPC '{npc_key}'", scene_path=scene_path)
        in_room = data.get("in_room")
        if not in_room:
            raise SceneLoadError(f"场景文件 {scene_path} 的 NPC '{npc_key}' 缺少 'in_room'")
        if str(in_room) not in room_ids:
            raise SceneLoadError(
                f"场景文件 {scene_path} 的 NPC '{npc_key}' 的 in_room '{in_room}' 不是已定义的房间"
            )
        npc = world.create_entity()
        _attach_identity_and_description(
            world, npc, data, label=f"NPC '{npc_key}'", scene_path=scene_path
        )
        world.add_component(npc, Position(room=room_ids[str(in_room)]))
        _capture_entity_unknown_fields(world, npc, data, _NPC_KNOWN_FIELDS)


def _build_player(
    world: World,
    player: Mapping,
    room_ids: dict[str, EntityId],
    scene_path: Path,
) -> EntityId:
    """建玩家实体（Identity+Position+Container）。玩家不挂 Description。"""
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
    _capture_entity_unknown_fields(world, player_id, player, _PLAYER_KNOWN_FIELDS)
    return player_id


def _attach_identity_and_description(
    world: World,
    entity: EntityId,
    data: Mapping,
    *,
    label: str,
    scene_path: Path,
) -> None:
    """给实体挂 Identity + Description：name 必需、short 缺省取 name、long 缺省空。

    房间/物品/NPC 共用这一份"名字+描述"装配（玩家除外，玩家不挂 Description）。
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
        Description(short=str(data.get("short", name)), long=str(data.get("long", ""))),
    )


__all__ = ["SceneLoadError", "load_scene"]
