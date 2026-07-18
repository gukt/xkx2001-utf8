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
"""

from __future__ import annotations

from collections.abc import Callable

# 默认存档周期（tick 数）。CLI 每条命令推进 1 tick，即约每 10 条命令存一次--
# "普通游玩过程中稳定触发若干次周期性存档"（spec「心跳循环」）。
DEFAULT_SAVE_INTERVAL = 10


class TickLoop:
    """tick 计数 + 间隔触发存档。M1 唯一挂载的系统是存档；未来加系统在此扩展。

    存档触发由 ``save_fn`` 回调承担（解耦：本循环不知道存档写到哪、怎么写），
    CLI 构造时注入 ``lambda: save_world(world, player_id, save_dir)``。
    """

    def __init__(
        self,
        save_fn: Callable[[], None],
        *,
        interval: int = DEFAULT_SAVE_INTERVAL,
    ) -> None:
        self._save_fn = save_fn
        self._interval = interval
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
        """推进一个 tick；``tick`` 达到 interval 的整数倍时触发一次存档。"""
        self._tick += 1
        if self._tick % self._interval == 0:
            self._save()

    def force_save(self) -> None:
        """立即触发一次存档，不管当前 tick 是否到达周期（quit / 退出前用）。

        05 验收 #2：``quit`` 无论当前 tick 是否到达周期都会在退出前触发一次立即存档。
        """
        self._save()

    def _save(self) -> None:
        self._save_fn()
        self._save_count += 1


__all__ = ["DEFAULT_SAVE_INTERVAL", "TickLoop"]
