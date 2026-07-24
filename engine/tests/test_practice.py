"""M2-13：practice 命令。"""

from __future__ import annotations

from pathlib import Path

from openmud.components import SkillLevels, SkillProgress, Vitals
from openmud.parsing import execute_line
from openmud.save import restore_world, save_world
from openmud.scene_loader import load_scene


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
    practice:
      neili: 10
      jingli: 5
      exp: 15
    exp_thresholds: [30, 60]
    moves:
      - name: 直拳
        force: 5
        dodge: 0
        damage_type: blunt
player:
  name: 你
  start_room: yard
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 40
    jingli_max: 40
  skills:
    basic_fist:
      level: 0
      exp: 20
"""


class TestPractice:
    def test_unlearned_skill(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "practice unknown")
        assert any("没学会" in line for line in lines)

    def test_insufficient_resources(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        world.require_component(player_id, Vitals).neili_current = 3
        before = world.require_component(player_id, SkillLevels).levels["basic_fist"]
        lines = execute_line(world, player_id, "practice basic_fist")
        assert any("练不动" in line for line in lines)
        assert world.require_component(player_id, SkillLevels).levels["basic_fist"] == before
        assert world.require_component(player_id, Vitals).neili_current == 3

    def test_practice_gains_exp(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "practice basic_fist")
        assert any("经验" in line for line in lines)
        progress = world.require_component(player_id, SkillLevels).levels["basic_fist"]
        # 20+15=35 >= 30 → level 1, exp 结转 5
        assert progress.level == 1
        assert progress.exp == 5
        assert any("升到了" in line for line in lines)
        vitals = world.require_component(player_id, Vitals)
        assert vitals.neili_current == 40
        assert vitals.jingli_current == 35

    def test_practice_without_level_up(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        world.require_component(player_id, SkillLevels).levels["basic_fist"] = SkillProgress(
            level=0, exp=0
        )
        lines = execute_line(world, player_id, "practice basic_fist")
        progress = world.require_component(player_id, SkillLevels).levels["basic_fist"]
        assert progress.level == 0
        assert progress.exp == 15
        assert not any("升到了" in line for line in lines)

    def test_save_restore_progress(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "practice basic_fist")
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored, rid = restore_world(save_dir)
        progress = restored.require_component(rid, SkillLevels).levels["basic_fist"]
        assert progress.level == 1
        assert progress.exp == 5
