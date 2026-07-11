"""``resolve_attack`` 的输出：一回合结果 + 副作用账本。

Effect 账本按"文本与状态交织真实顺序"记录（do_attack 七步中 exp/jingli/qi 的
mutate 与消息产出是交织的，不得"先算后批量 apply"）。调用方按账本顺序 apply
到 ECS 组件并下发消息。

``ledger`` 字段记录 msg/eff 的统一调用顺序，用于验证交织不变量（do_attack
invariants[1]，[ADR-0011](../../../docs/adr/ADR-0011-spec-conformance-checker.md)）。
``messages`` 与 ``effects`` 列表保留不变以向后兼容。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# 结果码（对应 include/combat.h RESULT_*）
RESULT_HIT = 0
RESULT_DODGE = -1
RESULT_PARRY = -2

# Effect 类型
KIND_DAMAGE = "damage"  # qi 减少
KIND_WOUND = "wound"  # eff_qi 减少（受伤）
KIND_EXP = "exp"  # combat_exp 增加
KIND_POTENTIAL = "potential"  # 潜能增加
KIND_JINGLI = "jingli"  # 精力变化（正=恢复，负=消耗）
KIND_SKILL_IMPROVE = "skill_improve"  # 技能熟练度提升

LEDGER_MESSAGE = "message"
LEDGER_EFFECT = "effect"


class Effect(BaseModel):
    """战斗副作用。运行时按账本顺序 apply 到组件。"""

    kind: str
    target_id: int
    amount: int = 0
    detail: str = ""  # skill_id / damage_type / 等


class LedgerEntry(BaseModel):
    """账本条目：message 或 effect，按 resolve_attack 调用顺序记录。"""

    entry_type: str  # LEDGER_MESSAGE / LEDGER_EFFECT
    text: str = ""  # entry_type == LEDGER_MESSAGE 时
    effect: Effect | None = None  # entry_type == LEDGER_EFFECT 时


class CombatRoundResult(BaseModel):
    """一回合战斗结果。"""

    result_code: int  # RESULT_HIT / RESULT_DODGE / RESULT_PARRY
    damage: int = 0  # 最终伤害（HIT 时；DODGE/PARRY 为 0）
    messages: list[str] = Field(default_factory=list)  # 文本，按交织顺序
    effects: list[Effect] = Field(default_factory=list)  # 副作用，按交织顺序
    ledger: list[LedgerEntry] = Field(default_factory=list)  # 统一调用顺序（交织验证用）
    riposte_triggered: bool = False  # S1: 仅标记，不递归（riposte 后置）


def msg(result: CombatRoundResult, text: str) -> None:
    """追加一条战斗文本（交织顺序）。"""
    result.messages.append(text)
    result.ledger.append(LedgerEntry(entry_type=LEDGER_MESSAGE, text=text))


def eff(
    result: CombatRoundResult,
    kind: str,
    target_id: int,
    amount: int = 0,
    detail: str = "",
) -> None:
    """追加一条副作用到账本（交织顺序）。"""
    effect = Effect(kind=kind, target_id=target_id, amount=amount, detail=detail)
    result.effects.append(effect)
    result.ledger.append(LedgerEntry(entry_type=LEDGER_EFFECT, effect=effect))
