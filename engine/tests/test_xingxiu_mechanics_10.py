"""Pre-M4-10：柔丝索跨玩家捕获（SkillBehavior + relocate_entity）。

Seam：
- S0：直调 ``SilkRopeCaptureBehavior.hit_ob`` + 受限移动方法本体，断言 Position。
- S1：同一 World 双 ``PlayerSession`` + ``attack``/tick，断言被捕获者进目标房。
"""

from __future__ import annotations

import random
from pathlib import Path

from mud_engine.combat import CombatContext, CombatMoveSnapshot, attach_power_model
from mud_engine.combat_system import attach_combat_system, resolve_one_strike
from mud_engine.components import (
    BaseAttributes,
    Identity,
    Position,
    SkillLevels,
    SkillProgress,
    Vitals,
)
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene
from mud_engine.scenes import load_xingxiu_mechanics
from mud_engine.skills import (
    SKILLS,
    SilkRopeCaptureBehavior,
    SkillData,
    SkillMove,
    clear_skill_behaviors,
    get_skill_behavior,
    replace_skills_registry,
)
from mud_engine.tick import TickLoop
from mud_engine.world import World


def _vitals() -> Vitals:
    return Vitals(
        qi_current=100,
        qi_max=100,
        neili_current=50,
        neili_max=50,
        jingli_current=50,
        jingli_max=50,
    )


def _combat_ctx(
    world: World,
    *,
    attacker_id: int,
    defender_id: int,
    skill_id: str = "silk_rope",
) -> CombatContext:
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
        defender_dex=0,
        defender_int=10,
        move=CombatMoveSnapshot(
            name="柔丝索",
            force=30,
            dodge=0,
            damage_type="blunt",
            damage=1,
            skill_id=skill_id,
        ),
        world=world,
        attacker_id=attacker_id,
        defender_id=defender_id,
    )


def _two_room_world() -> tuple[World, int, int, int, int]:
    """施法房 + 捕获房；返回 world, yard, prison, attacker, defender。"""
    world = World()
    yard = world.create_entity()
    prison = world.create_entity()
    world.add_component(yard, Identity(name="柔丝庭院"))
    world.add_component(prison, Identity(name="柔丝室"))
    world.room_ids = {"silk_yard": yard, "silk_prison": prison}

    attacker = world.create_entity()
    world.add_component(attacker, Identity(name="甲"))
    world.add_component(attacker, Position(room=yard))
    world.add_component(attacker, _vitals())
    world.add_component(attacker, BaseAttributes(dex=0))

    defender = world.create_entity()
    world.add_component(defender, Identity(name="乙"))
    world.add_component(defender, Position(room=yard))
    world.add_component(defender, _vitals())
    world.add_component(defender, BaseAttributes(dex=0))

    world.primary_player_id = attacker
    return world, yard, prison, attacker, defender


class TestSilkRopeS0:
    def test_builtin_behavior_registered(self) -> None:
        clear_skill_behaviors()
        behavior = get_skill_behavior("silk_rope")
        assert behavior is not None
        assert isinstance(behavior, SilkRopeCaptureBehavior)

    def test_hit_ob_relocates_defender_via_method_body(self) -> None:
        clear_skill_behaviors()
        world, _yard, prison, attacker, defender = _two_room_world()
        behavior = SilkRopeCaptureBehavior(capture_room="silk_prison")
        ctx = _combat_ctx(world, attacker_id=attacker, defender_id=defender)

        msg = behavior.hit_ob(ctx, damage=1)

        assert world.require_component(defender, Position).room == prison
        assert world.require_component(attacker, Position).room != prison
        assert isinstance(msg, str)
        assert "柔丝" in msg


class TestSilkRopeS1:
    def test_dual_session_capture_via_combat_strike(self) -> None:
        clear_skill_behaviors()
        replace_skills_registry(
            {
                "silk_rope": SkillData(
                    skill_id="silk_rope",
                    skill_type="martial",
                    level_req=0,
                    moves=(
                        SkillMove(
                            name="柔丝索",
                            force=40,
                            dodge=0,
                            damage_type="blunt",
                            damage=1,
                        ),
                    ),
                )
            }
        )
        world, _yard, prison, capturer, victim = _two_room_world()
        world.add_component(
            capturer,
            SkillLevels(levels={"silk_rope": SkillProgress(level=1, exp=0)}),
        )
        attach_power_model(world)
        attach_combat_system(world, rng=random.Random(1))

        result = resolve_one_strike(world, capturer, victim, rng=random.Random(1))
        assert result is not None
        assert result.hit is True
        assert world.require_component(victim, Position).room == prison
        assert world.require_component(capturer, Position).room != prison
        assert "silk_rope" in SKILLS

    def test_dual_session_attack_command_and_tick(self, tmp_path: Path) -> None:
        clear_skill_behaviors()
        scene = tmp_path / "silk.yaml"
        scene.write_text(
            """rooms:
  silk_yard:
    name: 柔丝庭院
    exits:
      north: silk_prison
  silk_prison:
    name: 柔丝室
    exits:
      south: silk_yard
skills:
  silk_rope:
    type: martial
    level_req: 0
    moves:
    - name: 柔丝索
      force: 40
      dodge: 0
      damage_type: blunt
      damage: 1
player:
  name: 甲
  start_room: silk_yard
  skills:
    silk_rope:
      level: 1
      exp: 0
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
    dex: 10
    int: 10
""",
            encoding="utf-8",
        )
        world, capturer = load_scene(scene)
        yard = world.room_ids["silk_yard"]
        prison = world.room_ids["silk_prison"]
        victim = world.spawn_player_session(name="乙", room=yard)
        world.add_component(victim, _vitals())
        world.add_component(victim, BaseAttributes(str_=5, con=10, dex=0, int_=5))
        attach_power_model(world)
        attach_combat_system(world, rng=random.Random(42))

        lines = execute_line(world, capturer, "attack 乙")
        assert any("交战" in m for m in lines)
        TickLoop(lambda: None, world=world).advance()

        assert world.require_component(victim, Position).room == prison
        assert world.require_component(capturer, Position).room == yard


class TestSilkRopeSlice:
    def test_slice_has_silk_rooms_and_skill(self) -> None:
        clear_skill_behaviors()
        world, player = load_xingxiu_mechanics()
        assert "silk_yard" in world.room_ids
        assert "silk_prison" in world.room_ids
        from mud_engine.skills import SKILLS

        assert "silk_rope" in SKILLS
        levels = world.require_component(player, SkillLevels)
        assert "silk_rope" in levels.levels

    def test_slice_dual_session_playable(self) -> None:
        clear_skill_behaviors()
        world, capturer = load_xingxiu_mechanics()
        yard = world.room_ids["silk_yard"]
        prison = world.room_ids["silk_prison"]
        # 主会话默认 dig_base；搬到柔丝庭院再捕获
        world.require_component(capturer, Position).room = yard
        victim = world.spawn_player_session(name="乙", room=yard)
        world.add_component(victim, _vitals())
        world.add_component(victim, BaseAttributes(str_=5, con=10, dex=0, int_=5))
        attach_power_model(world)
        attach_combat_system(world, rng=random.Random(7))

        execute_line(world, capturer, "attack 乙")
        TickLoop(lambda: None, world=world).advance()

        assert world.require_component(victim, Position).room == prison
