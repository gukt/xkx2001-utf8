"""M2-12：交战 Engaged + attack/flee + tick 自动回合。

Seam：``execute_line``（attack/flee）+ ``TickLoop.advance``（战斗结算）。
"""

from __future__ import annotations

import random
from pathlib import Path

from mud_engine.combat import attach_power_model
from mud_engine.components import Engaged, Identity, Vitals
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene
from mud_engine.tick import TickLoop


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """
rooms:
  yard:
    name: 院子
    exits: {}
skills:
  basic_fist:
    type: martial
    level_req: 0
    moves:
      - name: 直拳
        force: 20
        dodge: 0
        damage_type: blunt
        damage: 10
npcs:
  bandit:
    name: 山贼
    in_room: yard
    vitals:
      qi_current: 40
      qi_max: 40
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    attributes:
      str: 10
      con: 10
      dex: 0
      int: 5
    skills:
      basic_fist:
        level: 1
        exp: 0
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
    basic_fist:
      level: 1
      exp: 0
"""


def _bandit_id(world, player_id):
    for entity in world.entities_with(Identity):
        if entity == player_id:
            continue
        if world.require_component(entity, Identity).name == "山贼":
            return entity
    raise AssertionError("山贼未找到")


class TestAttackCommand:
    def test_attack_establishes_bidirectional_engaged(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "attack 山贼")
        assert any("交战" in line or "攻击" in line for line in lines)
        bandit = _bandit_id(world, player_id)
        assert world.require_component(player_id, Engaged).opponent == bandit
        assert world.require_component(bandit, Engaged).opponent == player_id

    def test_kill_alias_works(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "kill 山贼")
        assert world.has_component(player_id, Engaged)

    def test_attack_missing_target(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "attack 幽灵")
        assert any("没有" in line for line in lines)
        assert not world.has_component(player_id, Engaged)

    def test_attack_while_already_engaged(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "attack 山贼")
        lines = execute_line(world, player_id, "attack 山贼")
        assert any("已经" in line or "交战" in line for line in lines)

    def test_one_vs_one_blocks_third_party(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    exits: {}
skills:
  basic_fist:
    type: martial
    level_req: 0
    moves:
      - name: 直拳
        force: 20
        dodge: 0
        damage_type: blunt
        damage: 10
npcs:
  bandit:
    name: 山贼
    in_room: yard
    vitals:
      qi_current: 40
      qi_max: 40
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    attributes:
      str: 10
      con: 10
      dex: 0
      int: 5
  thug:
    name: 恶霸
    in_room: yard
    vitals:
      qi_current: 30
      qi_max: 30
      neili_current: 0
      neili_max: 0
      jingli_current: 5
      jingli_max: 5
    attributes:
      str: 8
      con: 8
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
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        execute_line(world, player_id, "attack 山贼")
        lines = execute_line(world, player_id, "attack 恶霸")
        assert any("正在" in line or "交战" in line for line in lines)
        bandit = _bandit_id(world, player_id)
        assert world.require_component(player_id, Engaged).opponent == bandit


class TestFleeCommand:
    def test_flee_success_clears_engagement(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        from mud_engine.combat_system import attach_combat_system

        attach_combat_system(world, rng=random.Random(0))  # seed 保证成功路径可测
        # 用恒成功 rng：random() < 0.5 对 Random(1) 的首个 random 可能失败；
        # 改用显式 flee_chance=1.0 覆盖。
        attach_combat_system(world, rng=random.Random(0), flee_success_chance=1.0)
        execute_line(world, player_id, "attack 山贼")
        bandit = _bandit_id(world, player_id)
        lines = execute_line(world, player_id, "flee")
        assert any("逃" in line or "脱离" in line for line in lines)
        assert not world.has_component(player_id, Engaged)
        assert not world.has_component(bandit, Engaged)

    def test_flee_failure_takes_extra_hit(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        from mud_engine.combat_system import attach_combat_system

        attach_combat_system(world, rng=random.Random(0), flee_success_chance=0.0)
        execute_line(world, player_id, "attack 山贼")
        before = world.require_component(player_id, Vitals).qi_current
        lines = execute_line(world, player_id, "flee")
        assert any("逃" in line or "失败" in line or "没能" in line for line in lines)
        assert world.has_component(player_id, Engaged)
        assert world.require_component(player_id, Vitals).qi_current < before


class TestCombatTick:
    def test_tick_reduces_qi_deterministically(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        from mud_engine.combat_system import attach_combat_system

        attach_power_model(world)
        attach_combat_system(world, rng=random.Random(42))
        execute_line(world, player_id, "attack 山贼")
        bandit = _bandit_id(world, player_id)
        before_b = world.require_component(bandit, Vitals).qi_current
        before_p = world.require_component(player_id, Vitals).qi_current
        TickLoop(lambda: None, world=world).advance()
        after_b = world.require_component(bandit, Vitals).qi_current
        after_p = world.require_component(player_id, Vitals).qi_current
        # dex=0 + 固定伤害招式 → 双方至少一方掉血（同 seed 可复现）
        assert after_b < before_b or after_p < before_p
        assert any(
            "直拳" in m or "伤害" in m or "闪避" in m or "招架" in m for m in world.pending_messages
        )

    def test_engaged_survives_save_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "attack 山贼")
        bandit = _bandit_id(world, player_id)
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored, rid = restore_world(save_dir)
        assert restored.require_component(rid, Engaged).opponent == bandit
        assert restored.require_component(bandit, Engaged).opponent == rid
