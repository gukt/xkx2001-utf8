"""08 号票测试：命令生命周期钩子 before/after。

``execute`` 外包一层 ``on_command_before`` / ``on_command_after``（Inform 7 四段式
"前置校验 -> 执行 -> 后置通知"精炼，是"夜里 NPC 不卖酒""诅咒物品拿不起"等前置
否决规则的挂载点）。before 返回 ``Allow`` / ``Deny`` / ``Replace``（M1 默认
``Allow`` 放行）；after 修饰消息列表。钩子复用 07 号票的 ``world.events`` 注册表
（``register`` 与 ``commands.register`` 同构）；before 否决短路 / after 消息折叠
都不是 fire-and-forget，故走 ``handlers_for`` 自取 handler 列表自行聚合。

测试驱动 ``execute_line``（已确认的测试 seam），断言返回消息与可查询世界状态，
不测内部实现细节。按 Given/When 场景分组成嵌套类，方法名只写 Then（见
engine/README.md「测试约定」）。
"""

from dataclasses import FrozenInstanceError

import pytest

from mud_engine.commands import (
    ON_COMMAND_AFTER,
    ON_COMMAND_BEFORE,
    Allow,
    Deny,
    Replace,
)
from mud_engine.components import Container
from mud_engine.intent import Intent
from mud_engine.parsing import execute_line
from mud_engine.scenes import build_world


class TestCommandLifecycleContract:
    """命令生命周期钩子签名形状的契约测试（spec 块 A user story 6）。

    锁定形状：``ON_COMMAND_BEFORE``/``ON_COMMAND_AFTER`` 稳定字符串 key；
    ``Allow``/``Deny``/``Replace`` 为 frozen dataclass；``Deny`` 带 ``message``、
    ``Replace`` 带 ``intent``。未来加字段不破坏钩子签名，但改 / 删现有字段会被这些
    测试拦下（同 ``TestTickContextContract`` 思路）。
    """

    def test_on_command_before_constant_is_a_stable_string_key(self) -> None:
        # 事件名常量锁定：注册与执行处用同一个常量，避免拼写漂移。
        assert ON_COMMAND_BEFORE == "on_command_before"

    def test_on_command_after_constant_is_a_stable_string_key(self) -> None:
        assert ON_COMMAND_AFTER == "on_command_after"

    def test_allow_is_constructible_with_no_payload(self) -> None:
        assert isinstance(Allow(), Allow)

    def test_deny_carries_a_message(self) -> None:
        assert Deny("夜里不卖酒。").message == "夜里不卖酒。"

    def test_replace_carries_an_intent(self) -> None:
        intent = Intent(verb="look", target=None)
        assert Replace(intent).intent is intent

    def test_deny_is_immutable(self) -> None:
        with pytest.raises(FrozenInstanceError):
            Deny("x").message = "y"  # type: ignore[misc]

    def test_replace_is_immutable(self) -> None:
        with pytest.raises(FrozenInstanceError):
            Replace(Intent(verb="x", target=None)).intent = Intent(verb="y", target=None)  # type: ignore[misc]

    def test_allow_instances_are_equal(self) -> None:
        # 无载荷 frozen dataclass：两个 Allow() 相等，钩子 return Allow() 不分实例。
        assert Allow() == Allow()


