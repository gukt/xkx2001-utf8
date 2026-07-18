"""M1 空场景数据：不含任何具体题材内容的最小房间图，仅用于验证引擎骨架。

场景数据（房间列表、出口映射）与命令调度/ECS 存储代码分离——这是给未来题材包
"只提供数据、不触碰引擎实现"留的边界（M1 spec「场景数据与引擎能力的边界」）。
格式选型不在本票决定范围，先用最直接的内嵌数据结构跑通闭环。
"""

from __future__ import annotations

from mud_engine.components import Description, Exits, Identity, Position
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

# (起点房间键, 方向, 终点房间键)；反方向出口按 OPPOSITE_DIRECTION 自动补上。
_CONNECTIONS: tuple[tuple[str, str, str], ...] = (
    ("start_yard", "north", "corridor"),
    ("corridor", "north", "quiet_room"),
)


def build_world() -> tuple[World, EntityId]:
    """构造 M1 空场景 world，返回 (world, 玩家实体 id)。"""
    world = World()
    room_ids: dict[str, EntityId] = {}

    for key, short, long_desc in _ROOMS:
        room = world.create_entity()
        world.add_component(room, Identity(name=short))
        world.add_component(room, Description(short=short, long=long_desc))
        world.add_component(room, Exits())
        room_ids[key] = room

    for from_key, direction, to_key in _CONNECTIONS:
        from_room, to_room = room_ids[from_key], room_ids[to_key]
        from_exits = world.require_component(from_room, Exits)
        to_exits = world.require_component(to_room, Exits)

        from_exits.by_direction[direction] = to_room
        to_exits.by_direction[OPPOSITE_DIRECTION[direction]] = from_room

    player = world.create_entity()
    world.add_component(player, Identity(name="你"))
    world.add_component(player, Position(room=room_ids["start_yard"]))

    return world, player
