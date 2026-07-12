"""condition 系统测试（阶段 1 T1，ADR-0018）。

验证 ConditionHandler.on_tick 纯函数契约 + ConditionSystem.update apply 逻辑：
到期触发、duration 衰减、completed 移除、永久不衰减、flags 传递、多 condition 共存、
纯函数不 mutate、非均匀 tick。
"""

from __future__ import annotations

from xkx.combat.result import KIND_DAMAGE
from xkx.runtime.components import EffectComp, Vitals
from xkx.runtime.conditions import (
    CND_NO_HEAL_UP,
    ConditionHandler,
    ConditionSystem,
    ConditionTickResult,
)
from xkx.runtime.ecs import World


def _target(world: World, qi: int = 100) -> int:
    """创建被作用实体（有 Vitals）。"""
    eid = world.new_entity()
    world.add(eid, Vitals(qi=qi, max_qi=qi, eff_qi=qi))
    return eid


def _effect(
    world: World,
    target_id: int,
    *,
    effect_id: str = "e1",
    kind: str = KIND_DAMAGE,
    amount: int = 10,
    duration: int = 3,
    tick_interval: int = 1,
    next_tick: int = 0,
    flags: int = 0,
) -> int:
    """创建 effect 实体（EffectComp attach，target_id 指向被作用实体）。"""
    eid = world.new_entity()
    world.add(
        eid,
        EffectComp(
            effect_id=effect_id,
            kind=kind,
            target_id=target_id,
            amount=amount,
            duration=duration,
            tick_interval=tick_interval,
            next_tick=next_tick,
            flags=flags,
        ),
    )
    return eid


# ---- ConditionTickResult ----


def test_condition_tick_result_defaults() -> None:
    r = ConditionTickResult()
    assert r.effects == []
    assert r.messages == []
    assert r.condition_deltas == {}
    assert r.completed == []
    assert r.flags == 0
    assert r.ledger == []


# ---- ConditionHandler.on_tick 纯函数 ----


def test_on_tick_no_effects() -> None:
    """无 EffectComp 时 on_tick 返回空。"""
    w = World()
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.effects == []
    assert r.condition_deltas == {}


def test_on_tick_triggers_due() -> None:
    """到期的 EffectComp 触发 Effect。"""
    w = World()
    t = _target(w)
    _effect(w, t, amount=10, next_tick=0)
    r = ConditionHandler().on_tick(w, tick=0)
    assert len(r.effects) == 1
    assert r.effects[0].target_id == t
    assert r.effects[0].amount == 10
    assert len(r.ledger) == 1


def test_on_tick_skips_not_due() -> None:
    """未到期（next_tick > tick）的不触发。"""
    w = World()
    t = _target(w)
    _effect(w, t, next_tick=5)
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.effects == []
    assert r.condition_deltas == {}


def test_on_tick_decay_duration() -> None:
    """duration 衰减：duration=3 -> 2。"""
    w = World()
    t = _target(w)
    eff_eid = _effect(w, t, duration=3, next_tick=0)
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.condition_deltas == {eff_eid: 2}
    assert r.completed == []


def test_on_tick_completed() -> None:
    """duration 到 0 -> completed。"""
    w = World()
    t = _target(w)
    eff_eid = _effect(w, t, duration=1, next_tick=0)
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.condition_deltas == {eff_eid: 0}
    assert r.completed == [eff_eid]


def test_on_tick_permanent_no_decay() -> None:
    """duration=0 永久，不衰减不 completed，但仍触发 Effect。"""
    w = World()
    t = _target(w)
    _effect(w, t, duration=0, next_tick=0)
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.condition_deltas == {}
    assert r.completed == []
    assert len(r.effects) == 1


def test_on_tick_flags_propagate() -> None:
    """CND_NO_HEAL_UP flags 传递到 result。"""
    w = World()
    t = _target(w)
    _effect(w, t, flags=CND_NO_HEAL_UP, next_tick=0)
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.flags & CND_NO_HEAL_UP


def test_on_tick_pure_function() -> None:
    """on_tick 不 mutate world：EffectComp 的 duration/next_tick 不变。"""
    w = World()
    t = _target(w)
    _effect(w, t, duration=3, next_tick=0)
    ConditionHandler().on_tick(w, tick=0)
    eff = w.get(next(w.entities_with(EffectComp)), EffectComp)
    assert eff.duration == 3  # 未衰减（on_tick 不 mutate）
    assert eff.next_tick == 0  # 未更新（on_tick 不 mutate）


def test_on_tick_multiple_conditions_same_target() -> None:
    """一个实体多个 condition（独立 effect 实体，target_id 相同，2.2 用 effect_eid 作 key）。"""
    w = World()
    t = _target(w)
    a_eid = _effect(w, t, effect_id="cond_a", amount=5, next_tick=0)
    b_eid = _effect(w, t, effect_id="cond_b", amount=0, duration=2, next_tick=0)
    r = ConditionHandler().on_tick(w, tick=0)
    assert len(r.effects) == 1  # 只有 amount!=0 的生成 Effect
    assert r.effects[0].amount == 5
    assert set(r.condition_deltas.keys()) == {a_eid, b_eid}


# ---- ConditionSystem.update ----


def test_system_update_applies_damage() -> None:
    """ConditionSystem.update apply effects 到 Vitals。"""
    w = World()
    t = _target(w, qi=100)
    _effect(w, t, amount=10, next_tick=0)
    ConditionSystem().update(w, tick=0)
    assert w.get(t, Vitals).qi == 90


def test_system_update_removes_completed() -> None:
    """update 到期移除 EffectComp。"""
    w = World()
    t = _target(w)
    _effect(w, t, duration=1, next_tick=0)
    ConditionSystem().update(w, tick=0)
    assert list(w.entities_with(EffectComp)) == []


def test_system_update_decays_and_updates_next_tick() -> None:
    """update 衰减 duration + 更新 next_tick = tick + tick_interval。"""
    w = World()
    t = _target(w)
    _effect(w, t, duration=5, tick_interval=2, next_tick=0)
    ConditionSystem().update(w, tick=3)
    eff = w.get(next(w.entities_with(EffectComp)), EffectComp)
    assert eff.next_tick == 5  # 3 + 2
    assert eff.duration == 4  # 5 - 1


def test_system_update_non_uniform_tick() -> None:
    """非均匀 tick：next_tick=5 的在 tick=3 不触发，tick=5 触发。"""
    w = World()
    t = _target(w, qi=100)
    _effect(w, t, amount=10, next_tick=5, tick_interval=5)
    ConditionSystem().update(w, tick=3)
    assert w.get(t, Vitals).qi == 100  # 未触发
    ConditionSystem().update(w, tick=5)
    assert w.get(t, Vitals).qi == 90  # 触发扣血
