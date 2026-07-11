"""SystemContext：System.update 路径轻量上下文（阶段 1 Wave 2 T4，ADR-0021 决策 2 C 类）。

System.update 路径不经 Command 管线（Q3 裁决"System tick 派生变更不经 Command"），
无 ActionContext。这些路径的 ``previous_object()`` 检查在 LPC 中多是防御性代码
（防止 System 函数被外部误调），greenfield 下 System.update 由引擎调度器（TickRunner）
调用，不存在"外部误调"场景，**这些检查直接删除**。

若 System 路径确需审计 / 能力钩子（如 combat do_attack 需记录"谁打的谁"），携带轻量
``SystemContext``（02 Q3 未消除风险"System 路径 ActionContext 分歧"裁决："System 路径
携带轻量 SystemContext 供能力/审计钩子但派生变更不进 input log"）。SystemContext 只含
actor/target（无 source/capability_token，因 System 无"调用源"概念）。

[ADR-0021](../../../docs/adr/ADR-0021-previous-object-explicit-mapping.md) 决策 2 C 类
[02](../../../docs/xkx-arch/02-三个开放架构问题裁决.md) Q3
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SystemContext:
    """System.update 路径轻量上下文（ADR-0021 决策 2 C 类）。

    只含 actor/target，无 source/capability_token（System 无"调用源"概念）。
    派生变更不进 input log（Q3 裁决）。
    """

    actor: int
    """发起者 entity_id（如 combat do_attack 的攻击者）。"""

    target: int | None = None
    """目标 entity_id（如 combat do_attack 的被攻击者），None=无目标。"""

    @classmethod
    def for_actor(cls, actor: int) -> SystemContext:
        """构造仅含 actor 的 SystemContext（无目标 System tick 用）。"""
        return cls(actor=actor, target=None)
