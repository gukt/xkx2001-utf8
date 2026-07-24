"""09 号票测试：领域事件点（移动 / 物品 / 门）。

在移动 / 物品 / 门命令路径预留领域语义级事件点（空挂调用，M1 默认放行），复用
07 号票的 ``world.events`` 事件总线注册 handler。与 08 号票命令级 before/after 钩子
不同，这是领域语义级事件点：handler 收领域上下文（房间 / 物品 / 门状态），在
"移动 / 拿取 / 丢 / 门状态变化"这些领域事实发生时触发。可否决的 before 事件点
（``on_before_enter_room`` / ``on_get`` / ``on_drop``）复用 08 的 ``Allow``/``Deny``。

测试驱动 ``execute_line``（已确认的测试 seam）：注册计数器 / 记录参数的测试
handler，触发 go / take / drop / 门命令，断言 handler 被调用且收到正确参数；
注册 deny handler 拦截可否决事件点，断言操作被否决、状态不变。按 Given/When
场景分组成嵌套类，方法名只写 Then（见 engine/README.md「测试约定」）。

默认场景（m1_default_scene.yaml）布局：
- start_yard north -> corridor（无门可通行）；south -> storage_room（关门）。
- corridor north -> quiet_room（锁门，钥匙 iron_key 摆在 corridor 地面）。
- 石头摆在 start_yard 地面。
"""

from dataclasses import FrozenInstanceError

import pytest

from openmud.commands import (
    ON_BEFORE_ENTER_ROOM,
    ON_DOOR_STATE_CHANGE,
    ON_ENTER_ROOM,
    ON_LEAVE_ROOM,
    ON_TRAVERSE_BLOCKED,
    Allow,
    Deny,
    DoorStateChangeContext,
    EnterRoomContext,
    TraverseBlockedContext,
)
from openmud.components import (
    Container,
    DoorState,
    Exits,
    Identity,
    Position,
)
from openmud.parsing import execute_line
from openmud.scenes import build_world
from openmud.transfer import ON_DROP, ON_GET, TransferContext
from openmud.world import EntityId, World


def _player_room(world: World, player_id: EntityId) -> EntityId:
    return world.require_component(player_id, Position).room


def _player_room_name(world: World, player_id: EntityId) -> str:
    return world.require_component(_player_room(world, player_id), Identity).name


def _exit_target(world: World, player_id: EntityId, direction: str) -> EntityId:
    """当前房间某方向出口的目标房间 id（go 的 to_room）。"""
    room = _player_room(world, player_id)
    exits = world.require_component(room, Exits)
    return exits.by_direction[direction].target


def _stone_id(world: World, player_id: EntityId) -> EntityId:
    """start_yard 地面的石头 entity id（take 前从地面查；entity id 转移后不变）。"""
    room = _player_room(world, player_id)
    container = world.require_component(room, Container)
    for item in container.items:
        if world.require_component(item, Identity).name == "石头":
            return item
    raise AssertionError("场景里没找到石头")


class TestDomainEventPointConstants:
    """事件名常量是稳定字符串 key（spec 块 A user story 6：注册与触发处用同一
    常量，避免拼写漂移）。"""

    def test_on_before_enter_room_is_a_stable_string_key(self) -> None:
        assert ON_BEFORE_ENTER_ROOM == "on_before_enter_room"

    def test_on_enter_room_is_a_stable_string_key(self) -> None:
        assert ON_ENTER_ROOM == "on_enter_room"

    def test_on_leave_room_is_a_stable_string_key(self) -> None:
        assert ON_LEAVE_ROOM == "on_leave_room"

    def test_on_traverse_blocked_is_a_stable_string_key(self) -> None:
        assert ON_TRAVERSE_BLOCKED == "on_traverse_blocked"

    def test_on_get_is_a_stable_string_key(self) -> None:
        assert ON_GET == "on_get"

    def test_on_drop_is_a_stable_string_key(self) -> None:
        assert ON_DROP == "on_drop"

    def test_on_door_state_change_is_a_stable_string_key(self) -> None:
        assert ON_DOOR_STATE_CHANGE == "on_door_state_change"


class TestEnterRoomContextContract:
    """移动事件点上下文形状契约（spec 块 A user story 6）。frozen dataclass +
    player_id/from_room/to_room 三字段，未来加字段不破坏 ``handler(ctx)`` 签名。"""

    def test_carries_player_from_and_to_rooms(self) -> None:
        ctx = EnterRoomContext(player_id=1, from_room=2, to_room=3)
        assert ctx.player_id == 1
        assert ctx.from_room == 2
        assert ctx.to_room == 3

    def test_is_immutable(self) -> None:
        ctx = EnterRoomContext(player_id=1, from_room=2, to_room=3)
        with pytest.raises(FrozenInstanceError):
            ctx.to_room = 9  # type: ignore[misc]


