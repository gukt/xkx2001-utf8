"""心跳循环（tick loop）：随时间推进的系统的统一驱动点（05 号票）。

M1 阶段只承载一件事：达到设定的 tick 间隔时触发一次存档。心跳推进时机由 CLI
决定（每条命令后推进一次），保证普通游玩稳定触发若干次周期性存档。未来战斗
回合结算、生命自然恢复、NPC 行为决策直接挂载到这个循环上，不需另起驱动机制
（spec 用户故事 18）。

与命令路径的职责边界（spec 用户故事 17）：命令处理函数只响应玩家一次性输入
触发的状态变更，不承担"世界随时间自然演化"的职责；本循环是"随时间推进"那条
路径的统一入口，两条路径不交叉触发同一状态。``quit`` 等退出只设 ``should_quit``，
存档时机由本循环（周期）或 CLI（退出前 force_save）协调，命令路径不直接碰持久化。

持久化边界是"崩溃恢复级耐久"：内存态权威，存档是周期快照（见 save.py）；两次
快照间的变更在异常崩溃后会丢，是有意取舍。

07 号票（块 A 地基）：``advance`` 在推进 tick 后、周期存档前，把 ``on_tick`` 事件
经 ``world.events`` 分发给所有订阅者（spec 块 A user story 2、§8"随时间推进类规则
必须挂 tick"）。on_tick 分发在存档之前，使未来 Nature / NPC 等订阅者推进的状态被
同 tick 的周期存档捕获。存档继续走 ``save_fn``（issue 验收 #4"或等价机制"允许保留
save_fn 并额外分发 on_tick--``force_save`` 语义清晰、周期触发逻辑天然留在 TickLoop、
05 号票行为零回归）；``force_save`` 不分发 on_tick（退出前立即存档不应触发世界推进
副作用）。M1 生产代码里 on_tick 暂无订阅者，事件总线机制就位为未来 Nature 时辰推进 /
NPC 行为 / Effect 衰减预留统一驱动点。``world`` 可选：不传时 ``advance`` 只做周期存档
（保持 05 号票行为），``__main__`` 构造时传 world 启用 on_tick 分发。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from mud_engine.events import ON_TICK, TickContext

if TYPE_CHECKING:
    from mud_engine.world import World

# 默认存档周期（tick 数）。CLI 每条命令推进 1 tick，即约每 10 条命令存一次--
# "普通游玩过程中稳定触发若干次周期性存档"（spec「心跳循环」）。
DEFAULT_SAVE_INTERVAL = 10


class TickLoop:
    """tick 计数 + on_tick 事件分发 + 间隔触发存档。

    存档触发由 ``save_fn`` 回调承担（解耦：本循环不知道存档写到哪、怎么写），
    CLI 构造时注入 ``lambda: save_world(world, player_id, save_dir)``。``world``
    传入后 ``advance`` 会把 ``on_tick`` 分发给 ``world.events`` 上的订阅者。
    """

    def __init__(
        self,
        save_fn: Callable[[], None],
        *,
        interval: int = DEFAULT_SAVE_INTERVAL,
        world: World | None = None,
    ) -> None:
        self._save_fn = save_fn
        self._interval = interval
        self._world = world
        self._tick = 0
        self._save_count = 0  # 已触发的存档次数（观测/测试用）

    @property
    def tick(self) -> int:
        """当前已推进的 tick 数。"""
        return self._tick

    @property
    def save_count(self) -> int:
        """已触发的存档次数（周期触发 + force_save 都计入）。"""
        return self._save_count

    def advance(self) -> None:
        """推进一个 tick：先分发 ``on_tick`` 给订阅者，再按周期触发存档。

        on_tick 分发在存档之前：未来 Nature / NPC 等订阅者推进的状态会被同 tick
        的周期存档捕获（保存最新世界状态）。``world`` 未传时分发跳过，只做周期
        存档（05 号票行为，零回归）。
        """
        self._tick += 1
        if self._world is not None:
            self._world.tick = self._tick
            self._world.events.dispatch(ON_TICK, TickContext(tick=self._tick, world=self._world))
        if self._tick % self._interval == 0:
            self._save()

    def force_save(self) -> None:
        """立即触发一次存档，不管当前 tick 是否到达周期（quit / 退出前用）。

        05 验收 #2：``quit`` 无论当前 tick 是否到达周期都会在退出前触发一次立即存档。
        不分发 on_tick：退出前立即存档不应触发世界推进副作用（Nature / NPC 不应被
        推进一个 tick）。
        """
        self._save()

    def _save(self) -> None:
        self._save_fn()
        self._save_count += 1


__all__ = ["DEFAULT_SAVE_INTERVAL", "TickLoop"]
