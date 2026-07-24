"""Pre-M4-10：柔丝索跨玩家捕获（SkillBehavior + relocate_entity）。

Seam：
- S0：直调 ``SilkRopeCaptureBehavior.hit_ob`` + 受限移动方法本体，断言 Position。
- S1：同一 World 双 ``PlayerSession`` + ``attack``/tick，断言被捕获者进目标房。
"""

from __future__ import annotations

import random
from pathlib import Path

from openmud.combat import CombatContext, CombatMoveSnapshot, attach_power_model
from openmud.combat_system import attach_combat_system, resolve_one_strike
from openmud.components import (
    BaseAttributes,
    Identity,
    PlayerSession,
    Position,
    SkillLevels,
    SkillProgress,
    Vitals,
)
from openmud.parsing import execute_line
from openmud.scene_loader import load_scene
from openmud.scenes import load_xingxiu_mechanics
from openmud.skills import (
    SilkRopeCaptureBehavior,
    SkillData,
    SkillMove,
    clear_skill_behaviors,
    get_skill_behavior,
    replace_skills_registry,
)
from openmud.tick import TickLoop
from openmud.world import EntityId, World


def _vitals() -> Vitals:
    return Vitals(
        qi_current=100,
        qi_max=100,
        neili_current=50,
        neili_max=50,
        jingli_current=50,
        jingli_max=50,
    )


def _arm_combatant(world: World, entity: EntityId, *, dex: int = 0) -> None:
    """给 ``spawn_player_session`` 产物补上交战所需组件。"""
    if world.get_component(entity, Vitals) is None:
        world.add_component(entity, _vitals())
    if world.get_component(entity, BaseAttributes) is None:
        world.add_component(entity, BaseAttributes(str_=10, con=10, dex=dex, int_=10))


def _combat_ctx(
    world: World,
    *,
    defender_id: EntityId,
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
        defender_id=defender_id,
    )


def _register_silk_skill() -> None:
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


def _two_session_yard() -> tuple[World, EntityId, EntityId, EntityId, EntityId]:
    """施法房 + 捕获房 + 双 PlayerSession；返回 world, yard, prison, capturer, victim。"""
    world = World()
    yard = world.create_entity()
    prison = world.create_entity()
    world.add_component(yard, Identity(name="柔丝庭院"))
    world.add_component(prison, Identity(name="柔丝室"))
    world.room_ids = {"silk_yard": yard, "silk_prison": prison}

    capturer = world.create_entity()
    world.add_component(capturer, Identity(name="甲"))
    world.add_component(capturer, Position(room=yard))
    world.add_component(capturer, PlayerSession())
    _arm_combatant(world, capturer, dex=10)
    world.add_component(
        capturer,
        SkillLevels(levels={"silk_rope": SkillProgress(level=1, exp=0)}),
    )
    world.primary_player_id = capturer

    victim = world.spawn_player_session(name="乙", room=yard)
    _arm_combatant(world, victim, dex=0)
    return world, yard, prison, capturer, victim


def _attack_and_tick(world: World, capturer: EntityId, victim_name: str = "乙") -> None:
    attach_power_model(world)
    attach_combat_system(world, rng=random.Random(42))
    lines = execute_line(world, capturer, f"attack {victim_name}")
    assert any("交战" in m for m in lines)
    TickLoop(lambda: None, world=world).advance()


class TestSilkRopeS0:
    def test_builtin_behavior_registered(self) -> None:
        clear_skill_behaviors()
        behavior = get_skill_behavior("silk_rope")
        assert behavior is not None
        assert isinstance(behavior, SilkRopeCaptureBehavior)

    def test_hit_ob_relocates_defender_via_method_body(self) -> None:
        clear_skill_behaviors()
        world, _yard, prison, capturer, victim = _two_session_yard()
        behavior = SilkRopeCaptureBehavior(capture_room="silk_prison")
        ctx = _combat_ctx(world, defender_id=victim)

        msg = behavior.hit_ob(ctx, damage=1)

        assert world.require_component(victim, Position).room == prison
        assert world.require_component(capturer, Position).room != prison
        assert isinstance(msg, str)
        assert "柔丝" in msg

    def test_hit_ob_without_live_refs_is_silent_noop(self) -> None:
        clear_skill_behaviors()
        behavior = SilkRopeCaptureBehavior(capture_room="silk_prison")
        ctx = CombatContext(
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
                skill_id="silk_rope",
            ),
        )
        assert behavior.hit_ob(ctx, damage=1) is None


class TestSilkRopeS1:
    def test_dual_session_capture_via_combat_strike(self) -> None:
        clear_skill_behaviors()
        _register_silk_skill()
        world, _yard, prison, capturer, victim = _two_session_yard()
        assert world.has_component(victim, PlayerSession)
        attach_power_model(world)
        attach_combat_system(world, rng=random.Random(1))

        result = resolve_one_strike(world, capturer, victim, rng=random.Random(1))
        assert result is not None
        assert result.hit is True
        assert any("柔丝" in frag for frag in result.message_fragments)
        assert world.require_component(victim, Position).room == prison
        assert world.require_component(capturer, Position).room != prison

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
        _arm_combatant(world, victim, dex=0)
        _attack_and_tick(world, capturer)

        assert world.require_component(victim, Position).room == prison
        assert world.require_component(capturer, Position).room == yard


class TestSilkRopeSlice:
    def test_slice_has_silk_rooms_and_skill(self) -> None:
        clear_skill_behaviors()
        world, player = load_xingxiu_mechanics()
        assert "silk_yard" in world.room_ids
        assert "silk_prison" in world.room_ids
        from openmud.skills import SKILLS

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
        _arm_combatant(world, victim, dex=0)
        _attack_and_tick(world, capturer)

        assert world.require_component(victim, Position).room == prison
