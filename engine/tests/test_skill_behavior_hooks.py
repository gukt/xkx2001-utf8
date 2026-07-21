"""M2-16：SkillBehavior 钩子真实接入 + 示范淬毒招式。"""

from __future__ import annotations

import random

from mud_engine.combat import CombatContext, CombatMoveSnapshot, resolve_attack
from mud_engine.skills import (
    DemoPoisonStrikeBehavior,
    clear_skill_behaviors,
    get_skill_behavior,
    register_skill_behavior,
)


def _ctx(*, skill_id: str | None = None, damage: int = 10) -> CombatContext:
    return CombatContext(
        attacker_qi_current=100,
        attacker_neili_current=50,
        attacker_str=20,
        attacker_con=10,
        attacker_dex=10,
        attacker_int=10,
        defender_qi_current=100,
        defender_neili_current=50,
        defender_str=10,
        defender_con=10,
        defender_dex=0,  # dp=0 → 必中
        defender_int=10,
        move=CombatMoveSnapshot(
            name="测试招",
            force=10,
            dodge=0,
            damage_type="blunt",
            damage=damage,
            skill_id=skill_id,
        ),
    )


class TestSkillBehaviorWiring:
    def test_no_hook_skill_unchanged(self) -> None:
        plain = resolve_attack(_ctx(skill_id=None, damage=10), random.Random(1))
        assert plain.hit is True
        assert plain.damage == 10
        assert plain.message_fragments == ("测试招命中，造成 10 点伤害",)

    def test_poison_strike_bonus_damage_and_fragment(self) -> None:
        clear_skill_behaviors()
        assert get_skill_behavior("poison_strike") is not None
        result = resolve_attack(_ctx(skill_id="poison_strike", damage=10), random.Random(1))
        assert result.hit is True
        assert result.damage == 10 + DemoPoisonStrikeBehavior.BONUS_DAMAGE
        assert any("毒素" in frag for frag in result.message_fragments)

    def test_hit_ob_str_appends_message_keeps_damage(self) -> None:
        class MsgOnly:
            def hit_ob(self, ctx: CombatContext, damage: int) -> int | str | None:
                return "额外播报"

            def hit_by(self, ctx: CombatContext) -> None:
                return None

            def post_action(self, ctx: CombatContext) -> None:
                return None

        register_skill_behavior("msg_only", MsgOnly())
        result = resolve_attack(_ctx(skill_id="msg_only", damage=7), random.Random(1))
        assert result.damage == 7
        assert "额外播报" in result.message_fragments

    def test_hit_ob_none_is_noop(self) -> None:
        class Noop:
            def hit_ob(self, ctx: CombatContext, damage: int) -> int | str | None:
                return None

            def hit_by(self, ctx: CombatContext) -> None:
                return None

            def post_action(self, ctx: CombatContext) -> None:
                return None

        register_skill_behavior("noop_hook", Noop())
        result = resolve_attack(_ctx(skill_id="noop_hook", damage=9), random.Random(1))
        assert result.damage == 9

    def test_post_action_runs_without_changing_result(self) -> None:
        calls: list[str] = []

        class Tracker:
            def hit_ob(self, ctx: CombatContext, damage: int) -> int | str | None:
                return None

            def hit_by(self, ctx: CombatContext) -> None:
                calls.append("hit_by")

            def post_action(self, ctx: CombatContext) -> None:
                calls.append("post_action")

        register_skill_behavior("tracker", Tracker())
        result = resolve_attack(_ctx(skill_id="tracker", damage=4), random.Random(1))
        assert result.damage == 4
        assert calls == ["hit_by", "post_action"]