class TestTraverseBlockedContextContract:
    def test_carries_player_room_direction_and_door_state(self) -> None:
        ctx = TraverseBlockedContext(
            player_id=1, from_room=2, direction="south", door_state=DoorState.CLOSED
        )
        assert ctx.player_id == 1
        assert ctx.from_room == 2
        assert ctx.direction == "south"
        assert ctx.door_state is DoorState.CLOSED

    def test_is_immutable(self) -> None:
        ctx = TraverseBlockedContext(
            player_id=1, from_room=2, direction="south", door_state=DoorState.CLOSED
        )
        with pytest.raises(FrozenInstanceError):
            ctx.door_state = DoorState.OPEN  # type: ignore[misc]


class TestTransferContextContract:
    def test_carries_player_item_src_and_dst(self) -> None:
        ctx = TransferContext(player_id=1, item=2, src=3, dst=1)
        assert ctx.player_id == 1
        assert ctx.item == 2
        assert ctx.src == 3
        assert ctx.dst == 1

    def test_is_immutable(self) -> None:
        ctx = TransferContext(player_id=1, item=2, src=3, dst=1)
        with pytest.raises(FrozenInstanceError):
            ctx.item = 9  # type: ignore[misc]


class TestDoorStateChangeContextContract:
    def test_carries_room_direction_old_and_new_state(self) -> None:
        ctx = DoorStateChangeContext(
            player_id=1,
            room=2,
            direction="south",
            old_state=DoorState.CLOSED,
            new_state=DoorState.OPEN,
        )
        assert ctx.room == 2
        assert ctx.direction == "south"
        assert ctx.old_state is DoorState.CLOSED
        assert ctx.new_state is DoorState.OPEN

    def test_is_immutable(self) -> None:
        ctx = DoorStateChangeContext(
            player_id=1,
            room=2,
            direction="south",
            old_state=DoorState.CLOSED,
            new_state=DoorState.OPEN,
        )
        with pytest.raises(FrozenInstanceError):
            ctx.new_state = DoorState.LOCKED  # type: ignore[misc]


class TestOnBeforeEnterRoom:
    """on_before_enter_room：移动前、可否决（"封城不能进"等规则挂载点）。"""

    class WhenNoHandlerRegistered:
        def test_go_moves_the_player_normally(self) -> None:
            world, player_id = build_world()
            start = _player_room(world, player_id)
            execute_line(world, player_id, "go north")
            assert _player_room(world, player_id) != start

    class WhenADenyHandlerVetoesEntry:
        def test_go_is_blocked_and_player_stays(self) -> None:
            world, player_id = build_world()
            start = _player_room(world, player_id)

            def deny_entry(ctx):
                return Deny("封城不能进。")

            world.events.register(ON_BEFORE_ENTER_ROOM, deny_entry)
            messages = execute_line(world, player_id, "go north")
            assert messages == ["封城不能进。"]
            assert _player_room(world, player_id) == start  # 没移动

        def test_deny_handler_receives_correct_rooms(self) -> None:
            world, player_id = build_world()
            start = _player_room(world, player_id)
            corridor = _exit_target(world, player_id, "north")
            seen: list[EnterRoomContext] = []

            def observe(ctx):
                seen.append(ctx)
                return Allow()

            world.events.register(ON_BEFORE_ENTER_ROOM, observe)
            execute_line(world, player_id, "go north")
            assert len(seen) == 1
            assert seen[0].player_id == player_id
            assert seen[0].from_room == start
            assert seen[0].to_room == corridor

        def test_vetoed_go_fires_no_enter_or_leave(self) -> None:
            # 否决则不触发 on_enter_room / on_leave_room（没移动）。
            world, player_id = build_world()
            fired: list[str] = []

            def deny(ctx):
                return Deny("封城。")

            def track_leave(ctx):
                fired.append("leave")

            def track_enter(ctx):
                fired.append("enter")

            world.events.register(ON_BEFORE_ENTER_ROOM, deny)
            world.events.register(ON_LEAVE_ROOM, track_leave)
            world.events.register(ON_ENTER_ROOM, track_enter)
            execute_line(world, player_id, "go north")
            assert fired == []

    class WhenMultipleDenyHandlersRegistered:
        def test_the_first_deny_wins_and_short_circuits(self) -> None:
            world, player_id = build_world()
            ran: list[str] = []

            def first(ctx):
                ran.append("first")
                return Deny("第一个。")

            def second(ctx):
                ran.append("second")
                return Deny("第二个。")

            world.events.register(ON_BEFORE_ENTER_ROOM, first)
            world.events.register(ON_BEFORE_ENTER_ROOM, second)
            messages = execute_line(world, player_id, "go north")
            assert messages == ["第一个。"]
            assert ran == ["first"]  # short-circuit：第二个没跑

    class WhenABeforeHandlerReturnsNone:
        def test_none_is_tolerated_as_allow(self) -> None:
            # 容错：钩子忘写 return（None）视为 Allow，不崩溃。
            world, player_id = build_world()
            start = _player_room(world, player_id)

            def forgets_return(ctx):
                return  # None

            world.events.register(ON_BEFORE_ENTER_ROOM, forgets_return)
            execute_line(world, player_id, "go north")
            assert _player_room(world, player_id) != start  # 正常移动

    class WhenABlockedDoorPreventsEntry:
        def test_on_before_enter_room_does_not_fire(self) -> None:
            # 门挡住时走 on_traverse_blocked 路径，on_before_enter_room 不触发：
            # 门都没过，谈不上"进房前校验"。
            world, player_id = build_world()
            fired: list[str] = []

            def observe(ctx):
                fired.append("before")

            world.events.register(ON_BEFORE_ENTER_ROOM, observe)
            execute_line(world, player_id, "go south")  # 关门
            assert fired == []


