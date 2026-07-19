"""07 号票测试：事件总线 / 钩子注册表 + on_tick 上下文契约。

EventBus 是 ADR-0004"注册表注入"手法在非战斗系统的地基（``register(name, handler)``
与 ``commands.register`` 同构、与 ``register_condition`` 同源）。TickContext 是
on_tick 事件点分发给订阅者的上下文，形状被契约测试锁定（防 M2 引入真实规则时
改接口，spec 块 A user story 6）。

测试只验证外部可观察行为（handler 被调用、收到正确参数、注册顺序），不测
``_handlers`` 字典内部结构。按 Given/When 场景分组成嵌套类，方法名只写 Then
（见 engine/README.md「测试约定」）。
"""

from dataclasses import FrozenInstanceError

import pytest

from mud_engine.events import ON_TICK, EventBus, TickContext
from mud_engine.world import World


class TestEventBus:
    class WhenHandlerRegisteredForAnEvent:
        def test_dispatch_calls_the_handler(self) -> None:
            bus = EventBus()
            calls: list[tuple] = []
            bus.register("on_something", lambda *a: calls.append(a))
            bus.dispatch("on_something")
            assert len(calls) == 1

        def test_dispatch_passes_args_through_to_handler(self) -> None:
            bus = EventBus()
            received: list[tuple] = []
            bus.register("on_something", lambda *a, **kw: received.append((a, kw)))
            bus.dispatch("on_something", 1, 2, key="v")
            assert received == [((1, 2), {"key": "v"})]

        def test_register_uses_a_string_event_key_like_commands_register(self) -> None:
            # 与 commands.register 同构：按字符串 key 注册 handler 到注册表。
            # 任意字符串 key 都可（on_tick / on_command_before / on_enter_room …）。
            bus = EventBus()
            seen: list[str] = []
            bus.register("arbitrary_event_name", lambda: seen.append("hit"))
            bus.dispatch("arbitrary_event_name")
            assert seen == ["hit"]

    class WhenMultipleHandlersForSameEvent:
        def test_dispatch_calls_all_in_registration_order(self) -> None:
            bus = EventBus()
            order: list[str] = []
            bus.register("e", lambda: order.append("first"))
            bus.register("e", lambda: order.append("second"))
            bus.register("e", lambda: order.append("third"))
            bus.dispatch("e")
            assert order == ["first", "second", "third"]

        def test_does_not_short_circuit_so_rules_can_compose(self) -> None:
            # §12：多规则按 any/all 聚合不互斥，一个 handler 不阻断其他 handler。
            # 这里断言 dispatch 遍历全部 handler（不因第一个而短路）。
            bus = EventBus()
            count: list[int] = []
            bus.register("e", lambda: count.append(1))
            bus.register("e", lambda: count.append(1))
            bus.register("e", lambda: count.append(1))
            bus.dispatch("e")
            assert len(count) == 3

        def test_handler_registered_mid_dispatch_joins_next_dispatch_only(self) -> None:
            # dispatch 遍历开始那一刻的 handler 快照：遍历中新 register 的不参与本次，
            # 下次 dispatch 才包含（避免遍历中改列表导致跳过 / 重复 / 无限增长）。
            bus = EventBus()
            seen: list[str] = []

            def first() -> None:
                seen.append("first")
                bus.register("e", lambda: seen.append("late"))

            bus.register("e", first)
            bus.register("e", lambda: seen.append("second"))
            bus.dispatch("e")
            assert seen == ["first", "second"]  # "late" 未参与本次
            bus.dispatch("e")
            assert "late" in seen  # 第二次 dispatch 才包含 late

    class WhenNoHandlerRegistered:
        def test_dispatch_is_a_noop(self) -> None:
            bus = EventBus()
            bus.dispatch("nobody_home")  # 不抛、不分发

    class WhenHandlerRegisteredForDifferentEvent:
        def test_dispatch_does_not_call_unrelated_handler(self) -> None:
            bus = EventBus()
            calls: list[str] = []
            bus.register("on_a", lambda: calls.append("a"))
            bus.dispatch("on_b")
            assert calls == []


class TestTickContextContract:
    """on_tick 事件点签名形状的契约测试（spec 块 A user story 6）。

    锁定形状：frozen dataclass，含 ``tick: int`` + ``world: World``。未来加字段
    不破坏 ``handler(context)`` 签名，但改 / 删现有字段会被这些测试拦下。
    """

    def test_carries_the_tick_count(self) -> None:
        world = World()
        ctx = TickContext(tick=7, world=world)
        assert ctx.tick == 7

    def test_carries_a_reference_to_the_world(self) -> None:
        world = World()
        ctx = TickContext(tick=1, world=world)
        assert ctx.world is world

    def test_is_immutable(self) -> None:
        ctx = TickContext(tick=1, world=World())
        with pytest.raises(FrozenInstanceError):
            ctx.tick = 2  # type: ignore[misc]

    def test_on_tick_constant_is_a_stable_string_key(self) -> None:
        # 事件名常量锁定：注册与分发用同一个常量，避免拼写漂移。
        assert ON_TICK == "on_tick"
