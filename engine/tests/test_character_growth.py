"""M2-05：角色成长组件 Vitals / BaseAttributes / SkillLevels + status/skills。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import BaseAttributes, SkillLevels, SkillProgress, Vitals
from mud_engine.parsing import execute_line
from mud_engine.save import restore_world, save_world
from mud_engine.scene_loader import load_scene


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
      - name: 基本拳
        force: 5
        dodge: 1
        damage_type: blunt
npcs:
  dummy:
    name: 木桩
    in_room: yard
    vitals:
      qi_current: 50
      qi_max: 50
      neili_current: 0
      neili_max: 0
      jingli_current: 20
      jingli_max: 20
    attributes:
      str: 8
      con: 12
      dex: 6
      int: 4
player:
  name: 你
  start_room: yard
  vitals:
    qi: 80
    qi_max: 100
    neili: 30
    neili_max: 50
    jingli: 40
    jingli_max: 40
  attributes:
    str_: 15
    con: 12
    dex: 14
    int_: 10
  skills:
    basic_fist:
      level: 2
      exp: 35
"""


class TestCharacterGrowthComponents:
    def test_player_and_npc_load_vitals_and_attributes(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        vitals = world.require_component(player_id, Vitals)
        assert vitals.qi_current == 80
        assert vitals.qi_max == 100
        assert vitals.neili_current == 30
        attrs = world.require_component(player_id, BaseAttributes)
        assert attrs.str_ == 15
        assert attrs.int_ == 10
        skills = world.require_component(player_id, SkillLevels)
        assert skills.levels["basic_fist"] == SkillProgress(level=2, exp=35)

    def test_status_and_skills_commands(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        status_lines = execute_line(world, player_id, "status")
        joined = "\n".join(status_lines)
        assert "气血：80/100" in joined
        assert "内力：30/50" in joined
        assert "力量：15" in joined
        assert "智力：10" in joined
        skill_lines = execute_line(world, player_id, "skills")
        assert any("basic_fist" in line and "2" in line for line in skill_lines)

    def test_status_without_components_gives_hint(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "status")
        assert any("缺少" in line or "未配置" in line for line in lines)

    def test_skills_empty_message(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
  vitals:
    qi: 10
    qi_max: 10
    neili: 0
    neili_max: 0
    jingli: 0
    jingli_max: 0
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "skills")
        assert lines == ["你还没有学会任何技能。"]

    def test_vitals_and_skills_survive_save_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        vitals = world.require_component(player_id, Vitals)
        vitals.qi_current = 12
        skills = world.require_component(player_id, SkillLevels)
        skills.levels["basic_fist"] = SkillProgress(level=3, exp=99)
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        rworld, rplayer = restored
        assert rworld.require_component(rplayer, Vitals).qi_current == 12
        assert rworld.require_component(rplayer, SkillLevels).levels["basic_fist"] == SkillProgress(
            level=3, exp=99
        )
