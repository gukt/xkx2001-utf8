"""04 号票测试：门（开/关/锁）与动态出口。

覆盖 04 号票 acceptance：
- 关门出口：go 被拒、open 后通行、close 后再拒、look 标注门状态。
- 锁门出口：没钥匙 unlock 失败、持钥匙 unlock 成功（变关）、需再 open 才通行。
- knock 对关/锁/开门有反馈、不改状态。
- 动态出口：运行时增删 ``Exits.by_direction``，look/go 立即反映。
- 门状态是独立于 ``Exits`` 的 ``Doors`` 组件（``Exit`` 不含 state/key 字段）。
- 门命令方向匹配复用 02 号票的 ``match_target``（别名 + 无匹配失败路径）。

默认场景（m1_default_scene.yaml）的门布局：
- start_yard south -> storage_room：关门（open/close/go 闭环）。
- corridor north -> quiet_room：锁门，钥匙 iron_key 摆在 corridor 地面。

按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md「测试约定」）。
"""

from mud_engine.components import (
    Door,
    Doors,
    DoorState,
    Exit,
    Exits,
    Identity,
    Position,
)
from mud_engine.parsing import execute_line
from mud_engine.scenes import build_world
from mud_engine.world import EntityId, World


def _player_room(world: World, player_id: EntityId) -> EntityId:
    return world.require_component(player_id, Position).room


def _player_room_name(world: World, player_id: EntityId) -> str:
    return world.require_component(_player_room(world, player_id), Identity).name


def _door_at(world: World, room: EntityId, direction: str) -> Door | None:
    doors = world.get_component(room, Doors)
    if doors is None:
        return None
    return doors.by_direction.get(direction)


def _goto_corridor(world: World, player_id: EntityId) -> None:
    """start_yard north -> corridor（无门），供锁门测试到达 corridor。"""
    execute_line(world, player_id, "go north")


class TestClosedDoor:
    class WhenTheDoorIsClosed:
        def test_go_is_rejected_mentioning_the_door(self) -> None:
            world, player_id = build_world()
            before = _player_room(world, player_id)
            messages = execute_line(world, player_id, "go south")
            assert _player_room(world, player_id) == before
            assert any("关" in m for m in messages)

        def test_look_annotates_the_door_as_closed(self) -> None:
            world, player_id = build_world()
            combined = " ".join(execute_line(world, player_id, "look"))
            assert "南(south)（关）" in combined

    class WhenTheDoorHasBeenOpened:
        def test_open_then_go_moves_the_player_through(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "open south")
            execute_line(world, player_id, "go south")
            assert _player_room_name(world, player_id) == "储藏室"

        def test_open_reports_success(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "open south")
            assert any("打开" in m for m in messages)

        def test_close_blocks_go_again(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "open south")
            execute_line(world, player_id, "close south")
            before = _player_room(world, player_id)
            messages = execute_line(world, player_id, "go south")
            assert _player_room(world, player_id) == before
            assert any("关" in m for m in messages)

        def test_opening_an_already_open_door_is_a_no_op(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "open south")
            messages = execute_line(world, player_id, "open south")
            assert any("已经开着" in m for m in messages)

        def test_closing_an_already_closed_door_is_a_no_op(self) -> None:
            world, player_id = build_world()
            messages = execute_line(world, player_id, "close south")
            assert any("已经关着" in m for m in messages)


class TestLockedDoor:
    class WhenThePlayerHasNoKey:
        def test_unlock_fails_mentioning_a_key(self) -> None:
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            messages = execute_line(world, player_id, "unlock north")
            assert any("钥匙" in m for m in messages)
            room = _player_room(world, player_id)
            assert _door_at(world, room, "north").state is DoorState.LOCKED

        def test_go_is_rejected_mentioning_the_lock(self) -> None:
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            before = _player_room(world, player_id)
            messages = execute_line(world, player_id, "go north")
            assert _player_room(world, player_id) == before
            assert any("锁" in m for m in messages)

        def test_open_a_locked_door_tells_you_to_unlock_first(self) -> None:
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            messages = execute_line(world, player_id, "open north")
            assert any("锁" in m for m in messages)

    class WhenThePlayerHoldsTheKey:
        def test_take_the_key_then_unlock_succeeds(self) -> None:
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            execute_line(world, player_id, "get 钥匙")
            messages = execute_line(world, player_id, "unlock north")
            assert any("解锁" in m for m in messages)
            room = _player_room(world, player_id)
            assert _door_at(world, room, "north").state is DoorState.CLOSED

        def test_go_still_blocked_until_opened_after_unlock(self) -> None:
            # unlock 后门变关，go 仍被拒，需再 open。
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            execute_line(world, player_id, "get 钥匙")
            execute_line(world, player_id, "unlock north")
            before = _player_room(world, player_id)
            messages = execute_line(world, player_id, "go north")
            assert _player_room(world, player_id) == before
            assert any("关" in m for m in messages)

        def test_unlock_then_open_then_go_reaches_the_room(self) -> None:
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            execute_line(world, player_id, "get 钥匙")
            execute_line(world, player_id, "unlock north")
            execute_line(world, player_id, "open north")
            execute_line(world, player_id, "go north")
            assert _player_room_name(world, player_id) == "静室"

        def test_unlock_again_says_not_locked(self) -> None:
            # 钥匙不被 unlock 消耗；再 unlock 提示没上锁。
            world, player_id = build_world()
            _goto_corridor(world, player_id)
            execute_line(world, player_id, "get 钥匙")
            execute_line(world, player_id, "unlock north")
            messages = execute_line(world, player_id, "unlock north")
            assert any("没上锁" in m for m in messages)
            assert "钥匙" in " ".join(execute_line(world, player_id, "inventory"))


