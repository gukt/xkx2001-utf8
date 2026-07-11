"""combat 范围的 seeded RNG。

替换 LPC ``combatd.c`` ``do_attack`` 的 18 处 ``random()`` 调用，
使 ``resolve_attack`` 成为可重放的纯函数（同 seed + 同快照 -> 同输出）。

LPC ``random(n)`` 返回 ``[0, n)``；Python ``random.Random.randrange(n)`` 同语义。
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


class DeterministicRNG:
    """注入 ``resolve_attack`` 的确定性随机源。"""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def rand(self, n: int) -> int:
        """LPC ``random(n)``：返回 ``[0, n)``。``n <= 0`` 时返回 0。"""
        if n <= 0:
            return 0
        return self._rng.randrange(n)

    def chance(self, denominator: int) -> bool:
        """LPC ``!random(n)`` 语义：命中概率 ``1/n``（即 ``random(n) == 0``）。"""
        if denominator <= 0:
            return False
        return self._rng.randrange(denominator) == 0

    def choice(self, seq: Sequence[T]) -> T | None:
        """从序列随机选一个（对应 LPC ``random(sizeof(arr))`` 取下标）。"""
        if not seq:
            return None
        return seq[self._rng.randrange(len(seq))]

    def derive_seed(self) -> int:
        """从当前 RNG 状态派生子 seed（riposte 递归用，ADR-0023 决策 4 第 2 项）。

        确定性：同 seed 链推进 -> 同派生 seed。用于 riposte 子回合的
        ``DeterministicRNG`` 初始化，保证子回合可重放。
        """
        return self._rng.randrange(2**31)