class TestCommandBeforeHooks:
    class WhenNoHandlerRegistered:
        def test_command_runs_normally(self) -> None:
            # M1 默认无钩子即放行：现有命令行为零回归。acceptance"不注册任何 handler
            # 时现有 11 个命令行为完全不变"由 test_commands 全量覆盖，这里加一条显式。
            world, player_id = build_world()
            messages = execute_line(world, player_id, "look")
            assert any("起始庭院" in m for m in messages)

    class WhenADenyHandlerInterceptsACommand:
        def test_the_command_is_vetoed_with_the_deny_message(self) -> None:
            world, player_id = build_world()

            def deny_take(world, player, intent):
                if intent.verb == "get":
                    return Deny("夜里拿不动。")
                return Allow()

            world.events.register(ON_COMMAND_BEFORE, deny_take)
            messages = execute_line(world, player_id, "get 石头")
            assert messages == ["夜里拿不动。"]

        def test_the_vetoed_command_changes_no_world_state(self) -> None:
            world, player_id = build_world()

            def deny_take(world, player, intent):
                return Deny("拿不动。")

            world.events.register(ON_COMMAND_BEFORE, deny_take)
            execute_line(world, player_id, "get 石头")
            inventory = world.require_component(player_id, Container)
            assert not inventory.items  # 物品没被拿起

        def test_other_commands_still_run(self) -> None:
            # deny 钩子只否决 take，look 等其他命令不受影响。
            world, player_id = build_world()

            def deny_take_only(world, player, intent):
                if intent.verb == "get":
                    return Deny("夜里拿不动。")
                return Allow()

            world.events.register(ON_COMMAND_BEFORE, deny_take_only)
            messages = execute_line(world, player_id, "look")
            assert any("起始庭院" in m for m in messages)

    class WhenAReplaceHandlerRewritesTheIntent:
        def test_the_replaced_command_runs_instead(self) -> None:
            # 把 look 意图替换成 inventory：执行 look 实际跑的是 inventory。
            world, player_id = build_world()

            def redirect_to_inventory(world, player, intent):
                if intent.verb == "look":
                    return Replace(Intent(verb="inventory", target=None))
                return Allow()

            world.events.register(ON_COMMAND_BEFORE, redirect_to_inventory)
            messages = execute_line(world, player_id, "look")
            # 空物品栏提示"你什么都没带。"，不是房间的"起始庭院"。
            assert any("没" in m for m in messages)
            assert not any("起始庭院" in m for m in messages)

        def test_replace_to_an_unknown_verb_gives_the_unknown_hint(self) -> None:
            # Replace 改写到未注册动词：按生效意图给未知命令提示（不崩溃）。
            world, player_id = build_world()

            def redirect_to_unknown(world, player, intent):
                if intent.verb == "look":
                    return Replace(Intent(verb="fly", target=None))
                return Allow()

            world.events.register(ON_COMMAND_BEFORE, redirect_to_unknown)
            messages = execute_line(world, player_id, "look")
            assert any("未知命令" in m for m in messages)

    class WhenAReplaceIsFollowedByAnotherBeforeHandler:
        def test_subsequent_handlers_see_the_replaced_intent(self) -> None:
            # Replace 把 look 改成 inventory；第二个 before 钩子看到 inventory 并否决它。
            # 证明 before 钩子按注册顺序传递改写后的意图（Replace 链式生效）。
            world, player_id = build_world()

            def redirect(world, player, intent):
                if intent.verb == "look":
                    return Replace(Intent(verb="inventory", target=None))
                return Allow()

            def deny_inventory(world, player, intent):
                if intent.verb == "inventory":
                    return Deny("inventory 被否决。")
                return Allow()

            world.events.register(ON_COMMAND_BEFORE, redirect)
            world.events.register(ON_COMMAND_BEFORE, deny_inventory)
            messages = execute_line(world, player_id, "look")
            assert messages == ["inventory 被否决。"]

    class WhenMultipleDenyHandlersRegistered:
        def test_the_first_deny_wins_and_short_circuits(self) -> None:
            # 按注册顺序遍历，首个 Deny 即否决；其后的 Deny 钩子不跑（用副作用验证）。
            world, player_id = build_world()
            ran: list[str] = []

            def first_deny(world, player, intent):
                ran.append("first")
                return Deny("第一个否决。")

            def second_deny(world, player, intent):
                ran.append("second")
                return Deny("第二个否决。")

            world.events.register(ON_COMMAND_BEFORE, first_deny)
            world.events.register(ON_COMMAND_BEFORE, second_deny)
            messages = execute_line(world, player_id, "look")
            assert messages == ["第一个否决。"]
            assert ran == ["first"]  # short-circuit：第二个没跑

    class WhenABeforeHandlerReturnsNone:
        def test_none_is_tolerated_as_allow(self) -> None:
            # 容错：钩子忘写 return（None）视为 Allow，不崩溃。
            world, player_id = build_world()

            def forgets_to_return(world, player, intent):
                if intent.verb == "get":
                    return  # None
                return Allow()

            world.events.register(ON_COMMAND_BEFORE, forgets_to_return)
            messages = execute_line(world, player_id, "get 石头")
            assert any("拿" in m and "石头" in m for m in messages)  # 正常执行

    class WhenADenyTargetsAnUnknownVerb:
        def test_unknown_verb_message_is_unchanged(self) -> None:
            # 未知动词无处理函数，before/after 不挂（否决一个不存在的命令无意义）。
            world, player_id = build_world()

            def deny_all(world, player, intent):
                return Deny("不该到这。")

            world.events.register(ON_COMMAND_BEFORE, deny_all)
            messages = execute_line(world, player_id, "fly")
            assert any("未知命令" in m for m in messages)

    class WhenADenyFires:
        def test_after_hooks_do_not_run(self) -> None:
            # 否决时处理函数没跑，after 也不挂：after 钩子的修饰不作用于拒绝消息。
            world, player_id = build_world()
            after_ran: list[str] = []

            def deny(world, player, intent):
                return Deny("拒绝。")

            def after(world, player, intent, messages):
                after_ran.append("ran")
                return messages + ["<after>"]

            world.events.register(ON_COMMAND_BEFORE, deny)
            world.events.register(ON_COMMAND_AFTER, after)
            messages = execute_line(world, player_id, "look")
            assert messages == ["拒绝。"]
            assert after_ran == []


