"""05 号票测试：心跳循环（TickLoop）。

覆盖 05 验收 #1（tick 达到间隔触发存档）与 force_save 语义（quit 立即存档的
驱动点）。用 spy ``save_fn`` 记录触发，不依赖真实文件 IO。

按 Given/When 场景分组成嵌套类，方法名只写 Then（见 engine/README.md「测试约定」）。
"""

from collections.abc import Callable

from mud_engine.tick import DEFAULT_SAVE_INTERVAL, TickLoop


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
