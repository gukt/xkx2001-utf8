"""pilot 样本 id=12：s_combatd.c:death_penalty 迁移单元测试。

覆盖 6 项后置分支中的关键路径：userp/wizardp 门控、combat_exp 三段扣减
（amount>50 / 20<..<=5000 / <=20）、potential 扣半、death_times 递增判定、
shen 扣 1/20、behavior_exp/balance 扣半、death_count+1、vendetta/rob_victim/
initiator 删除、thief 减半、skill_death_penalty 调用。
"""

from __future__ import annotations

from typing import Any

from tools.sampling.pilot.samples.s_combatd_c_death_penalty import (
    _postponed_get,
    death_penalty,
)

from xkx.runtime.components import (
    Identity,
    Progression,
    Skills,
    TitleComp,
)
from xkx.runtime.ecs import World


def _world(
    *,
    is_player: bool = True,
    combat_exp: int = 600000,
    potential: int = 200,
    shen: int = 1000,
    behavior_exp: int = 1000,
    balance: int = 30000,
    death_times: int = 0,
    death_count: int = 0,
    thief: int = 0,
    vendetta: int = 0,
    rob_victim: int = 0,
    initiator: int = 0,
    skills: dict[str, int] | None = None,
) -> tuple[World, int]:
    """构造 1 玩家最小场景，后置 key 走样本桩 store 预置。"""
    world = World()
    victim = world.new_entity()
    world.add(victim, Identity(
        name="玩家", aliases=["player"], is_player=is_player, prototype_id="player"
    ))
    world.add(victim, Progression(
        combat_exp=combat_exp, potential=potential, max_potential=potential
    ))
    world.add(victim, TitleComp(shen=shen))
    world.add(victim, Skills(levels=dict(skills if skills is not None else {})))

    # 后置 key 预置到样本桩 store
    store = {
        "death_times": death_times,
        "death_count": death_count,
        "behavior_exp": behavior_exp,
        "balance": balance,
    }
    if thief:
        store["thief"] = thief
    if vendetta:
        store["vendetta"] = vendetta
    if rob_victim:
        store["rob_victim"] = rob_victim
    if initiator:
        store["initiator"] = initiator
    world._postponed_db = {victim: store}  # type: ignore[attr-defined]

    return world, victim


def _prog(world: World, eid: int) -> Progression:
    p = world.get(eid, Progression)
    assert p is not None
    return p


def _title(world: World, eid: int) -> TitleComp:
    t = world.get(eid, TitleComp)
    assert t is not None
    return t


def test_non_player_skipped() -> None:
    """非玩家对象不执行惩罚（L877 userp 门控）。"""
    world, victim = _world(is_player=False)
    before = _prog(world, victim).combat_exp
    death_penalty(world, victim)
    assert _prog(world, victim).combat_exp == before


def test_wizard_skipped(monkeypatch: Any) -> None:
    """巫师跳过惩罚（L879 wizardp 门控）。"""
    world, victim = _world()
    monkeypatch.setattr(
        "tools.sampling.pilot.samples.s_combatd_c_death_penalty.wizardp",
        lambda *_args, **_kw: True,
    )
    before = _prog(world, victim).combat_exp
    death_penalty(world, victim)
    assert _prog(world, victim).combat_exp == before


def test_combat_exp_branch_a_deducts_amount_and_potential_half() -> None:
    """分支 A：combat_exp>5000 -> amount=5000，扣 amount + potential 扣半。

    combat_exp=600000 -> amount=min(6000,5000)=5000 > 50 -> 扣 5000；
    potential=200 -> 扣 200//2=100，余 100。
    """
    world, victim = _world(combat_exp=600000, potential=200)
    death_penalty(world, victim)
    assert _prog(world, victim).combat_exp == 595000
    assert _prog(world, victim).potential == 100


def test_combat_exp_branch_b_deducts_fixed_20() -> None:
    """分支 B：20 < combat_exp <= 5000 -> 扣固定 20。

    combat_exp=3000 -> amount=30，不 > 50，但 combat_exp>20 -> 扣 20。
    amount=30 < 50 走 elif，combat_exp(3000)>20 扣 20。
    """
    world, victim = _world(combat_exp=3000, potential=200)
    death_penalty(world, victim)
    assert _prog(world, victim).combat_exp == 2980
    # 分支 B 不扣 potential
    assert _prog(world, victim).potential == 200


def test_combat_exp_branch_c_no_deduct() -> None:
    """分支 C：combat_exp <= 20 -> 不扣。

    combat_exp=15 -> amount=0，不 > 50，combat_exp(15) 不 > 20 -> 不扣。
    """
    world, victim = _world(combat_exp=15, potential=200)
    death_penalty(world, victim)
    assert _prog(world, victim).combat_exp == 15
    assert _prog(world, victim).potential == 200


