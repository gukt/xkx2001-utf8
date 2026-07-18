"""空场景数据构造：验证房间图连通、出口双向、玩家初始状态。

测试按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md
「测试约定」）。
"""

from mud_engine.components import Container, Description, Exits, Identity, Position
from mud_engine.scenes import build_world


class TestBuildWorld:
    def test_returns_a_player_positioned_in_a_room_with_identity(self) -> None:
        world, player_id = build_world()
        room = world.require_component(player_id, Position).room
        assert world.has_component(room, Identity)

    def test_rooms_have_at_least_one_exit(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        start_exits = world.require_component(start_room, Exits)
        assert len(start_exits.by_direction) >= 1

    class WhenARoomHasAnExitInADirection:
        def test_the_target_room_has_a_matching_exit_in_the_opposite_direction(self) -> None:
            world, player_id = build_world()
            start_room = world.require_component(player_id, Position).room
            start_exits = world.require_component(start_room, Exits)
            assert "north" in start_exits.by_direction

            next_room = start_exits.by_direction["north"].target
            next_exits = world.require_component(next_room, Exits)
            assert next_exits.by_direction["south"].target == start_room

    def test_start_yard_floor_has_a_preset_item(self) -> None:
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        floor = world.require_component(start_room, Container)
        assert len(floor.items) == 1
        item = next(iter(floor.items))
        assert world.require_component(item, Identity).name == "石头"

    def test_player_starts_with_an_empty_inventory(self) -> None:
        world, player_id = build_world()
        assert not world.require_component(player_id, Container).items

    def test_item_has_a_description_component(self) -> None:
        # 物品展示文本复用 01 号票的 Description 组件形状（03 号票 spec 要求）。
        world, player_id = build_world()
        start_room = world.require_component(player_id, Position).room
        floor = world.require_component(start_room, Container)
        item = next(iter(floor.items))
        assert world.has_component(item, Description)