class TestOnEnterAndLeaveRoom:
    """on_enter_room / on_leave_room：移动后、fire-and-forget。"""

    class WhenThePlayerMoves:
        def test_both_fire_after_the_move_in_order(self) -> None:
            # leave 先于 enter（对应 LPC move 先离开旧环境再进入新）。
            world, player_id = build_world()
            fired: list[str] = []

            def track_leave(ctx):
                fired.append("leave")

            def track_enter(ctx):
                fired.append("enter")

            world.events.register(ON_LEAVE_ROOM, track_leave)
            world.events.register(ON_ENTER_ROOM, track_enter)
            execute_line(world, player_id, "go north")
            assert fired == ["leave", "enter"]

        def test_handlers_receive_correct_rooms(self) -> None:
            world, player_id = build_world()
            start = _player_room(world, player_id)
            corridor = _exit_target(world, player_id, "north")
            seen_leave: list[EnterRoomContext] = []
            seen_enter: list[EnterRoomContext] = []

            def rec_leave(ctx):
                seen_leave.append(ctx)

            def rec_enter(ctx):
                seen_enter.append(ctx)

            world.events.register(ON_LEAVE_ROOM, rec_leave)
            world.events.register(ON_ENTER_ROOM, rec_enter)
            execute_line(world, player_id, "go north")
            for ctx in seen_leave + seen_enter:
                assert ctx.player_id == player_id
                assert ctx.from_room == start
                assert ctx.to_room == corridor

        def test_player_is_already_in_to_room_when_handlers_fire(self) -> None:
            # enter/leave 在移动后触发：handler 跑时玩家位置已更新到 to_room。
            world, player_id = build_world()
            corridor = _exit_target(world, player_id, "north")
            current_at_enter: list[EntityId] = []

            def record_room(ctx):
                current_at_enter.append(_player_room(world, player_id))

            world.events.register(ON_ENTER_ROOM, record_room)
            execute_line(world, player_id, "go north")
            assert current_at_enter == [corridor]


