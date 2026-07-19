"""05 号票测试：心跳循环（TickLoop）。

覆盖 05 验收 #1（tick 达到间隔触发存档）与 force_save 语义（quit 立即存档的
驱动点）。用 spy ``save_fn`` 记录触发，不依赖真实文件 IO。

按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md「测试约定」）。
"""

from collections.abc import Callable

from mud_engine.events import ON_TICK
from mud_engine.tick import DEFAULT_SAVE_INTERVAL, TickLoop
from mud_engine.world import World


def _spy() -> tuple[list[int], Callable[[], None]]:
    """返回 (calls 记录列表, 存档回调)；回调每被调一次就往 calls 追加 1。"""
    calls: list[int] = []

    def save() -> None:
        calls.append(1)

    return calls, save


class TestTickLoop:
    class WhenTickHasNotReachedTheInterval:
        def test_does_not_save(self) -> None:
            calls, save = _spy()
            loop = TickLoop(save, interval=3)
            loop.advance()
            loop.advance()
            assert calls == []
            assert loop.save_count == 0

    class WhenTickReachesTheInterval:
        def test_saves_once(self) -> None:
            calls, save = _spy()
            loop = TickLoop(save, interval=3)
            loop.advance()
            loop.advance()
            loop.advance()
            assert len(calls) == 1
            assert loop.save_count == 1

        def test_saves_again_each_period(self) -> None:
            calls, save = _spy()
            loop = TickLoop(save, interval=2)
            for _ in range(6):  # tick 1..6，预期在 tick 2/4/6 存档
                loop.advance()
            assert len(calls) == 3
            assert loop.save_count == 3

    class WhenForceSave:
        def test_saves_immediately_regardless_of_tick(self) -> None:
            calls, save = _spy()
            loop = TickLoop(save, interval=100)  # 远未到周期
            loop.force_save()
            assert len(calls) == 1
            assert loop.save_count == 1

        def test_does_not_advance_the_tick(self) -> None:
            calls, save = _spy()
            loop = TickLoop(save, interval=100)
            loop.force_save()
            assert loop.tick == 0
            assert len(calls) == 1

    class WhenUsingTheDefaultInterval:
        def test_saves_at_the_default_interval(self) -> None:
            calls, save = _spy()
            loop = TickLoop(save)  # 不传 interval，用默认
            for _ in range(DEFAULT_SAVE_INTERVAL - 1):
                loop.advance()
            assert calls == []
            loop.advance()  # 到达默认间隔 -> 存档
            assert len(calls) == 1


class TestOnTickDispatch:
    """07 号票：TickLoop.advance 把 on_tick 事件分发给所有订阅者。

    on_tick 是 ADR-0004"骨架固定 + 钩子策略注入"手法推广到非战斗系统的第一个
    事件点（块 A 地基）：未来 Nature 时辰推进 / NPC 行为 / Effect 衰减都挂这个
    统一驱动点。M1 存档继续走 save_fn（issue 验收 #4"或等价机制"），on_tick 在
    生产代码里暂无订阅者；这里用测试 handler 验证分发机制就位（验收 #3/#5）。
    """

    class WhenWorldProvided:
        def test_dispatches_on_tick_to_registered_handler(self) -> None:
            world = World()
            received: list = []
            world.events.register(ON_TICK, lambda ctx: received.append(ctx))
            loop = TickLoop(lambda: None, world=world, interval=100)
            loop.advance()
            assert len(received) == 1
            assert received[0].tick == 1
            assert received[0].world is world

        def test_dispatches_on_every_advance_with_increasing_tick(self) -> None:
            world = World()
            ticks: list[int] = []
            world.events.register(ON_TICK, lambda ctx: ticks.append(ctx.tick))
            loop = TickLoop(lambda: None, world=world, interval=100)
            loop.advance()
            loop.advance()
            loop.advance()
            assert ticks == [1, 2, 3]

        def test_dispatches_before_periodic_save_so_save_sees_latest_state(self) -> None:
            # on_tick 在周期存档之前分发：未来 Nature/NPC 订阅者推进的状态会被同 tick
            # 的周期存档捕获。这里用顺序断言锁定"on_tick 先于 save_fn"这一不变量。
            world = World()
            order: list[str] = []
            world.events.register(ON_TICK, lambda ctx: order.append("on_tick"))

            def save() -> None:
                order.append("save")

            loop = TickLoop(save, world=world, interval=1)  # 每 tick 都存
            loop.advance()
            assert order == ["on_tick", "save"]

    class WhenMultipleOnTickHandlers:
        def test_all_called_in_registration_order(self) -> None:
            world = World()
            order: list[str] = []
            world.events.register(ON_TICK, lambda ctx: order.append("a"))
            world.events.register(ON_TICK, lambda ctx: order.append("b"))
            loop = TickLoop(lambda: None, world=world, interval=100)
            loop.advance()
            assert order == ["a", "b"]

    class WhenNoWorldProvided:
        def test_advance_does_not_dispatch_on_tick(self) -> None:
            # 向后兼容：不传 world 时 advance 只做 save_fn 周期触发，不分发 on_tick
            # （保持 05 号票行为，零回归）。
            calls: list[int] = []
            loop = TickLoop(lambda: None, interval=100)  # 不传 world
            loop.advance()
            assert calls == []

        def test_force_save_does_not_dispatch_on_tick(self) -> None:
            # force_save 是退出前立即存档，不分发 on_tick（不应触发世界推进副作用）。
            world = World()
            calls: list[int] = []
            world.events.register(ON_TICK, lambda ctx: calls.append(ctx.tick))
            loop = TickLoop(lambda: None, world=world, interval=100)
            loop.force_save()
            assert calls == []
