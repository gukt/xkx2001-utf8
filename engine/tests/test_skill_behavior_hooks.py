"""M2-16：SkillBehavior 钩子真实接入 + 示范淬毒招式。"""

from __future__ import annotations

import random
from pathlib import Path

from mud_engine.combat import CombatContext, CombatMoveSnapshot, attach_power_model, resolve_attack
from mud_engine.combat_system import attach_combat_system
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.skills import (
    DemoPoisonStrikeBehavior,
    clear_skill_behaviors,
    get_skill_behavior,
    register_skill_behavior,
)
from mud_engine.tick import TickLoop


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

            def hit_by(self, ctx: CombatContext) -> str | None:
                return None

            def post_action(self, ctx: CombatContext) -> str | None:
                return None

        register_skill_behavior("msg_only", MsgOnly())
        result = resolve_attack(_ctx(skill_id="msg_only", damage=7), random.Random(1))
        assert result.damage == 7
        assert "额外播报" in result.message_fragments

    def test_hit_ob_none_is_noop(self) -> None:
        class Noop:
            def hit_ob(self, ctx: CombatContext, damage: int) -> int | str | None:
                return None

            def hit_by(self, ctx: CombatContext) -> str | None:
                return None

            def post_action(self, ctx: CombatContext) -> str | None:
                return None

        register_skill_behavior("noop_hook", Noop())
        result = resolve_attack(_ctx(skill_id="noop_hook", damage=9), random.Random(1))
        assert result.damage == 9

    def test_post_action_runs_without_changing_damage(self) -> None:
        calls: list[str] = []

        class Tracker:
            def hit_ob(self, ctx: CombatContext, damage: int) -> int | str | None:
                return None

            def hit_by(self, ctx: CombatContext) -> str | None:
                calls.append("hit_by")
                return None

            def post_action(self, ctx: CombatContext) -> str | None:
                calls.append("post_action")
                return "收招余韵"

        register_skill_behavior("tracker", Tracker())
        result = resolve_attack(_ctx(skill_id="tracker", damage=4), random.Random(1))
        assert result.damage == 4
        assert calls == ["hit_by", "post_action"]
        assert "收招余韵" in result.message_fragments

    def test_resolve_attack_pure_no_cross_call_pollution(self) -> None:
        """连续两次独立调用互不污染；同输入同 RNG 结果一致。"""
        clear_skill_behaviors()
        poison = _ctx(skill_id="poison_strike", damage=10)
        plain = _ctx(skill_id=None, damage=10)

        a = resolve_attack(poison, random.Random(1))
        b = resolve_attack(plain, random.Random(1))
        c = resolve_attack(poison, random.Random(1))

        assert a == c
        assert any("毒素" in frag for frag in a.message_fragments)
        assert not any("毒素" in frag for frag in b.message_fragments)
        assert b.message_fragments == ("测试招命中，造成 10 点伤害",)


_POISON_TICK_SCENE = """
rooms:
  yard:
    name: 院子
    exits: {}
skills:
  poison_strike:
    type: martial
    level_req: 0
    moves:
      - name: 淬毒拳
        force: 30
        dodge: 0
        damage_type: blunt
        damage: 10
npcs:
  bandit:
    name: 山贼
    in_room: yard
    vitals:
      qi_current: 80
      qi_max: 80
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    attributes:
      str: 5
      con: 10
      dex: 0
      int: 5
player:
  name: 你
  start_room: yard
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
  attributes:
    str: 20
    con: 10
    dex: 0
    int: 10
  skills:
    poison_strike:
      level: 1
      exp: 0
"""


class TestSkillBehaviorViaCombatTick:
    def test_poison_hook_fires_on_real_tick_path(self, tmp_path: Path) -> None:
        """B3-4：经 attach_combat_system + TickLoop 触发 SkillBehavior，播报进 pending。"""
        clear_skill_behaviors()
        assert get_skill_behavior("poison_strike") is not None
        scene = tmp_path / "scene.yaml"
        scene.write_text(_POISON_TICK_SCENE, encoding="utf-8")
        world, player_id = load_scene(scene)
        attach_power_model(world)
        attach_combat_system(world, rng=random.Random(42))
        execute_line(world, player_id, "attack 山贼")
        world.pending_messages.clear()
        TickLoop(lambda: None, world=world).advance()
        joined = "\n".join(world.pending_messages)
        assert "毒素" in joined
        assert "淬毒拳" in joined