class TestOnTraverseBlocked:
    """on_traverse_blocked：出口存在但被门挡住时（go 走不通）。"""

    class WhenAClosedDoorBlocksMovement:
        def test_fires_with_closed_door_state(self) -> None:
            world, player_id = build_world()
            seen: list[TraverseBlockedContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_TRAVERSE_BLOCKED, observe)
            execute_line(world, player_id, "go south")
            assert len(seen) == 1
            assert seen[0].direction == "south"
            assert seen[0].door_state is DoorState.CLOSED

    class WhenALockedDoorBlocksMovement:
        def test_fires_with_locked_door_state(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "go north")  # 到 corridor
            seen: list[TraverseBlockedContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_TRAVERSE_BLOCKED, observe)
            execute_line(world, player_id, "go north")  # 锁门
            assert len(seen) == 1
            assert seen[0].door_state is DoorState.LOCKED

    class WhenTheExitDoesNotExist:
        def test_does_not_fire(self) -> None:
            # 出口不存在（无门无出口）是输入无效，不是领域阻塞，不触发。
            world, player_id = build_world()
            fired: list[str] = []

            def observe(ctx):
                fired.append("blocked")

            world.events.register(ON_TRAVERSE_BLOCKED, observe)
            execute_line(world, player_id, "go east")  # start_yard 无 east 出口
            assert fired == []

    class WhenTheExitHasNoDoor:
        def test_does_not_fire(self) -> None:
            # 无门出口可通行，不触发 on_traverse_blocked。
            world, player_id = build_world()
            fired: list[str] = []

            def observe(ctx):
                fired.append("blocked")

            world.events.register(ON_TRAVERSE_BLOCKED, observe)
            execute_line(world, player_id, "go north")  # 无门通行
            assert fired == []


class TestOnTake:
    """on_get：拿物品前、可否决（"诅咒物品拿不起""任务物品不能拿"挂载点）。"""

    class WhenNoHandlerRegistered:
        def test_take_works_normally(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")
            inv = world.require_component(player_id, Container)
            assert any(world.require_component(i, Identity).name == "石头" for i in inv.items)

    class WhenADenyHandlerVetoesTake:
        def test_the_item_is_not_taken(self) -> None:
            world, player_id = build_world()
            room = _player_room(world, player_id)

            def deny(ctx):
                return Deny("诅咒物品拿不起。")

            world.events.register(ON_GET, deny)
            messages = execute_line(world, player_id, "get 石头")
            assert messages == ["诅咒物品拿不起。"]
            # 物品仍在房间地面
            floor = world.require_component(room, Container)
            assert any(world.require_component(i, Identity).name == "石头" for i in floor.items)
            # 物品栏空
            assert not world.require_component(player_id, Container).items

        def test_deny_handler_receives_correct_transfer_context(self) -> None:
            world, player_id = build_world()
            room = _player_room(world, player_id)
            stone = _stone_id(world, player_id)
            seen: list[TransferContext] = []

            def observe(ctx):
                seen.append(ctx)
                return Allow()

            world.events.register(ON_GET, observe)
            execute_line(world, player_id, "get 石头")
            assert len(seen) == 1
            assert seen[0].player_id == player_id
            assert seen[0].item == stone
            assert seen[0].src == room  # take: src=房间
            assert seen[0].dst == player_id  # take: dst=玩家


class TestOnDrop:
    """on_drop：丢物品前、可否决（"任务物品不能丢"挂载点，no_drop 自定义提示）。"""

    class WhenADenyHandlerVetoesDrop:
        def test_the_item_is_not_dropped(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "get 石头")  # 先拿起

            def deny(ctx):
                return Deny("任务物品不能丢弃。")

            world.events.register(ON_DROP, deny)
            messages = execute_line(world, player_id, "drop 石头")
            assert messages == ["任务物品不能丢弃。"]
            # 物品仍在物品栏
            assert any(
                world.require_component(i, Identity).name == "石头"
                for i in world.require_component(player_id, Container).items
            )

        def test_deny_handler_receives_correct_transfer_context(self) -> None:
            world, player_id = build_world()
            room = _player_room(world, player_id)
            stone = _stone_id(world, player_id)  # take 前查（entity id 转移后不变）
            seen: list[TransferContext] = []

            def observe(ctx):
                seen.append(ctx)
                return Allow()

            world.events.register(ON_DROP, observe)
            execute_line(world, player_id, "get 石头")  # 先拿起
            execute_line(world, player_id, "drop 石头")
            assert len(seen) == 1
            assert seen[0].player_id == player_id
            assert seen[0].item == stone
            assert seen[0].src == player_id  # drop: src=玩家
            assert seen[0].dst == room  # drop: dst=房间


class TestOnDoorStateChange:
    """on_door_state_change：门状态实际变化时（open/close/unlock 改 state 处）。
    knock 不改状态不触发；无变化路径（open 已开 / close 已关 / unlock 未锁）不触发。"""

    class WhenOpeningAClosedDoor:
        def test_fires_with_closed_to_open(self) -> None:
            world, player_id = build_world()
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "open south")
            assert len(seen) == 1
            assert seen[0].direction == "south"
            assert seen[0].old_state is DoorState.CLOSED
            assert seen[0].new_state is DoorState.OPEN

        def test_context_carries_player_and_room(self) -> None:
            world, player_id = build_world()
            room = _player_room(world, player_id)
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "open south")
            assert seen[0].player_id == player_id
            assert seen[0].room == room

    class WhenClosingAnOpenDoor:
        def test_fires_with_open_to_closed(self) -> None:
            world, player_id = build_world()
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "open south")  # CLOSED -> OPEN
            execute_line(world, player_id, "close south")  # OPEN -> CLOSED
            assert len(seen) == 2
            assert seen[0].old_state is DoorState.CLOSED
            assert seen[0].new_state is DoorState.OPEN
            assert seen[1].old_state is DoorState.OPEN
            assert seen[1].new_state is DoorState.CLOSED

    class WhenUnlockingALockedDoor:
        def test_fires_with_locked_to_closed(self) -> None:
            world, player_id = build_world()
            execute_line(world, player_id, "go north")  # corridor
            execute_line(world, player_id, "get 钥匙")
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "unlock north")
            assert len(seen) == 1
            assert seen[0].direction == "north"
            assert seen[0].old_state is DoorState.LOCKED
            assert seen[0].new_state is DoorState.CLOSED

    class WhenKnockingOnADoor:
        def test_does_not_fire(self) -> None:
            # knock 不改门状态。
            world, player_id = build_world()
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "knock south")
            assert seen == []

    class WhenOpeningAnAlreadyOpenDoor:
        def test_does_not_fire(self) -> None:
            # 已开着再 open，无状态变化。
            world, player_id = build_world()
            execute_line(world, player_id, "open south")  # 先开
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "open south")  # 再开（已开）
            assert seen == []

    class WhenClosingAnAlreadyClosedDoor:
        def test_does_not_fire(self) -> None:
            world, player_id = build_world()
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "close south")  # 已关
            assert seen == []

    class WhenUnlockingAnUnlockedDoor:
        def test_does_not_fire(self) -> None:
            # south 门是 closed（非 locked），unlock 提示没上锁、不改状态。
            world, player_id = build_world()
            seen: list[DoorStateChangeContext] = []

            def observe(ctx):
                seen.append(ctx)

            world.events.register(ON_DOOR_STATE_CHANGE, observe)
            execute_line(world, player_id, "unlock south")
            assert seen == []