class TestCommandAfterHooks:
    class WhenAnAfterHandlerModifiesMessages:
        def test_the_modified_messages_are_returned(self) -> None:
            world, player_id = build_world()

            def append_line(world, player, intent, messages):
                return messages + ["<脚注>"]

            world.events.register(ON_COMMAND_AFTER, append_line)
            messages = execute_line(world, player_id, "look")
            assert messages[-1] == "<脚注>"
            assert any("起始庭院" in m for m in messages)  # 原消息仍在

    class WhenMultipleAfterHandlersRegistered:
        def test_they_chain_in_registration_order(self) -> None:
            # 前一个的输出是后一个的输入：先注册 A 再注册 B -> 顺序 A 在 B 前。
            world, player_id = build_world()

            def add_a(world, player, intent, messages):
                return messages + ["A"]

            def add_b(world, player, intent, messages):
                return messages + ["B"]

            world.events.register(ON_COMMAND_AFTER, add_a)
            world.events.register(ON_COMMAND_AFTER, add_b)
            messages = execute_line(world, player_id, "inventory")
            assert messages[-2:] == ["A", "B"]

    class WhenTheIntentWasReplaced:
        def test_after_sees_the_effective_replaced_intent(self) -> None:
            # before Replace 把 look 改成 inventory；after 收到的 intent.verb 应是 inventory。
            world, player_id = build_world()
            seen_verb: list[str] = []

            def redirect(world, player, intent):
                if intent.verb == "look":
                    return Replace(Intent(verb="inventory", target=None))
                return Allow()

            def observe(world, player, intent, messages):
                seen_verb.append(intent.verb)
                return messages

            world.events.register(ON_COMMAND_BEFORE, redirect)
            world.events.register(ON_COMMAND_AFTER, observe)
            execute_line(world, player_id, "look")
            assert seen_verb == ["inventory"]

    class WhenAnAfterHandlerReplacesTheWholeList:
        def test_the_replacement_becomes_the_result(self) -> None:
            world, player_id = build_world()

            def replace_all(world, player, intent, messages):
                return ["完全替换。"]

            world.events.register(ON_COMMAND_AFTER, replace_all)
            messages = execute_line(world, player_id, "look")
            assert messages == ["完全替换。"]


class TestHookIsolationBetweenWorlds:
    """钩子挂 ``world.events``（实例隔离，07 号票设计）：一个 world 注册的钩子不影响
    另一个 world。``build_world`` 每次新建 world，钩子天然不跨测试泄漏。"""

    def test_a_handler_registered_on_one_world_does_not_fire_on_another(self) -> None:
        world_a, player_a = build_world()
        world_b, player_b = build_world()

        def deny_always(world, player, intent):
            return Deny("a 拒绝。")

        world_a.events.register(ON_COMMAND_BEFORE, deny_always)
        # world_a 被否决
        assert execute_line(world_a, player_a, "look") == ["a 拒绝。"]
        # world_b 不受影响，正常 look
        assert any("起始庭院" in m for m in execute_line(world_b, player_b, "look"))
