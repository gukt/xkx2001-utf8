"""M2-02：战斗结算核心纯函数测试（CombatContext + resolve_attack + PowerModel）。

Seam：给定 CombatContext + seeded RNG，断言 CombatRoundResult；不依赖 World/tick/命令。
"""

from __future__ import annotations

import random

from mud_engine.combat import (
    CombatContext,
    CombatMoveSnapshot,
    DefaultWuxiaPowerModel,
    attach_power_model,
    register_power_model,
    resolve_attack,
)
from mud_engine.world import World


def _ctx(
    *,
    attacker_qi: int = 100,
    defender_qi: int = 100,
    attacker_str: int = 20,
    defender_dex: int = 10,
    force: int = 10,
    dodge: int = 0,
    damage: int | None = None,
    move_name: str = "测试招式",
) -> CombatContext:
    return CombatContext(
        attacker_qi_current=attacker_qi,
        attacker_neili_current=50,
        attacker_str=attacker_str,
        attacker_con=10,
        attacker_dex=10,
        attacker_int=10,
        defender_qi_current=defender_qi,
        defender_neili_current=50,
        defender_str=10,
        defender_con=10,
        defender_dex=defender_dex,
        defender_int=10,
        move=CombatMoveSnapshot(
            name=move_name,
            force=force,
            dodge=dodge,
            damage_type="blunt",
            damage=damage,
        ),
    )


class TestResolveAttackDeterminism:
    def test_same_context_and_seed_yield_identical_results(self) -> None:
        ctx = _ctx(force=15, dodge=5, defender_dex=12)
        a = resolve_attack(ctx, random.Random(42))
        b = resolve_attack(ctx, random.Random(42))
        assert a == b


class TestDodgeAndParry:
    def test_zero_dp_always_hits(self) -> None:
        # dp=0：random(ap+0)<0 永不成立 → 必中（不闪）。
        model = DefaultWuxiaPowerModel()
        ctx = _ctx(force=10, dodge=0, defender_dex=0)
        assert model.defense_power(ctx) == 0
        for seed in range(20):
            result = resolve_attack(ctx, random.Random(seed), power_model=model)
            assert result.dodged is False
            assert result.hit is True
            assert result.damage > 0

    def test_huge_dp_always_dodges(self) -> None:
        # 极大 dodge 使 dp >> ap，闪避几乎必成。
        ctx = _ctx(force=1, dodge=10_000, defender_dex=0)
        for seed in range(20):
            result = resolve_attack(ctx, random.Random(seed))
            assert result.dodged is True
            assert result.hit is False
            assert result.damage == 0


class TestPowerModelAp:
    def test_higher_strength_raises_ap(self) -> None:
        model = DefaultWuxiaPowerModel()
        weak = _ctx(attacker_str=0, force=10)
        strong = _ctx(attacker_str=50, force=10)
        assert model.attack_power(strong) > model.attack_power(weak)

    def test_fixed_damage_move_ignores_strength_for_inflict(self) -> None:
        # 固定伤害招式：命中后伤害等于声明的 damage，不随力量缩放。
        ctx = _ctx(attacker_str=100, force=10, damage=7, defender_dex=0, dodge=0)
        result = resolve_attack(ctx, random.Random(0))
        assert result.hit is True
        assert result.damage == 7


class TestAttachPowerModel:
    def test_attach_is_idempotent_and_sets_world_field(self) -> None:
        world = World()
        custom = DefaultWuxiaPowerModel(str_factor=0.5)
        attach_power_model(world, custom)
        attach_power_model(world, custom)
        assert world.power_model is custom

    def test_register_power_model_is_alias_of_attach(self) -> None:
        world = World()
        model = DefaultWuxiaPowerModel()
        register_power_model(world, model)
        assert world.power_model is model