class TestKnock:
    def test_knock_on_a_closed_door_gives_feedback(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "knock south")
        assert messages
        assert any("敲" in m for m in messages)

    def test_knock_on_a_locked_door_gives_feedback(self) -> None:
        world, player_id = build_world()
        _goto_corridor(world, player_id)
        messages = execute_line(world, player_id, "knock north")
        assert messages
        assert any("敲" in m for m in messages)

    def test_knock_does_not_change_door_state(self) -> None:
        world, player_id = build_world()
        execute_line(world, player_id, "knock south")
        room = _player_room(world, player_id)
        assert _door_at(world, room, "south").state is DoorState.CLOSED

    def test_knock_on_an_open_door_does_not_crash(self) -> None:
        world, player_id = build_world()
        execute_line(world, player_id, "open south")
        messages = execute_line(world, player_id, "knock south")
        assert messages

    def test_knock_a_direction_without_a_door_says_so(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "knock north")
        assert any("没有门" in m for m in messages)


class TestDoorCommandsOnMissingDoor:
    def test_open_a_direction_without_a_door_says_so(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "open north")
        assert any("没有门" in m for m in messages)

    def test_close_a_direction_without_a_door_says_so(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "close north")
        assert any("没有门" in m for m in messages)

    def test_unlock_a_direction_without_a_door_says_so(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "unlock north")
        assert any("没有门" in m for m in messages)


class TestDoorCommandsReuseAliasMatching:
    """门命令方向匹配复用 02 号票的 match_target（acceptance 第 8 条）。"""

    def test_open_by_direction_alias(self) -> None:
        world, player_id = build_world()
        room = _player_room(world, player_id)
        exits = world.require_component(room, Exits)
        south_target = exits.by_direction["south"].target
        # 给 south 出口临时加别名"侧门"（只改 Exits，不动 Doors 的门状态）。
        exits.by_direction["south"] = Exit(target=south_target, aliases=("侧门",))
        messages = execute_line(world, player_id, "open 侧门")
        assert any("打开" in m for m in messages)
        assert _door_at(world, room, "south").state is DoorState.OPEN

    def test_door_command_on_unknown_direction_is_no_target_match(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "open up")
        assert any("没有出口" in m for m in messages)

    def test_missing_direction_argument_returns_a_usage_hint(self) -> None:
        world, player_id = build_world()
        for verb in ("open", "close", "knock", "unlock"):
            messages = execute_line(world, player_id, verb)
            assert messages
            assert verb in messages[0] or "什么" in messages[0]


class TestDynamicExits:
    """运行时增删出口表，look/go 立即反映（acceptance 第 6 条）。"""

    def test_added_exit_is_visible_in_look_and_passable(self) -> None:
        world, player_id = build_world()
        room = _player_room(world, player_id)
        exits = world.require_component(room, Exits)
        corridor = exits.by_direction["north"].target
        exits.by_direction["up"] = Exit(target=corridor)
        combined = " ".join(execute_line(world, player_id, "look"))
        assert "up" in combined
        execute_line(world, player_id, "go up")
        assert _player_room_name(world, player_id) == "长廊"

    def test_removed_exit_disappears_from_look_and_blocks_go(self) -> None:
        world, player_id = build_world()
        room = _player_room(world, player_id)
        exits = world.require_component(room, Exits)
        exits.by_direction.pop("north")
        combined = " ".join(execute_line(world, player_id, "look"))
        assert "north" not in combined
        before = _player_room(world, player_id)
        messages = execute_line(world, player_id, "go north")
        assert _player_room(world, player_id) == before
        assert any("没有出口" in m for m in messages)


class TestDoorStateIsIndependentOfExits:
    """可开合/上锁状态是独立于 Exits 的 Doors 组件（acceptance 第 7 条）。"""

    def test_door_state_lives_in_a_separate_doors_component(self) -> None:
        world, player_id = build_world()
        room = _player_room(world, player_id)
        assert world.has_component(room, Doors)
        doors = world.require_component(room, Doors)
        assert doors.by_direction["south"].state is DoorState.CLOSED
        assert doors.by_direction["south"].key_item_id is None

    def test_exit_does_not_carry_door_state(self) -> None:
        # Exit 只有 target/aliases，门状态不挂在它身上。
        world, player_id = build_world()
        room = _player_room(world, player_id)
        exits = world.require_component(room, Exits)
        south_exit = exits.by_direction["south"]
        assert not hasattr(south_exit, "state")
        assert not hasattr(south_exit, "key_item_id")

    def test_room_without_doors_has_no_doors_component(self) -> None:
        world, player_id = build_world()
        room = _player_room(world, player_id)
        corridor = world.require_component(room, Exits).by_direction["north"].target
        quiet_room = world.require_component(corridor, Exits).by_direction["north"].target
        assert not world.has_component(quiet_room, Doors)


class TestHelpListsDoorCommands:
    def test_help_lists_open_close_knock_unlock(self) -> None:
        world, player_id = build_world()
        combined = " ".join(execute_line(world, player_id, "help"))
        for verb in ("open", "close", "knock", "unlock"):
            assert verb in combined
