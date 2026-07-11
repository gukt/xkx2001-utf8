"""``resolve_attack`` 的输出：一回合结果 + 副作用账本。

Effect 账本按"文本与状态交织真实顺序"记录（do_attack 七步中 exp/jingli/qi 的
mutate 与消息产出是交织的，不得"先算后批量 apply"）。调用方按账本顺序 apply
到 ECS 组件并下发消息。

``ledger`` 字段记录 msg/eff 的统一调用顺序，用于验证交织不变量（do_attack
invariants[1]，[ADR-0011](../../../docs/adr/ADR-0011-spec-conformance-checker.md)）。
``messages`` 与 ``effects`` 列表保留不变以向后兼容。

T6（ADR-0023）扩展：
- ``LedgerEntry`` 支持 riposte 子回合嵌入（``sub_result`` 字段，非独立账本）--
  父回合文本 -> 子回合文本+副作用 -> 父回合后续的交织序列（决策 4 第 2 项）。
- ``CombatRoundResult.riposte_triggered`` 从"仅标记"升级为实际递归结果载体。
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
LEDGER_SUBRESULT = "subresult"  # riposte 子回合嵌入（ADR-0023 决策 4 第 2 项）


class Effect(BaseModel):
    """战斗副作用。运行时按账本顺序 apply 到组件。"""

    kind: str
    target_id: int
    amount: int = 0
    detail: str = ""  # skill_id / damage_type / 等


class LedgerEntry(BaseModel):
    """账本条目：message / effect / subresult，按 resolve_attack 调用顺序记录。

    ``sub_result`` 用于 riposte 子回合嵌入：父回合 ledger 的对应 order 位置嵌入
    子回合的完整 ``CombatRoundResult``（含子回合自己的 ledger），形成"父回合文本
    -> 子回合文本+副作用 -> 父回合后续"的交织序列（非独立账本）。
    """

    entry_type: str  # LEDGER_MESSAGE / LEDGER_EFFECT / LEDGER_SUBRESULT
    text: str = ""  # entry_type == LEDGER_MESSAGE 时
    effect: Effect | None = None  # entry_type == LEDGER_EFFECT 时
    sub_result: CombatRoundResult | None = None  # entry_type == LEDGER_SUBRESULT 时


class CombatRoundResult(BaseModel):
    """一回合战斗结果。"""

    result_code: int  # RESULT_HIT / RESULT_DODGE / RESULT_PARRY
    damage: int = 0  # 最终伤害（HIT 时；DODGE/PARRY 为 0）
    messages: list[str] = Field(default_factory=list)  # 文本，按交织顺序
    effects: list[Effect] = Field(default_factory=list)  # 副作用，按交织顺序
    ledger: list[LedgerEntry] = Field(default_factory=list)  # 统一调用顺序（交织验证用）
    riposte_triggered: bool = False  # T6：实际递归触发标记（非 S1 仅标记）
    # riposte 子回合结果（None=未触发；非空时子回合已嵌入 ledger 的对应位置）
    riposte_sub_result: CombatRoundResult | None = None


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


def embed_subresult(result: CombatRoundResult, sub: CombatRoundResult) -> None:
    """在父回合 ledger 当前位置嵌入 riposte 子回合（ADR-0023 决策 4 第 2 项）。

    子回合的 messages/effects 已在其自身 ledger 中交织记录；父回合在嵌入位置
    追加一条 ``LEDGER_SUBRESULT`` 条目引用子回合整体。调用方 apply 时按账本
    顺序：先 apply 父回合前序 -> 展开 sub_result 的 messages/effects -> 父回合
    后续。保持七步交织不分离（子回合整体嵌入，不拆散）。
    """
    result.ledger.append(LedgerEntry(entry_type=LEDGER_SUBRESULT, sub_result=sub))
