"""resolve_attack 测试：确定性重放 + 三分支可达 + 副作用账本不变量。"""

from __future__ import annotations

from copy import deepcopy

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from xkx.combat.context import CombatantSnapshot, CombatContext
from xkx.combat.resolve_attack import resolve_attack
from xkx.combat.result import (
    KIND_DAMAGE,
    RESULT_DODGE,
    RESULT_HIT,
    RESULT_PARRY,
)

_VALID_CODES = {RESULT_HIT, RESULT_DODGE, RESULT_PARRY}


def _attacker() -> CombatantSnapshot:
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


def _victim() -> CombatantSnapshot:
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


def _ctx(seed: int) -> CombatContext:
    return CombatContext(attacker=_attacker(), victim=_victim(), seed=seed)


@given(seed=st.integers(min_value=0, max_value=10**6))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_deterministic_same_seed_same_output(seed: int) -> None:
    """同 seed + 同快照 -> 同输出（combat 确定性的核心）。"""
    ctx = _ctx(seed)
    r1 = resolve_attack(ctx)
    r2 = resolve_attack(ctx)
    assert r1 == r2


@given(seed=st.integers(min_value=0, max_value=10**6))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_result_code_valid(seed: int) -> None:
    ctx = _ctx(seed)
    r = resolve_attack(ctx)
    assert r.result_code in _VALID_CODES
    # dodge/parry 时无伤害
    if r.result_code != RESULT_HIT:
        assert r.damage == 0


@given(seed=st.integers(min_value=0, max_value=10**6))
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_no_mutation_of_context(seed: int) -> None:
    """resolve_attack 不得 mutate 输入快照（纯函数）。"""
    ctx = _ctx(seed)
    before = deepcopy(ctx)
    resolve_attack(ctx)
    assert ctx == before


@given(seed=st.integers(min_value=0, max_value=10**6))
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_effects_target_valid(seed: int) -> None:
    """所有 effect 的 target_id 必须是 attacker 或 victim。"""
    ctx = _ctx(seed)
    r = resolve_attack(ctx)
    valid_ids = {ctx.attacker.entity_id, ctx.victim.entity_id}
    for e in r.effects:
        assert e.target_id in valid_ids


@given(seed=st.integers(min_value=0, max_value=10**6))
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_hit_branch_has_damage_effect(seed: int) -> None:
    """命中时账本必含一条 DAMAGE effect（副作用按交织顺序入账本）。"""
    ctx = _ctx(seed)
    r = resolve_attack(ctx)
    if r.result_code == RESULT_HIT:
        damages = [e for e in r.effects if e.kind == KIND_DAMAGE]
        assert len(damages) == 1
        assert damages[0].target_id == ctx.victim.entity_id


def test_three_branches_reachable() -> None:
    """dodge/parry/hit 三分支都应可达（遍历 seed 找证据）。"""
    found: set[int] = set()
    for seed in range(2000):
        r = resolve_attack(_ctx(seed))
        found.add(r.result_code)
        if found == _VALID_CODES:
            break
    assert found == _VALID_CODES, f"未覆盖的分支: {_VALID_CODES - found}"


def test_hit_by_override() -> None:
    """hit_by 回调应覆盖最终伤害（S1: int 覆盖）。"""
    # 构造必然命中：ap 远大于 dp+pp
    a = CombatantSnapshot(
        entity_id=1,
        name="甲",
        str_=50,
        dex_=50,
        combat_exp=99999,
        skills={"unarmed": 80},
    )
    v = CombatantSnapshot(
        entity_id=2,
        name="乙",
        dex_=1,
        con_=1,
        combat_exp=0,
        skills={"dodge": 0},
        hit_by_override=42,
        max_qi=10,
        qi=10,
    )
    r = resolve_attack(CombatContext(attacker=a, victim=v, seed=0))
    assert r.result_code == RESULT_HIT
    assert r.damage == 42