class TestNoHandlerDefaultBehavior:
    """不注册任何 handler 时，现有命令行为不变（acceptance 第 6 条）。

    事件点空挂：``dispatch`` 遍历空 handler 列表是 no-op，``_run_vetoable`` 返回
    None 放行，故 go/take/drop/门命令的消息与状态变更与 09 号票前完全一致。
    """

    def test_go_through_an_open_exit_moves_the_player(self) -> None:
        world, player_id = build_world()
        start = _player_room(world, player_id)
        execute_line(world, player_id, "go north")
        assert _player_room(world, player_id) != start

    def test_blocked_go_still_returns_the_door_message(self) -> None:
        world, player_id = build_world()
        messages = execute_line(world, player_id, "go south")
        assert any("关" in m for m in messages)

    def test_take_and_drop_round_trip_works(self) -> None:
        world, player_id = build_world()
        execute_line(world, player_id, "get 石头")
        execute_line(world, player_id, "drop 石头")
        room = _player_room(world, player_id)
        assert any(
            world.require_component(i, Identity).name == "石头"
            for i in world.require_component(room, Container).items
        )

    def test_open_then_go_through_works(self) -> None:
        world, player_id = build_world()
        execute_line(world, player_id, "open south")
        execute_line(world, player_id, "go south")
        assert _player_room_name(world, player_id) == "储藏室"


class TestDomainEventIsolationBetweenWorlds:
    """领域事件点挂 world.events（实例隔离，07 号票设计）：一个 world 注册的
    handler 不影响另一个 world。``build_world`` 每次新建 world，handler 天然不跨
    测试泄漏。"""

    def test_a_handler_registered_on_one_world_does_not_fire_on_another(self) -> None:
        world_a, player_a = build_world()
        world_b, player_b = build_world()

        def deny_entry(ctx):
            return Deny("a 拒绝。")

        world_a.events.register(ON_BEFORE_ENTER_ROOM, deny_entry)
        # world_a 被否决，没移动
        start_a = _player_room(world_a, player_a)
        assert execute_line(world_a, player_a, "go north") == ["a 拒绝。"]
        assert _player_room(world_a, player_a) == start_a
        # world_b 不受影响，正常移动
        start_b = _player_room(world_b, player_b)
        execute_line(world_b, player_b, "go north")
        assert _player_room(world_b, player_b) != start_b
