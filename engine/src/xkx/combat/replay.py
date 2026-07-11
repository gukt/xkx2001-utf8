"""combat 范围确定性重放入口（ADR-0023 决策 3）。

``replay(snapshot, seed, input_log)`` 纯函数：按序消费 input log，每条输入驱动
一次 ``resolve_attack``，seed 链按调用顺序推进。同 snapshot + 同 seed + 同
input_log -> 同 ``list[CombatRoundResult]`` 输出，跨进程一致（PYTHONHASHSEED=0，
[ADR-0012](../../../docs/adr/ADR-0012-performance-microbenchmark.md) 已验证基础）。

combat-only 确定性边界（ADR-0023 决策 1）：重放只覆盖 combat 相关组件 + combat
相关输入，不含 heal/exp/condition 等 System 的 tick mutation（全仿真确定性后置 M3）。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.combat.result import CombatRoundResult

# input log 条目类型（ADR-0023 决策 3）
INPUT_ATTACK = "attack"  # 一次攻击输入（attacker_id + victim_id + attack_type）


class InputEntry(BaseModel):
    """input log 单条记录：战斗内输入的有序序列。

    ADR-0023 决策 3：每条记录含输入类型 + 输入内容 + 输入时序。T6 最小实现：
    ``attack`` 类型（attacker_id/victim_id/attack_type），riposte 递归由
    ``resolve_attack`` 内部处理（不进 input log，属派生非输入）。
    """

    entry_type: str = INPUT_ATTACK
    attacker_id: int = 0
    victim_id: int = 0
    attack_type: int = 0
    # 输入时序（tick 内相对顺序，T8 跨 tick 回放扩展用；T6 单 tick 内按列表顺序）
    seq: int = 0


class CombatSnapshot(BaseModel):
    """单 tick 战斗快照（ADR-0023 决策 3）。

    覆盖 combat 相关组件 + combat 相关 temp，足够支撑 combat 范围重放。
    ``combatants`` 是参与战斗的实体快照（按 entity_id 索引），``enemies`` 是
    敌对关系（entity_id -> [enemy_id]），``seed`` 是本 tick 的 seed 基。
    """

    combatants: dict[int, CombatantSnapshot] = Field(default_factory=dict)
    seed: int = 0
    limbs: tuple[str, ...] = (
        "头部",
        "胸口",
        "腹部",
        "左臂",
        "右臂",
        "左腿",
        "右腿",
    )


def replay(
    snapshot: CombatSnapshot,
    seed: int,
    input_log: list[InputEntry],
) -> list[CombatRoundResult]:
    """确定性重放：按序消费 input log，驱动 resolve_attack。

    同 snapshot + 同 seed + 同 input_log -> 同输出（combat-only 确定性）。
    每条 ``attack`` 输入从快照取 attacker/victim 不可变副本，构造 ``CombatContext``
    （seed 由调用方传入，单 tick 内多回合用 seed 递增派生保证确定性）。

    不依赖运行时 ECS（ADR-0023 决策 2：重放不依赖运行时，只依赖快照 + seed + input log）。
    """
    results: list[CombatRoundResult] = []
    for i, entry in enumerate(input_log):
        if entry.entry_type != INPUT_ATTACK:
            continue
        attacker = snapshot.combatants.get(entry.attacker_id)
        victim = snapshot.combatants.get(entry.victim_id)
        if attacker is None or victim is None:
            continue
        ctx = CombatContext(
            attacker=attacker.model_copy(),
            victim=victim.model_copy(),
            # 单 tick 内多回合：seed + i 派生保证确定性（同 input_log 顺序 -> 同 seed 链）
            seed=seed + i,
            attack_type=entry.attack_type,
            limbs=snapshot.limbs,
        )
        results.append(resolve_attack(ctx))
    return results