def test_amount_capped_at_5000() -> None:
    """combat_exp//100 超 5000 截断为 5000（L887）。"""
    world, victim = _world(combat_exp=2_000_000, potential=200)
    death_penalty(world, victim)
    # amount=min(20000,5000)=5000
    assert _prog(world, victim).combat_exp == 2_000_000 - 5000


def test_potential_zero_not_deducted() -> None:
    """potential=0 时不扣（L890 if potential>0 门控）。"""
    world, victim = _world(combat_exp=600000, potential=0)
    death_penalty(world, victim)
    assert _prog(world, victim).potential == 0


def test_death_times_increment_when_exp_ge_threshold() -> None:
    """combat_exp >= 10000*death_times -> death_times+1（L882-883）。

    death_times=2 -> 阈值 20000，combat_exp=600000 >= 20000 -> 递增为 3。
    """
    world, victim = _world(combat_exp=600000, death_times=2)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "death_times") == 3


def test_death_times_not_incremented_when_exp_lt_threshold() -> None:
    """combat_exp < 10000*death_times -> 不递增。

    death_times=100 -> 阈值 1_000_000，combat_exp=600000 < 阈值 -> 不变。
    """
    world, victim = _world(combat_exp=600000, death_times=100)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "death_times") == 100


def test_shen_deducted_one_twentieth() -> None:
    """shen 扣 1/20（L884，已映射 TitleComp.shen）。shen=1000 -> 扣 50，余 950。"""
    world, victim = _world(shen=1000)
    death_penalty(world, victim)
    assert _title(world, victim).shen == 950


def test_behavior_exp_deducted_one_twentieth() -> None:
    """behavior_exp 扣 1/20（L885，后置 key）。1000 -> 扣 50，余 950。"""
    world, victim = _world(behavior_exp=1000)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "behavior_exp") == 950


def test_balance_over_10000_halved() -> None:
    """balance 超 10000 部分扣半（L896-897）。balance=30000 -> 超 20000，扣 10000。"""
    world, victim = _world(balance=30000)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "balance") == 20000


def test_balance_under_10000_not_deducted() -> None:
    """balance <= 10000 不扣（L897 if amount>0 门控）。"""
    world, victim = _world(balance=5000)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "balance") == 5000


def test_death_count_incremented() -> None:
    """death_count+1（L898）。"""
    world, victim = _world(death_count=3)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "death_count") == 4


def test_vendetta_and_temps_deleted() -> None:
    """delete vendetta / rob_victim / initiator（L899-901）。"""
    world, victim = _world(vendetta=1, rob_victim=1, initiator=1)
    death_penalty(world, victim)
    store = world._postponed_db[victim]  # type: ignore[attr-defined]
    assert "vendetta" not in store
    assert "rob_victim" not in store
    assert "initiator" not in store


def test_thief_halved() -> None:
    """thief 存在时减半（L902-903）。thief=100 -> 50。"""
    world, victim = _world(thief=100)
    death_penalty(world, victim)
    assert _postponed_get(world, victim, "thief") == 50


def test_thief_zero_not_set() -> None:
    """thief=0 时不写（L902 if thief 门控）。"""
    world, victim = _world(thief=0)
    death_penalty(world, victim)
    store = world._postponed_db[victim]  # type: ignore[attr-defined]
    assert "thief" not in store


def test_skill_death_penalty_called(monkeypatch: Any) -> None:
    """skill_death_penalty 被调用且作用技能等级（L904）。

    skills={"xueshan-sword": 10} 无 learned -> skills[sk]-- 降为 9。
    """
    world, victim = _world(skills={"xueshan-sword": 10})
    death_penalty(world, victim)
    skills = world.get(victim, Skills)
    assert skills is not None
    assert skills.levels["xueshan-sword"] == 9


def test_clear_condition_called(monkeypatch: Any) -> None:
    """clear_condition 被调用，清除 victim 的 EffectComp（L880）。"""
    from xkx.runtime.components import EffectComp

    world, victim = _world(combat_exp=600000)
    eff_eid = world.new_entity()
    world.add(eff_eid, EffectComp(
        effect_id="poison", kind="dot", target_id=victim, duration=10
    ))
    death_penalty(world, victim)
    assert world.get(eff_eid, EffectComp) is None


def test_save_invoked(monkeypatch: Any) -> None:
    """_save 被调用（L905，通过 mark_dirty/persist_now 副作用观测）。"""
    calls: list[int] = []

    class _FakeStorage:
        def mark_dirty(self, eid: int) -> None:
            calls.append(eid)

        def persist_now(self, eid: int) -> None:
            calls.append(eid)

    world, victim = _world()
    world.storage_system = _FakeStorage()  # type: ignore[attr-defined]
    death_penalty(world, victim)
    assert victim in calls
