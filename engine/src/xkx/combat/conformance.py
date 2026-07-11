"""规格符合性检查器：验证 resolve_attack 输出符合 do_attack 规格。

输入 ``CombatContext + CombatRoundResult``，对照 do_attack 规格
（[layer_e_combat.py](../spec/layer_e_combat.py)）+ 实现状态映射
（[impl_map.py](../spec/impl_map.py)）检查，输出 ``ConformanceReport``。

检查范围（8 项单次 result 属性，
[ADR-0011](../../../docs/adr/ADR-0011-spec-conformance-checker.md)）：
- result_code 合法 / damage 非负 / 非命中时 damage=0
- effect target 合法 / 命中时有且仅有一条 DAMAGE / 非命中时无 DAMAGE
- 三层资源不变量（apply effects 后 0<=qi<=eff_qi<=max_qi）
- 交织顺序（ledger 中 message 与 effect 非全分组）

统计性属性（确定性、三分支可达、概率分布、TYPE_QUICK 对比）
在属性测试层用 hypothesis 做。
"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, Field

from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.result import (
    KIND_DAMAGE,
    KIND_EXP,
    KIND_JINGLI,
    KIND_POTENTIAL,
    KIND_SKILL_IMPROVE,
    KIND_WOUND,
    LEDGER_EFFECT,
    LEDGER_MESSAGE,
    RESULT_DODGE,
    RESULT_HIT,
    RESULT_PARRY,
    CombatRoundResult,
    Effect,
)
from xkx.spec.impl_map import DO_ATTACK_IMPL_MAP, ImplEntry, ImplStatus


class Violation(BaseModel):
    """单条规格违反。"""

    check_name: str
    spec_ref: str
    detail: str


class ConformanceReport(BaseModel):
    """符合性检查报告。"""

    passed: list[str] = Field(default_factory=list)
    skipped: list[ImplEntry] = Field(default_factory=list)
    violations: list[Violation] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.violations) == 0


_VALID_RESULT_CODES = {RESULT_HIT, RESULT_DODGE, RESULT_PARRY}
_VALID_KINDS = {
    KIND_DAMAGE,
    KIND_WOUND,
    KIND_EXP,
    KIND_POTENTIAL,
    KIND_JINGLI,
    KIND_SKILL_IMPROVE,
}


def _apply_effects(snapshot: CombatantSnapshot, effects: list[Effect]) -> CombatantSnapshot:
    """将 Effect 应用到快照副本（模拟 receive_damage/receive_wound 的 clamp 语义）。

    三层资源不变量验证用：apply 后检查 0<=qi<=eff_qi<=max_qi。
    """
    s = deepcopy(snapshot)
    for e in effects:
        if e.target_id != s.entity_id:
            continue
        if e.kind == KIND_DAMAGE:
            s.qi = max(0, s.qi - e.amount)
        elif e.kind == KIND_WOUND:
            s.eff_qi = max(0, s.eff_qi - e.amount)
            s.qi = min(s.qi, s.eff_qi)  # receive_wound 同步 qi <= eff_qi
        elif e.kind == KIND_EXP:
            s.combat_exp += e.amount
        elif e.kind == KIND_POTENTIAL:
            s.potential = min(s.max_potential, s.potential + e.amount)
        elif e.kind == KIND_JINGLI:
            s.jingli = max(0, min(s.max_jingli, s.jingli + e.amount))
        elif e.kind == KIND_SKILL_IMPROVE and e.detail:
            s.skills[e.detail] = s.skills.get(e.detail, 0) + e.amount
    return s


def _check_result_code_valid(ctx: CombatContext, result: CombatRoundResult) -> Violation | None:
    if result.result_code not in _VALID_RESULT_CODES:
        return Violation(
            check_name="result_code_valid",
            spec_ref="do_attack postconditions[0] 完成一次完整攻击回合",
            detail=f"result_code={result.result_code} 不在合法集 {_VALID_RESULT_CODES}",
        )
    return None


def _check_damage_non_negative(ctx: CombatContext, result: CombatRoundResult) -> Violation | None:
    if result.damage < 0:
        return Violation(
            check_name="damage_non_negative",
            spec_ref="do_attack postconditions[1] damage > 0 时 victim.qi 减少",
            detail=f"result.damage={result.damage} < 0",
        )
    return None


def _check_damage_zero_on_non_hit(
    ctx: CombatContext, result: CombatRoundResult
) -> Violation | None:
    if result.result_code != RESULT_HIT and result.damage != 0:
        return Violation(
            check_name="damage_zero_on_non_hit",
            spec_ref="do_attack side_effects 步骤3/4 return（闪避/招架不进步骤5）",
            detail=f"result_code={result.result_code} 但 damage={result.damage} != 0",
        )
    return None


def _check_effect_target_valid(ctx: CombatContext, result: CombatRoundResult) -> Violation | None:
    valid_ids = {ctx.attacker.entity_id, ctx.victim.entity_id}
    for e in result.effects:
        if e.target_id not in valid_ids:
            return Violation(
                check_name="effect_target_valid",
                spec_ref="do_attack side_effects target 字段（victim/me）",
                detail=f"effect kind={e.kind} target_id={e.target_id} 不在 {valid_ids}",
            )
    return None


def _check_hit_has_damage_effect(ctx: CombatContext, result: CombatRoundResult) -> Violation | None:
    if result.result_code != RESULT_HIT:
        return None
    damages = [e for e in result.effects if e.kind == KIND_DAMAGE]
    if len(damages) != 1:
        return Violation(
            check_name="hit_has_damage_effect",
            spec_ref="do_attack side_effects order=34 receive_damage('qi', damage, me)",
            detail=f"RESULT_HIT 时 KIND_DAMAGE effect 数量={len(damages)}，期望 1",
        )
    if damages[0].target_id != ctx.victim.entity_id:
        return Violation(
            check_name="hit_has_damage_effect",
            spec_ref="do_attack side_effects order=34 receive_damage target=victim",
            detail=f"DAMAGE target_id={damages[0].target_id} != victim={ctx.victim.entity_id}",
        )
    return None


def _check_dodge_parry_no_damage(ctx: CombatContext, result: CombatRoundResult) -> Violation | None:
    if result.result_code == RESULT_HIT:
        return None
    damages = [e for e in result.effects if e.kind == KIND_DAMAGE]
    if damages:
        return Violation(
            check_name="dodge_parry_no_damage",
            spec_ref="do_attack side_effects 步骤3/4 return（闪避/招架不进步骤5-6）",
            detail=f"result_code={result.result_code} 但有 {len(damages)} 条 KIND_DAMAGE",
        )
    return None


def _check_three_layer_resource_invariant(
    ctx: CombatContext, result: CombatRoundResult
) -> Violation | None:
    for snapshot in (ctx.attacker, ctx.victim):
        applied = _apply_effects(snapshot, result.effects)
        if applied.qi < 0:
            return Violation(
                check_name="three_layer_resource_invariant",
                spec_ref="do_attack invariants[0] 0<=qi<=eff_qi<=max_qi",
                detail=f"{snapshot.name} apply 后 qi={applied.qi} < 0",
            )
        if applied.eff_qi < applied.qi:
            return Violation(
                check_name="three_layer_resource_invariant",
                spec_ref="do_attack invariants[0] qi<=eff_qi",
                detail=f"{snapshot.name} apply 后 qi={applied.qi} > eff_qi={applied.eff_qi}",
            )
        if applied.eff_qi > applied.max_qi:
            return Violation(
                check_name="three_layer_resource_invariant",
                spec_ref="do_attack invariants[0] eff_qi<=max_qi",
                detail=f"{snapshot.name} eff_qi={applied.eff_qi} > max_qi={applied.max_qi}",
            )
        if applied.jingli < 0 or applied.jingli > applied.max_jingli:
            return Violation(
                check_name="three_layer_resource_invariant",
                spec_ref="do_attack invariants[0] 0<=jingli<=max_jingli（同三层资源）",
                detail=f"{snapshot.name} jingli={applied.jingli} 越界[0,{applied.max_jingli}]",
            )
    return None


def _check_interleaving_order(ctx: CombatContext, result: CombatRoundResult) -> Violation | None:
    if result.result_code != RESULT_HIT:
        return None  # dodge/parry 分支局部变量不记录 ledger，S1 简化下交织不可验证
    ledger = result.ledger
    message_indices = [i for i, entry in enumerate(ledger) if entry.entry_type == LEDGER_MESSAGE]
    effect_indices = [i for i, entry in enumerate(ledger) if entry.entry_type == LEDGER_EFFECT]
    if not message_indices or not effect_indices:
        return None
    has_message_before_effect = min(message_indices) < max(effect_indices)
    has_effect_before_message = min(effect_indices) < max(message_indices)
    if not (has_message_before_effect and has_effect_before_message):
        return Violation(
            check_name="interleaving_order",
            spec_ref="do_attack invariants[1] 七步副作用交织不可分离",
            detail="hit 分支 ledger 中 message 与 effect 全分组（非交织）",
        )
    return None


_CHECKS: list[tuple[str, object]] = [
    ("result_code_valid", _check_result_code_valid),
    ("damage_non_negative", _check_damage_non_negative),
    ("damage_zero_on_non_hit", _check_damage_zero_on_non_hit),
    ("effect_target_valid", _check_effect_target_valid),
    ("hit_has_damage_effect", _check_hit_has_damage_effect),
    ("dodge_parry_no_damage", _check_dodge_parry_no_damage),
    ("three_layer_resource_invariant", _check_three_layer_resource_invariant),
    ("interleaving_order", _check_interleaving_order),
]


def check_conformance(ctx: CombatContext, result: CombatRoundResult) -> ConformanceReport:
    """检查 resolve_attack 输出是否符合 do_attack 规格（按 impl_map 状态过滤）。"""
    report = ConformanceReport()
    for check_name, check_fn in _CHECKS:
        entry = DO_ATTACK_IMPL_MAP.get(check_name)
        if entry is None or entry.status == ImplStatus.POSTPONED:
            if entry is not None:
                report.skipped.append(entry)
            continue
        violation = check_fn(ctx, result)
        if violation is None:
            report.passed.append(check_name)
        else:
            report.violations.append(violation)
    return report
