"""ECS System 基类（阶段 1 T1，ADR-0014）。

System 是 tick 驱动的派生变更处理器（02 Q3 裁决：System tick 派生变更不经
Command）。每 tick（1s，CLAUDE.md 不变量）调 ``update``。派生变更通过 Effect 账本
记录（dissent 7，ADR-0017 / ADR-0018）。

具体 System（CombatSystem / ConditionSystem / HealSystem / ConnectionSystem 等）在
T1-T9 逐步实现（ADR-0014 的 6 ECS System）。
[ADR-0014](../../../docs/adr/ADR-0014-daemon-responsibility-redesign.md)
"""

from __future__ import annotations

from xkx.runtime.ecs import World


class System:
    """ECS System 基类：tick 驱动的派生变更处理器。

    子类 override ``update``，读组件快照、产出 Effect 账本、统一 apply 到 world
    （对齐 combat 的 resolve_attack -> apply_effects 模式，dissent 7）。System 派生
    变更不经 Command（02 Q3 裁决）。
    """

    name: str = "System"

    def update(self, world: World, tick: int) -> None:
        """每 tick 执行。子类 override。

        Args:
            world: ECS 世界（读快照 + 统一 apply 写）
            tick: 当前 tick 编号（1s 递增，CLAUDE.md 不变量 tick=1s）
        """
        raise NotImplementedError
