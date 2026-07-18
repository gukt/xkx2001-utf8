"""空场景数据构造：验证房间图连通、出口双向、玩家初始状态。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

from mud_engine.components import Exits, Identity, Position
from mud_engine.scenes import build_world


class TestBuildWorld:
    def test_returns_a_player_positioned_in_a_room_with_identity(self) -> None:
        world, player = build_world()
        room = world.require_component(player, Position).room
        assert world.has_component(room, Identity)

    def test_rooms_have_at_least_one_exit(self) -> None:
        world, player = build_world()
        start_room = world.require_component(player, Position).room
        start_exits = world.require_component(start_room, Exits)
        assert len(start_exits.by_direction) >= 1

    class WhenARoomHasAnExitInADirection:
        def test_the_target_room_has_a_matching_exit_in_the_opposite_direction(self) -> None:
            world, player = build_world()
            start_room = world.require_component(player, Position).room
            start_exits = world.require_component(start_room, Exits)
            assert "north" in start_exits.by_direction

            next_room = start_exits.by_direction["north"]
            next_exits = world.require_component(next_room, Exits)
            assert next_exits.by_direction.get("south") == start_room
