"""``resolve_attack`` 的输出：一回合结果 + 副作用账本。

Effect 账本按"文本与状态交织真实顺序"记录（do_attack 七步中 exp/jingli/qi 的
mutate 与消息产出是交织的，不得"先算后批量 apply"）。调用方按账本顺序 apply
到 ECS 组件并下发消息。
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


class Effect(BaseModel):
    """战斗副作用。运行时按账本顺序 apply 到组件。"""

    kind: str
    target_id: int
    amount: int = 0
    detail: str = ""  # skill_id / damage_type / 等


class CombatRoundResult(BaseModel):
    """一回合战斗结果。"""

    result_code: int  # RESULT_HIT / RESULT_DODGE / RESULT_PARRY
    damage: int = 0  # 最终伤害（HIT 时；DODGE/PARRY 为 0）
    messages: list[str] = Field(default_factory=list)  # 文本，按交织顺序
    effects: list[Effect] = Field(default_factory=list)  # 副作用，按交织顺序
    riposte_triggered: bool = False  # S1: 仅标记，不递归（riposte 后置）


def msg(result: CombatRoundResult, text: str) -> None:
    """追加一条战斗文本（交织顺序）。"""
    result.messages.append(text)


def eff(
    result: CombatRoundResult,
    kind: str,
    target_id: int,
    amount: int = 0,
    detail: str = "",
) -> None:
    """追加一条副作用到账本（交织顺序）。"""
    result.effects.append(Effect(kind=kind, target_id=target_id, amount=amount, detail=detail))
