"""HealSystem 测试（阶段 2.2，对照 LPC feature/damage.c heal_up）。

验证自然恢复 + 三层资源不变量 + water/food 门控 + 战斗状态影响 + 确定性。
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World
from xkx.runtime.heal import HealSystem, heal_up


def _make_entity(
    world: World,
    *,
    qi: int = 50,
    max_qi: int = 100,
    eff_qi: int = 100,
    jing: int = 50,
    max_jing: int = 100,
    eff_jing: int = 100,
    jingli: int = 50,
    max_jingli: int = 100,
    neili: int = 0,
    max_neili: int = 0,
    water: int = 200,
    food: int = 200,
    con: int = 20,
    str_: int = 20,
    dex_: int = 20,
    is_player: bool = True,
    fighting: bool = False,
    force: int = 0,
) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name="test", is_player=is_player))
    world.add(eid, Attributes(con_=con, str_=str_, dex_=dex_))
    world.add(
        eid,
        Vitals(
            qi=qi,
            max_qi=max_qi,
            eff_qi=eff_qi,
            jing=jing,
            max_jing=max_jing,
            eff_jing=eff_jing,
            jingli=jingli,
            max_jingli=max_jingli,
            neili=neili,
            max_neili=max_neili,
            water=water,
            food=food,
        ),
    )
    if fighting:
        world.add(eid, CombatState(is_fighting=True))
    if force:
        world.add(eid, Skills(levels={"force": force}))
    return eid


# ---- 基本恢复 ----


def test_heal_up_restores_qi_jing() -> None:
    """非战斗恢复 qi/jing（con/3 + max/10）。"""
    w = World()
    eid = _make_entity(w, qi=50, eff_qi=100, jing=50, eff_jing=100, max_jingli=100, con=30)
    flag = heal_up(w, eid)
    v = w.get(eid, Vitals)
    # qi += con/3 + max_neili/10 = 10 + 0 = 10
    assert v.qi == 60
    # jing += con/3 + max_jingli/10 = 10 + 10 = 20
    assert v.jing == 70
    assert flag > 0


def test_heal_up_fighting_slower() -> None:
    """战斗中恢复速率约 1/3（con/9 + max/30）。"""
    w = World()
    eid = _make_entity(
        w, qi=50, eff_qi=100, jing=50, eff_jing=100, max_jingli=100, con=30, fighting=True
    )
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # qi_rate = con/9 + max_neili/30 = 3 + 0 = 3
    assert v.qi == 53
    # jing_rate = con/9 + max_jingli/30 = 3 + 3 = 6
    assert v.jing == 56


def test_heal_up_clamps_to_eff() -> None:
    """jing 恢复钳位 eff_jing（jing >= eff_jing 时 jing=eff_jing + eff_jing++）。"""
    w = World()
    eid = _make_entity(w, jing=55, max_jing=100, eff_jing=60, max_jingli=100, con=30)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # jing += 20 = 75 >= 60 -> jing=60, eff_jing=61
    assert v.jing == 60
    assert v.eff_jing == 61


def test_heal_up_eff_jing_slow_recover() -> None:
    """eff_jing 只在 jing 达 eff_jing 上限后才 +1（上限 max_jing）。"""
    w = World()
    eid = _make_entity(w, jing=50, max_jing=100, eff_jing=55, max_jingli=100, con=30)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # jing += 20 = 70 >= 55 -> jing=55, eff_jing=56
    assert v.jing == 55
    assert v.eff_jing == 56


def test_heal_up_eff_jing_no_recover_below() -> None:
    """jing < eff_jing 时 eff_jing 不涨。"""
    w = World()
    eid = _make_entity(w, jing=10, max_jing=100, eff_jing=90, max_jingli=100, con=5)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # jing += con/3 + max_jingli/10 = 1 + 10 = 11 -> jing=21 < 90
    assert v.jing == 21
    assert v.eff_jing == 90


def test_heal_up_eff_jing_cap_at_max() -> None:
    """eff_jing 上限 max_jing（达 max 不再涨）。"""
    w = World()
    eid = _make_entity(w, jing=90, max_jing=100, eff_jing=100, max_jingli=100, con=30)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # jing >= eff_jing=100 但 eff_jing 不 < max_jing=100，不涨
    assert v.eff_jing == 100


# ---- water/food 门控 ----


def test_heal_up_water_food_decrement() -> None:
    """water/food 每 tick -1（>0 时）。"""
    w = World()
    eid = _make_entity(w, water=100, food=100)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    assert v.water == 99
    assert v.food == 99


def test_heal_up_player_starvation_stops() -> None:
    """玩家 water/food < 1 停止恢复（饥饿/脱水）。"""
    w = World()
    eid = _make_entity(w, qi=50, eff_qi=100, water=0, food=0, is_player=True, con=30)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    assert v.qi == 50  # 不恢复


def test_heal_up_npc_ignores_starvation() -> None:
    """NPC 不受 water/food 门控（无饥饿，恢复继续）。"""
    w = World()
    eid = _make_entity(w, qi=50, eff_qi=100, water=0, food=0, is_player=False, con=30)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    assert v.qi == 60  # NPC 恢复


# ---- jingli/neili 上限 ----


def test_heal_up_jingli_no_recover_above_max() -> None:
    """jingli >= max_jingli 时不恢复（条件 jingli < max_jingli）。"""
    w = World()
    eid = _make_entity(w, jingli=190, max_jingli=100, str_=50, dex_=50)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    assert v.jingli == 190


def test_heal_up_jingli_recovers_below_max() -> None:
    """jingli < max_jingli 时恢复（上限 max*2）。"""
    w = World()
    eid = _make_entity(w, jingli=50, max_jingli=100, str_=20, dex_=20)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # jingli += (20+20)/4 = 10 -> 60
    assert v.jingli == 60


def test_heal_up_neili_cap_max() -> None:
    """neili 上限 max_neili。"""
    w = World()
    eid = _make_entity(w, neili=90, max_neili=100, force=100)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    # neili += force/2 = 50 -> 140, 钳位 100
    assert v.neili == 100


def test_heal_up_neili_no_recover_without_max() -> None:
    """max_neili=0 时 neili 不恢复（条件 max_neili>0）。"""
    w = World()
    eid = _make_entity(w, neili=0, max_neili=0, force=100)
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    assert v.neili == 0


# ---- 确定性 ----


def test_heal_up_deterministic() -> None:
    """同输入同输出（无 random）。"""
    w1 = World()
    e1 = _make_entity(w1, qi=50, eff_qi=100, con=30)
    w2 = World()
    e2 = _make_entity(w2, qi=50, eff_qi=100, con=30)
    heal_up(w1, e1)
    heal_up(w2, e2)
    assert w1.get(e1, Vitals).qi == w2.get(e2, Vitals).qi


# ---- HealSystem tick ----


def test_heal_system_tick_all_entities() -> None:
    """HealSystem 遍历所有有 Vitals 的实体。"""
    w = World()
    e1 = _make_entity(w, qi=50, eff_qi=100, con=30)
    e2 = _make_entity(w, qi=50, eff_qi=100, con=30)
    HealSystem().update(w, tick=1)
    assert w.get(e1, Vitals).qi == 60
    assert w.get(e2, Vitals).qi == 60


# ---- hypothesis 三层不变量 ----


@given(
    max_qi=st.integers(min_value=1, max_value=500),
    eff_qi=st.integers(min_value=0, max_value=500),
    qi=st.integers(min_value=0, max_value=500),
    con=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=50)
def test_heal_up_invariant_qi_le_eff_le_max(max_qi: int, eff_qi: int, qi: int, con: int) -> None:
    """三层不变量：heal_up 后 0 <= qi <= eff_qi <= max_qi。"""
    eff_qi = min(eff_qi, max_qi)
    qi = min(qi, eff_qi)
    w = World()
    eid = _make_entity(
        w,
        qi=qi,
        max_qi=max_qi,
        eff_qi=eff_qi,
        jing=0,
        max_jing=max_qi,
        eff_jing=eff_qi,
        max_jingli=max_qi,
        water=200,
        food=200,
        con=con,
    )
    heal_up(w, eid)
    v = w.get(eid, Vitals)
    assert 0 <= v.qi <= v.eff_qi <= v.max_qi
