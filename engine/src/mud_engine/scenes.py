"""M1 空场景数据：不含任何具体题材内容的最小房间图，仅用于验证引擎骨架。

场景数据（房间列表、出口映射、物品）与命令调度/ECS 存储代码分离--这是给未来
题材包"只提供数据、不触碰引擎实现"留的边界（M1 spec「场景数据与引擎能力的
边界」）。格式选型不在本票决定范围，先用最直接的内嵌数据结构跑通闭环
（06 号票会把场景数据迁移到 YAML）。
"""

from __future__ import annotations

from mud_engine.components import Container, Description, Exit, Exits, Identity, Position
from mud_engine.world import EntityId, World

OPPOSITE_DIRECTION = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}

# (房间键, 简述, 详细描述)
_ROOMS: tuple[tuple[str, str, str], ...] = (
    ("start_yard", "起始庭院", "一片空荡荡的庭院，只搭了最基本的骨架，等待后续题材内容填充。"),
    ("corridor", "长廊", "一条连接南北两侧的长廊，两侧墙壁空无一物。"),
    ("quiet_room", "静室", "一间安静的房间，位于长廊的尽头。"),
)

# (起点房间键, 方向, 终点房间键, 起点方向别名)；反方向出口按 OPPOSITE_DIRECTION
# 自动补上，但不继承别名（别名是起点方向专属的，如"北道"对反向 south 无意义）。
_CONNECTIONS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("start_yard", "north", "corridor", ("北道",)),
    ("corridor", "north", "quiet_room", ()),
)

# (物品键, 规范名, 别名, 简述, 详细描述)。物品是 Identity + Description 的实体，
# 由某个房间的 Container 持有；Description 挂上供未来 examine 命令展示，本票的
# take/drop/inventory/look 只用 Identity.name。
_ITEMS: tuple[tuple[str, str, tuple[str, ...], str, str], ...] = (
    ("stone", "石头", ("石",), "一块灰扑扑的石头", "一块毫不起眼的石头，沉甸甸的，表面粗糙。"),
)

# (物品键, 放置房间键)：物品初始放在哪个房间的地面 Container 里。
_PLACEMENTS: tuple[tuple[str, str], ...] = (("stone", "start_yard"),)


def build_world() -> tuple[World, EntityId]:
    """构造 M1 空场景 world，返回 (world, 玩家实体 id)。"""
    world = World()
    room_ids: dict[str, EntityId] = {}

    for key, short, long_desc in _ROOMS:
        room = world.create_entity()
        world.add_component(room, Identity(name=short))
        world.add_component(room, Description(short=short, long=long_desc))
        world.add_component(room, Exits())
        world.add_component(room, Container())
        room_ids[key] = room

    for from_key, direction, to_key, aliases in _CONNECTIONS:
        from_room, to_room = room_ids[from_key], room_ids[to_key]
        from_exits = world.require_component(from_room, Exits)
        to_exits = world.require_component(to_room, Exits)

        from_exits.by_direction[direction] = Exit(target=to_room, aliases=aliases)
        to_exits.by_direction[OPPOSITE_DIRECTION[direction]] = Exit(target=from_room)

    item_ids: dict[str, EntityId] = {}
    for key, name, aliases, short, long_desc in _ITEMS:
        item = world.create_entity()
        world.add_component(item, Identity(name=name, aliases=aliases))
        world.add_component(item, Description(short=short, long=long_desc))
        item_ids[key] = item

    for item_key, room_key in _PLACEMENTS:
        room = room_ids[room_key]
        container = world.require_component(room, Container)
        container.items.add(item_ids[item_key])

    player_id = world.create_entity()
    world.add_component(player_id, Identity(name="你"))
    world.add_component(player_id, Position(room=room_ids["start_yard"]))
    world.add_component(player_id, Container())

    return world, player_id
