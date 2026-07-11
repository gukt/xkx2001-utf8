"""规格符合性检查器测试（任务 3 路径 B，
[ADR-0011](../../../docs/adr/ADR-0011-spec-conformance-checker.md)）。

测试内容：
- ConformanceChecker 单次检查：hypothesis 生成 ctx -> resolve_attack -> 断言无违反
- 统计性属性：确定性 / 三分支可达 / 闪避概率 / TYPE_QUICK 减半
- impl_map 完整性：检查项注册状态覆盖
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from xkx.combat.conformance import check_conformance
from xkx.combat.context import (
    TYPE_QUICK,
    TYPE_REGULAR,
    CombatantSnapshot,
    CombatContext,
)
from xkx.combat.resolve_attack import resolve_attack, skill_power
from xkx.combat.result import RESULT_DODGE, RESULT_HIT, RESULT_PARRY
from xkx.spec.impl_map import DO_ATTACK_IMPL_MAP, ImplStatus

# ---------------------------------------------------------------------------
# hypothesis 策略：生成合法 CombatantSnapshot
# ---------------------------------------------------------------------------


@st.composite
def _combatant(
    draw: st.DrawFn,
    entity_id: int,
    name: str,
) -> CombatantSnapshot:
    max_qi = draw(st.integers(min_value=1, max_value=2000))
    eff_qi = draw(st.integers(min_value=0, max_value=max_qi))
    qi = draw(st.integers(min_value=0, max_value=eff_qi))

    max_jing = draw(st.integers(min_value=1, max_value=2000))
    jing = draw(st.integers(min_value=0, max_value=max_jing))

    max_jingli = draw(st.integers(min_value=1, max_value=2000))
    jingli = draw(st.integers(min_value=0, max_value=max_jingli))

    max_potential = draw(st.integers(min_value=10, max_value=1000))

    skills_keys = draw(
        st.lists(
            st.sampled_from(["unarmed", "dodge", "parry"]), min_size=1, max_size=3, unique=True
        )
    )
    skills: dict[str, int] = {}
    for k in skills_keys:
        skills[k] = draw(st.integers(min_value=0, max_value=200))

    return CombatantSnapshot(
        entity_id=entity_id,
        name=name,
        str_=draw(st.integers(min_value=1, max_value=50)),
        dex_=draw(st.integers(min_value=1, max_value=50)),
        int_=draw(st.integers(min_value=1, max_value=50)),
        con_=draw(st.integers(min_value=1, max_value=50)),
        qi=qi,
        max_qi=max_qi,
        eff_qi=eff_qi,
        jing=jing,
        max_jing=max_jing,
        jingli=jingli,
        max_jingli=max_jingli,
        combat_exp=draw(st.integers(min_value=0, max_value=10000)),
        potential=draw(st.integers(min_value=0, max_value=max_potential)),
        max_potential=max_potential,
        skills=skills,
        apply_attack=draw(st.integers(min_value=0, max_value=100)),
        apply_dodge=draw(st.integers(min_value=0, max_value=100)),
        apply_parry=draw(st.integers(min_value=0, max_value=100)),
        apply_damage=draw(st.integers(min_value=0, max_value=100)),
        apply_armor=draw(st.integers(min_value=0, max_value=100)),
        weapon=draw(st.one_of(st.none(), st.text(min_size=1, max_size=10))),
        attack_skill=draw(st.sampled_from(["unarmed", "dodge", "parry"])),
        weapon_label=draw(st.text(min_size=1, max_size=5)),
        action_damage=draw(st.integers(min_value=0, max_value=100)),
        action_damage_type=draw(st.text(min_size=1, max_size=5)),
        hit_ob_bonus=draw(st.integers(min_value=0, max_value=50)),
        hit_by_override=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=200))),
    )


@st.composite
def _combat_context(draw: st.DrawFn) -> CombatContext:
    attacker = draw(_combatant(entity_id=1, name="甲"))
    victim = draw(_combatant(entity_id=2, name="乙"))
    if "unarmed" not in attacker.skills:
        attacker = attacker.model_copy(update={"skills": {**attacker.skills, "unarmed": 10}})
    if "dodge" not in victim.skills:
        victim = victim.model_copy(update={"skills": {**victim.skills, "dodge": 10}})
    return CombatContext(
        attacker=attacker,
        victim=victim,
        seed=draw(st.integers(min_value=0, max_value=10**6)),
        attack_type=draw(st.sampled_from([TYPE_REGULAR, TYPE_QUICK])),
    )


# ---------------------------------------------------------------------------
# ConformanceChecker 单次检查属性测试（核心）
# ---------------------------------------------------------------------------


class TestConformanceChecker:
    """hypothesis 生成 ctx -> resolve_attack -> check_conformance -> 断言无违反。"""

    @given(ctx=_combat_context())
    @settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_no_violations(self, ctx: CombatContext) -> None:
        """对任意合法 CombatContext，resolve_attack 输出不违反 do_attack 规格。"""
        result = resolve_attack(ctx)
        report = check_conformance(ctx, result)
        assert report.ok, (
            f"规格违反: {[v.model_dump() for v in report.violations]}\n"
            f"ctx={ctx.model_dump()}\nresult={result.model_dump()}"
        )

    @given(ctx=_combat_context())
    @settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_passed_checks_cover_all_implemented(self, ctx: CombatContext) -> None:
        """每次检查的 passed 应覆盖 ConformanceChecker 所有 implemented/simplified 检查项。"""
        from xkx.combat.conformance import _CHECKS

        result = resolve_attack(ctx)
        report = check_conformance(ctx, result)
        expected = {
            name
            for name, _ in _CHECKS
            if DO_ATTACK_IMPL_MAP[name].status in (ImplStatus.IMPLEMENTED, ImplStatus.SIMPLIFIED)
        }
        assert set(report.passed) == expected or report.violations, (
            f"passed={report.passed} 未覆盖 expected={expected}"
        )


# ---------------------------------------------------------------------------
# 统计性属性测试
# ---------------------------------------------------------------------------


def _fixed_attacker() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=20,
        dex_=15,
        int_=12,
        con_=14,
        combat_exp=2000,
        skills={"unarmed": 40},
        max_qi=600,
        qi=600,
        max_jingli=300,
        jingli=300,
    )


def _fixed_victim() -> CombatantSnapshot:
    return CombatantSnapshot(
        entity_id=2,
        name="乙",
        str_=15,
        dex_=20,
        int_=12,
        con_=14,
        combat_exp=1500,
        skills={"dodge": 35, "parry": 30},
        max_qi=500,
        qi=500,
        max_jingli=280,
        jingli=280,
    )


class TestStatisticalProperties:
    """确定性 / 三分支可达 / 闪避概率 / TYPE_QUICK 减半。"""

    @given(seed=st.integers(min_value=0, max_value=10**6))
    @settings(max_examples=100, deadline=None)
    def test_determinism(self, seed: int) -> None:
        """同 seed + 同快照 -> 同输出（do_attack determinism_note）。"""
        ctx = CombatContext(attacker=_fixed_attacker(), victim=_fixed_victim(), seed=seed)
        r1 = resolve_attack(ctx)
        r2 = resolve_attack(ctx)
        assert r1 == r2

    def test_three_branches_reachable(self) -> None:
        """dodge/parry/hit 三分支 seed 遍历可达。"""
        found: set[int] = set()
        for seed in range(5000):
            ctx = CombatContext(attacker=_fixed_attacker(), victim=_fixed_victim(), seed=seed)
            found.add(resolve_attack(ctx).result_code)
            if found == {RESULT_HIT, RESULT_DODGE, RESULT_PARRY}:
                break
        assert found == {RESULT_HIT, RESULT_DODGE, RESULT_PARRY}, (
            f"未覆盖: {{RESULT_HIT, RESULT_DODGE, RESULT_PARRY}} - {found}"
        )

    def test_dodge_probability_approximate(self) -> None:
        """闪避概率 ≈ dp/(ap+dp)（统计验证，容差 0.1）。"""
        attacker = _fixed_attacker()
        victim = _fixed_victim()
        ap = skill_power(attacker, "unarmed", "attack")
        dp = skill_power(victim, "dodge", "defense")
        expected_p = dp / (ap + dp)

        n = 2000
        dodge_count = 0
        for seed in range(n):
            ctx = CombatContext(attacker=attacker, victim=victim, seed=seed)
            if resolve_attack(ctx).result_code == RESULT_DODGE:
                dodge_count += 1
        actual_p = dodge_count / n
        assert abs(actual_p - expected_p) < 0.1, (
            f"闪避概率 {actual_p:.3f} 偏离期望 {expected_p:.3f}（ap={ap} dp={dp}）"
        )

    def test_parry_probability_approximate(self) -> None:
        """招架条件概率 ≈ pp/(ap+pp)（闪避失败后，统计验证，容差 0.1）。"""
        attacker = _fixed_attacker()
        victim = _fixed_victim()
        ap = skill_power(attacker, "unarmed", "attack")
        pp = skill_power(victim, "parry", "defense")
        expected_p = pp / (ap + pp)

        n = 5000
        non_dodge = 0
        parry_count = 0
        for seed in range(n):
            ctx = CombatContext(attacker=attacker, victim=victim, seed=seed)
            code = resolve_attack(ctx).result_code
            if code != RESULT_DODGE:
                non_dodge += 1
                if code == RESULT_PARRY:
                    parry_count += 1
        actual_p = parry_count / non_dodge if non_dodge else 0
        assert abs(actual_p - expected_p) < 0.1, (
            f"招架条件概率 {actual_p:.3f} 偏离期望 {expected_p:.3f}（ap={ap} pp={pp}）"
        )

    @given(ctx=_combat_context())
    @settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_ap_dp_pp_lower_bound(self, ctx: CombatContext) -> None:
        """ap/dp/pp >= 1（do_attack invariants[2]，skill_power 返回值 >= 1）。"""
        ap = skill_power(ctx.attacker, ctx.attacker.attack_skill, "attack")
        dp = skill_power(ctx.victim, "dodge", "defense")
        parry_skill = "parry" if "parry" in ctx.victim.skills else ctx.attacker.attack_skill
        pp = skill_power(ctx.victim, parry_skill, "defense")
        assert ap >= 1, f"ap={ap} < 1（attacker={ctx.attacker}）"
        assert dp >= 1, f"dp={dp} < 1（victim={ctx.victim}）"
        assert pp >= 1, f"pp={pp} < 1（victim={ctx.victim}）"

    @given(seed=st.integers(min_value=0, max_value=10**6))
    @settings(max_examples=200, deadline=None)
    def test_quick_damage_le_regular(self, seed: int) -> None:
        """TYPE_QUICK damage <= TYPE_REGULAR damage（同 seed，do_attack invariants[3]）。"""
        a = _fixed_attacker()
        v = _fixed_victim()
        ctx_reg = CombatContext(attacker=a, victim=v, seed=seed, attack_type=TYPE_REGULAR)
        ctx_quick = CombatContext(attacker=a, victim=v, seed=seed, attack_type=TYPE_QUICK)
        r_reg = resolve_attack(ctx_reg)
        r_quick = resolve_attack(ctx_quick)
        if r_reg.result_code == RESULT_HIT and r_quick.result_code == RESULT_HIT:
            assert r_quick.damage <= r_reg.damage, (
                f"QUICK dmg={r_quick.damage} > REG dmg={r_reg.damage}（seed={seed}）"
            )


# ---------------------------------------------------------------------------
# impl_map 完整性测试
# ---------------------------------------------------------------------------


class TestImplMap:
    """impl_map 注册状态覆盖 ConformanceChecker 的 8 项检查。"""

    def test_all_checks_registered(self) -> None:
        """ConformanceChecker 的 8 项检查都在 impl_map 中注册（子集关系）。"""
        from xkx.combat.conformance import _CHECKS

        registered = set(DO_ATTACK_IMPL_MAP.keys())
        checks = {name for name, _ in _CHECKS}
        assert checks <= registered, f"检查项未注册到 impl_map: {checks - registered}"

    def test_no_postponed_in_checks(self) -> None:
        """ConformanceChecker 检查的项不应有 postponed（postponed 不进检查范围）。"""
        from xkx.combat.conformance import _CHECKS

        for name, _ in _CHECKS:
            entry = DO_ATTACK_IMPL_MAP[name]
            assert entry.status != ImplStatus.POSTPONED, f"检查项 {name} 不应为 postponed"

    def test_each_entry_has_adr_ref(self) -> None:
        """每条 impl_map 条目都关联 ADR。"""
        for name, entry in DO_ATTACK_IMPL_MAP.items():
            assert entry.adr_ref, f"{name} 缺少 adr_ref"
            assert entry.adr_ref.startswith("ADR-"), f"{name} adr_ref 格式错误: {entry.adr_ref}"

    def test_simplified_entries_have_note(self) -> None:
        """simplified 状态的条目必须有 note 说明简化内容。"""
        for name, entry in DO_ATTACK_IMPL_MAP.items():
            if entry.status == ImplStatus.SIMPLIFIED:
                assert entry.note, f"simplified 条目 {name} 缺少 note"

    def test_implemented_count(self) -> None:
        """impl_map 应有 12 项 implemented + 2 项 simplified = 14 项。"""
        implemented = sum(
            1 for e in DO_ATTACK_IMPL_MAP.values() if e.status == ImplStatus.IMPLEMENTED
        )
        simplified = sum(
            1 for e in DO_ATTACK_IMPL_MAP.values() if e.status == ImplStatus.SIMPLIFIED
        )
        assert implemented == 12, f"implemented 数量 {implemented} != 12"
        assert simplified == 2, f"simplified 数量 {simplified} != 2"
