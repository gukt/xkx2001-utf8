"""condition 类型测试（阶段 2.2，对照 kungfu/condition/）。

验证 6 个具体 condition handler（poisoned/snake_poison/drunk/blind/killer/pker）
+ revive 苏醒 + apply/query/clear_condition 运行时函数 + 多 target 同名 condition
独立衰减（2.2 effect_eid key 演进核心）。
"""

from __future__ import annotations

from xkx.runtime.components import (
    Attributes,
    Identity,
    Marks,
    Vitals,
)
from xkx.runtime.conditions import (
    CONDITION_HANDLERS,
    ConditionHandler,
    ConditionSystem,
    apply_condition,
    clear_condition,
    clear_one_condition,
    query_condition,
)
from xkx.runtime.ecs import World


def _make_target(
    world: World,
    *,
    qi: int = 100,
    max_qi: int = 100,
    eff_qi: int = 100,
    jing: int = 100,
    max_jing: int = 100,
    eff_jing: int = 100,
    jingli: int = 100,
    max_jingli: int = 100,
    max_neili: int = 100,
    con: int = 20,
) -> int:
    eid = world.new_entity()
    world.add(eid, Identity(name="target"))
    world.add(eid, Attributes(con_=con))
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
            max_neili=max_neili,
        ),
    )
    return eid


# ---- apply/query/clear_condition ----


def test_apply_and_query_condition() -> None:
    """apply_condition 施加 + query_condition 查剩余。"""
    w = World()
    t = _make_target(w)
    assert query_condition(w, t, "killer") == 0
    apply_condition(w, t, "killer", 100)
    assert query_condition(w, t, "killer") == 100


def test_apply_condition_overrides() -> None:
    """apply_condition 直接覆盖（不叠加，对齐 LPC）。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "killer", 100)
    apply_condition(w, t, "killer", 50)
    assert query_condition(w, t, "killer") == 50


def test_apply_condition_pker_accumulate_by_caller() -> None:
    """pker 叠加由调用方手写 query+delta（对齐 LPC apply_condition 不自动叠加）。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "pker", query_condition(w, t, "pker") + 120)
    apply_condition(w, t, "pker", query_condition(w, t, "pker") + 120)
    assert query_condition(w, t, "pker") == 240


def test_clear_condition() -> None:
    """clear_condition 清除所有 condition。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "killer", 100)
    apply_condition(w, t, "pker", 120)
    clear_condition(w, t)
    assert query_condition(w, t, "killer") == 0
    assert query_condition(w, t, "pker") == 0


def test_clear_one_condition() -> None:
    """clear_one_condition 清除指定 condition，返回是否清除。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "killer", 100)
    apply_condition(w, t, "pker", 120)
    assert clear_one_condition(w, t, "killer") is True
    assert query_condition(w, t, "killer") == 0
    assert query_condition(w, t, "pker") == 120
    assert clear_one_condition(w, t, "killer") is False


def test_apply_condition_multiple_targets_same_name() -> None:
    """多 target 同名 condition 独立衰减（2.2 effect_eid key 演进核心）。

    玩家 A/B 各自中毒（两个 "killer" EffectComp），独立衰减不互相覆盖。
    """
    w = World()
    t1 = _make_target(w)
    t2 = _make_target(w)
    apply_condition(w, t1, "killer", 100)
    apply_condition(w, t2, "killer", 50)
    assert query_condition(w, t1, "killer") == 100
    assert query_condition(w, t2, "killer") == 50
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, t1, "killer") == 99
    assert query_condition(w, t2, "killer") == 49


# ---- poisoned（壳，纯衰减）----


def test_poisoned_decay() -> None:
    """poisoned 纯衰减无副作用（壳 condition）。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "poisoned", 10)
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, t, "poisoned") == 9
    assert w.get(t, Vitals).qi == 100  # 无扣血


# ---- snake_poison（DoT）----


def test_snake_poison_dot() -> None:
    """snake_poison 每 tick 扣 qi=duration//2 + wound eff_jing=duration//3。"""
    w = World()
    t = _make_target(w, qi=100, eff_jing=100, max_jing=100)
    apply_condition(w, t, "snake_poison", 10)
    ConditionSystem().update(w, tick=0)
    v = w.get(t, Vitals)
    assert v.qi == 95  # 100 - 10//2
    assert v.eff_jing == 97  # 100 - 10//3
    assert query_condition(w, t, "snake_poison") == 9


