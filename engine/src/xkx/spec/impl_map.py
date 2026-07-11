"""实现状态映射（impl_map）-- 规格条目与 Python 实现的符合性状态。

记录 ``do_attack`` 规格（[layer_e_combat.py](layer_e_combat.py) ``_do_attack``）
的每条检查项在 ``resolve_attack``（S1 简化版，
[ADR-0002](../../../docs/adr/ADR-0002-resolve-attack-extraction.md)）
中的实现状态。

三状态：
- ``implemented``：resolve_attack 已实现且符合规格，ConformanceChecker 验证
- ``simplified``：resolve_attack 简化实现，验证简化版规格（附简化说明）
- ``postponed``：后置（riposte 递归 / 双武器 / 回调链等），跳过验证

impl_map 独立于规格源（不污染 layer_e_combat.py 的纯 LPC 契约）。
ConformanceChecker（[conformance.py](../combat/conformance.py)）消费本映射决定检查/跳过。
设计见 [ADR-0011](../../../docs/adr/ADR-0011-spec-conformance-checker.md)。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ImplStatus(StrEnum):
    """规格条目在 Python 实现中的状态。"""

    IMPLEMENTED = "implemented"
    SIMPLIFIED = "simplified"
    POSTPONED = "postponed"


class ImplEntry(BaseModel):
    """单条检查项的实现状态。

    ``check_name`` 与 ConformanceChecker 的检查函数一一对应。
    """

    check_name: str
    status: ImplStatus
    spec_ref: str
    adr_ref: str
    note: str = ""


DO_ATTACK_IMPL_MAP: dict[str, ImplEntry] = {
    # --- implemented：resolve_attack 已实现且符合规格 ---
    "determinism": ImplEntry(
        check_name="determinism",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack random_specs determinism_note + CombatContext.seed",
        adr_ref="ADR-0002",
        note="同 seed + 同快照 -> 同输出，DeterministicRNG 替换 18 处 random",
    ),
    "three_branches": ImplEntry(
        check_name="three_branches",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack side_effects 步骤3/4/5 三分支 return",
        adr_ref="ADR-0002",
        note="dodge(步骤3)/parry(步骤4)/hit(步骤5-7) 三分支 seed 遍历可达",
    ),
    "dodge_probability": ImplEntry(
        check_name="dodge_probability",
        status=ImplStatus.IMPLEMENTED,
        spec_ref='do_attack random_specs "闪避判定" random(ap+dp) < dp',
        adr_ref="ADR-0002",
        note="rng.rand(ap+dp) < dp 对应 dp/(ap+dp) 概率模型",
    ),
    "parry_probability": ImplEntry(
        check_name="parry_probability",
        status=ImplStatus.IMPLEMENTED,
        spec_ref='do_attack random_specs "招架判定" random(ap+pp) < pp',
        adr_ref="ADR-0002",
        note="rng.rand(ap+pp) < pp 对应 pp/(ap+pp) 概率模型",
    ),
    "ap_dp_pp_lower_bound": ImplEntry(
        check_name="ap_dp_pp_lower_bound",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack invariants[2] ap>=1 && dp>=1 && pp>=1",
        adr_ref="ADR-0002",
        note="skill_power 返回值 >= 1（level³/3 + apply + attr*2，最小属性下 >= 1）",
    ),
    "quick_damage_halved": ImplEntry(
        check_name="quick_damage_halved",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack invariants[3] TYPE_QUICK => damage /= 2",
        adr_ref="ADR-0002",
        note="ctx.attack_type == TYPE_QUICK 时 damage //= 2",
    ),
    "damage_non_negative": ImplEntry(
        check_name="damage_non_negative",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack postconditions[1] damage > 0 时 victim.qi 减少",
        adr_ref="ADR-0002",
        note="resolve_attack 显式 if damage < 0: damage = 0",
    ),
    "result_code_valid": ImplEntry(
        check_name="result_code_valid",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack postconditions[0] 完成一次完整攻击回合",
        adr_ref="ADR-0002",
        note="result_code in {RESULT_HIT, RESULT_DODGE, RESULT_PARRY}",
    ),
    "damage_zero_on_non_hit": ImplEntry(
        check_name="damage_zero_on_non_hit",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack side_effects 步骤3/4 return（闪避/招架不进步骤5 伤害结算）",
        adr_ref="ADR-0002",
        note="RESULT_DODGE/PARRY 时 damage == 0（闪避/招架提前 return）",
    ),
    "effect_target_valid": ImplEntry(
        check_name="effect_target_valid",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack side_effects target 字段（victim/me）",
        adr_ref="ADR-0002",
        note="effect.target_id in {attacker.entity_id, victim.entity_id}",
    ),
    "hit_has_damage_effect": ImplEntry(
        check_name="hit_has_damage_effect",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack side_effects order=34 receive_damage('qi', damage, me)",
        adr_ref="ADR-0002",
        note="RESULT_HIT 时 effects 含且仅含一条 KIND_DAMAGE",
    ),
    "dodge_parry_no_damage": ImplEntry(
        check_name="dodge_parry_no_damage",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack side_effects 步骤3/4 return（闪避/招架时不进步骤5-6）",
        adr_ref="ADR-0002",
        note="RESULT_DODGE/PARRY 时 effects 无 KIND_DAMAGE",
    ),
    # --- implemented（T6 ADR-0023 升级：riposte 递归 + hit_ob/hit_by mapping
    #     补全后交织顺序更完整可验证；three_layer_resource_invariant 始终可验证）---
    "three_layer_resource_invariant": ImplEntry(
        check_name="three_layer_resource_invariant",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack invariants[0] 0<=qi<=eff_qi<=max_qi",
        adr_ref="ADR-0023",
        note="产 Effect 不调 receive_damage/wound；验证 apply 后不变量（T6 升级："
        "6 项简化台账补全后 combat 范围确定性重放可验证，三层资源不变量始终可验证）",
    ),
    "interleaving_order": ImplEntry(
        check_name="interleaving_order",
        status=ImplStatus.IMPLEMENTED,
        spec_ref="do_attack invariants[1] 七步副作用交织不可分离",
        adr_ref="ADR-0023",
        note="T6 升级：riposte 递归子回合嵌入父回合 ledger + hit_ob/hit_by mapping "
        "分支按规格 order 交织入账本，hit 分支 ledger 交织顺序完整可验证",
    ),
    # --- postponed：后置，跳过验证（不进 ConformanceChecker 检查范围）---
    # 以下检查项不注册到 impl_map，ConformanceChecker 不检查。
    # 仅在此记录后置理由，供审计查阅。
    # - receive_damage/receive_wound 实际调用（side_effects order=34/35）：
    #   resolve_attack 产 Effect 不调函数，simplified 已在 three_layer_resource_invariant 覆盖
    # - hit_ob/hit_by 回调链（side_effects order=23/25/26/32/33）：ADR-0002 仅 int 加成/覆盖，
    #   mapping 分支后置，阶段 0 后期补全
    # - riposte 递归（side_effects order=48/49）：ADR-0002 仅标记不递归，S2 子回合交织后置
    # - reset_action / actions 招式映射（side_effects order=3）：S4 SkillData YAML 后置
    # - post_action 回调（side_effects order=47）：后置
    # - wizard verbose / report_status / interrupt_me / remove_enemy / winner_msg
    #   （side_effects order=42/43/44/45/46）：后处理 + 自动停手，后置
    # - yield 模式 parry 经验（side_effects order=39）：后置
    # - 双武器/辟邪剑/双手互博：在 fight() 中处理，不在 do_attack 内（do_attack notes 明确）
    # - skill_power 完整公式（DamageFormula 三段式）：ADR-0002 简化为 level³/3，
    #   阶段 0 规格 extracted 但实现待阶段 2
}


def get_status(check_name: str) -> ImplStatus:
    """查询检查项的实现状态。未注册的检查项视为 postponed。"""
    entry = DO_ATTACK_IMPL_MAP.get(check_name)
    if entry is None:
        return ImplStatus.POSTPONED
    return entry.status
