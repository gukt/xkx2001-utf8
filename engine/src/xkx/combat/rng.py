"""combat 范围的 seeded RNG。

收口 LPC ``combatd.c`` ``do_attack`` 函数体内的 31 处 ``random()`` 调用，使
``resolve_attack`` 成为可重放的纯函数（同 seed + 同快照 -> 同输出）。

精确口径（2026-07-16 核查，braces 平衡 L340-L780 排除注释）：
- LPC 侧：``combatd.c`` ``do_attack`` 31 处 ``random()``（规格侧 random 点）。
- 实现侧：``resolve_attack`` 收口为 16 处 ``DeterministicRNG`` 调用
  （``rand``×13 + ``choice``×1 + ``chance``×1 + ``derive_seed``×1）。一处 rng 调用
  可对应多个 LPC random 点（如循环内 ``rng.rand``），故 16 < 31 非"漏收口"。
- ``s_combatd.c`` 36 处 ``random()`` 属阵法合击路径
  （ADR-0027 后置 2.7/M3），**当前 combat 确定性基准仅 ``combatd.c`` 一版，
  ``s_combatd.c`` 不纳入基准**。

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
