"""死亡状态机核心判定（M2-06 / spec C1）。

纯函数：给定当前状态 + 是否免死区，在气血耗尽时返回下一状态。不读写 World，
不执行掉落/惩罚/复活（那是 17 号票）。组件 ``Unconscious``/``Dead``/``NoDeathZone``
见 ``components``。
"""

from __future__ import annotations

from enum import Enum


class DeathState(Enum):
    """存活 / 昏迷 / 死亡。存活用"两 marker 都不挂"表达，本枚举只供纯函数。"""

    ALIVE = "alive"
    UNCONSCIOUS = "unconscious"
    DEAD = "dead"


def next_death_state(
    current: DeathState,
    *,
    in_no_death_zone: bool,
    vitals_depleted: bool = True,
) -> DeathState:
    """气血耗尽时的两段式状态转移。

    - 未耗尽：状态不变（调用方可在未耗尽时跳过本函数；保留参数便于统一入口）。
    - 免尽 + 免死区：一律转/保持昏迷（反复昏迷允许）。
    - 耗尽 + 非免死区 + 存活：转昏迷（第一段容错）。
    - 耗尽 + 非免死区 + 已昏迷：转死亡（第二段）。
    - 已死亡：保持死亡。
    """
    if not vitals_depleted:
        return current
    if current is DeathState.DEAD:
        return DeathState.DEAD
    if in_no_death_zone:
        return DeathState.UNCONSCIOUS
    if current is DeathState.UNCONSCIOUS:
        return DeathState.DEAD
    return DeathState.UNCONSCIOUS


__all__ = ["DeathState", "next_death_state"]
