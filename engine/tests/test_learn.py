"""M2-14：learn 命令。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import Faction, SkillLevels
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
    name: 武场
    exits: {}
factions:
  shaolin:
    display_name: 少林
    skill_pool: [luohan_quan, hunyuan]
    map_skill:
      martial: luohan_quan
      force: hunyuan
skills:
  luohan_quan:
    type: martial
    level_req: 0
    learn_condition:
      gte:
        field: con
        value: 12
    moves:
      - name: 罗汉拳
        force: 8
        dodge: 2
        damage_type: blunt
  hunyuan:
    type: force
    level_req: 0
    moves:
      - name: 混元功
        force: 0
        dodge: 0
        damage_type: none
  outsider:
    type: martial
    level_req: 0
    moves:
      - name: 外派拳
        force: 5
        dodge: 0
        damage_type: blunt
player:
  name: 你
  start_room: yard
  attributes:
    str: 10
    con: 15
    dex: 10
    int: 10
"""


class TestLearn:
    def test_no_faction(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "learn martial")
        assert any("没有门派" in line for line in lines)

    def test_unmapped_skill_type(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        lines = execute_line(world, player_id, "learn dodge")
        assert any("不会这个" in line for line in lines)

    def test_not_in_skill_pool(self, tmp_path: Path) -> None:
        # 把 map 指到池外技能
        scene = _SCENE.replace(
            "map_skill:\n      martial: luohan_quan\n      force: hunyuan",
            "map_skill:\n      martial: outsider\n      force: hunyuan",
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        execute_line(world, player_id, "join 少林")
        lines = execute_line(world, player_id, "learn martial")
        assert any("技能池" in line for line in lines)

    def test_learn_condition_failure(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        from mud_engine.components import BaseAttributes

        world.require_component(player_id, BaseAttributes).con = 8
        lines = execute_line(world, player_id, "learn martial")
        assert any("根骨" in line for line in lines)

    def test_learn_success(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        lines = execute_line(world, player_id, "learn martial")
        assert any("学会了luohan_quan" in line for line in lines)
        skills = world.require_component(player_id, SkillLevels)
        assert skills.levels["luohan_quan"].level == 1
        assert skills.levels["luohan_quan"].exp == 0

    def test_learn_duplicate(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        execute_line(world, player_id, "learn martial")
        lines = execute_line(world, player_id, "learn martial")
        assert any("已经学会" in line for line in lines)

    def test_save_restore(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        execute_line(world, player_id, "learn martial")
        save_dir = tmp_path / "save"
        save_world(world, player_id, save_dir)
        restored, rid = restore_world(save_dir)
        assert "luohan_quan" in restored.require_component(rid, SkillLevels).levels
        assert restored.require_component(rid, Faction).faction_id == "shaolin"