def test_snake_poison_message_by_eff_jing() -> None:
    """snake_poison 消息按 eff_jing 分档（伤情程度）。"""
    w = World()
    t = _make_target(w, eff_jing=90, max_jing=100)  # > max/2=50
    apply_condition(w, t, "snake_poison", 10)
    r = ConditionHandler().on_tick(w, tick=0)
    assert any("四肢发麻" in m for m in r.messages)


# ---- drunk（分档 debuff）----


def test_drunk_high_duration_damages_jing() -> None:
    """drunk duration > limit/2 扣 jing 10。"""
    w = World()
    t = _make_target(w, jing=100, max_neili=0, con=20)
    # limit = 3 + (20 + 0) = 23, half = 11
    apply_condition(w, t, "drunk", 20)  # 20 > 11
    ConditionSystem().update(w, tick=0)
    assert w.get(t, Vitals).jing == 90


def test_drunk_mild_tipsy_heals() -> None:
    """drunk limit/4 < duration <= limit/2 微醺加血（jing+10, qi+15）。"""
    w = World()
    t = _make_target(w, qi=50, jing=50, max_neili=0, con=20)
    # limit = 23, quarter = 5, half = 11
    apply_condition(w, t, "drunk", 8)  # 5 < 8 <= 11
    ConditionSystem().update(w, tick=0)
    v = w.get(t, Vitals)
    assert v.jing == 60  # +10
    assert v.qi == 65  # +15


# ---- blind（静默 + 到期消息）----


def test_blind_silent_decay() -> None:
    """blind 持续期间无副作用，衰减。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "blind", 5)
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, t, "blind") == 4


def test_blind_expire_message() -> None:
    """blind 到期输出视力恢复消息。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "blind", 1)  # duration<=1 触发恢复
    r = ConditionHandler().on_tick(w, tick=0)
    assert any("视力恢复" in m for m in r.messages)


# ---- killer / pker（计时器）----


def test_killer_decay() -> None:
    """killer 每 tick -1。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "killer", 100)
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, t, "killer") == 99


def test_killer_expire_message() -> None:
    """killer 到期 tell 官府不再通缉。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "killer", 1)
    r = ConditionHandler().on_tick(w, tick=0)
    assert any("官府不再通缉" in m for m in r.messages)


def test_pker_silent_decay() -> None:
    """pker 纯衰减无消息（与 killer 区别）。on_tick 纯函数不 mutate，需 update 衰减。"""
    w = World()
    t = _make_target(w)
    apply_condition(w, t, "pker", 120)
    r = ConditionHandler().on_tick(w, tick=0)
    assert r.messages == []
    assert query_condition(w, t, "pker") == 120  # on_tick 不 mutate
    ConditionSystem().update(w, tick=0)
    assert query_condition(w, t, "pker") == 119


# ---- revive（昏迷苏醒）----


def test_revive_clears_unconscious_flag() -> None:
    """revive 到期（duration<=1）清 unconscious 标记。"""
    w = World()
    t = _make_target(w)
    w.add(t, Marks(flags={"unconscious"}))
    apply_condition(w, t, "revive", 3)
    ConditionSystem().update(w, tick=0)
    # duration=3 -> 2，未到期，unconscious 保留
    assert "unconscious" in w.get(t, Marks).flags
    apply_condition(w, t, "revive", 1)  # 覆盖为 1（到期触发）
    ConditionSystem().update(w, tick=1)
    assert "unconscious" not in w.get(t, Marks).flags


# ---- handler 注册 ----


def test_condition_handlers_registered() -> None:
    """6 个 condition + revive 注册到 CONDITION_HANDLERS。"""
    expected = {
        "poisoned",
        "snake_poison",
        "drunk",
        "blind",
        "killer",
        "pker",
        "revive",
    }
    assert expected <= set(CONDITION_HANDLERS.keys())
