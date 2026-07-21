"""M2-03：技能数据地基测试（SkillData 全局注册表 + skills: YAML + SkillBehavior）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mud_engine.errors import SceneLoadError
from mud_engine.scene_loader import load_scene
from mud_engine.skills import (
    SKILLS,
    get_skill_behavior,
    register_skill_behavior,
)


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_BASE = """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
"""

_SKILLS_A = """
skills:
  luohan_quan:
    type: martial
    level_req: 1
    moves:
      - name: 罗汉拳·起手
        force: 10
        dodge: 4
        damage_type: blunt
        text: 你摆出罗汉拳起手式。
      - name: 罗汉拳·直冲
        force: 14
        dodge: 2
        damage_type: blunt
        damage: 12
        lvl: 5
        text: 你一记罗汉直冲拳打出。
  basic_dodge:
    type: dodge
    level_req: 0
    moves:
      - name: 基本轻身
        force: 0
        dodge: 8
        damage_type: none
        text: 你身形一晃。
"""

_SKILLS_B = """
skills:
  other_fist:
    type: martial
    level_req: 3
    moves:
      - name: 别派拳法
        force: 8
        dodge: 1
        damage_type: blunt
"""


class TestSkillsYamlLoading:
    def test_loads_two_sample_skills_into_global_registry(self, tmp_path: Path) -> None:
        load_scene(_write_scene(tmp_path, _BASE + _SKILLS_A))
        assert set(SKILLS) == {"luohan_quan", "basic_dodge"}
        luohan = SKILLS["luohan_quan"]
        assert luohan.skill_type == "martial"
        assert luohan.level_req == 1
        assert len(luohan.moves) == 2
        assert luohan.moves[0].name == "罗汉拳·起手"
        assert luohan.moves[0].force == 10
        assert luohan.moves[1].damage == 12
        assert luohan.moves[1].lvl == 5

    def test_reload_replaces_skills_registry(self, tmp_path: Path) -> None:
        # 连续加载两份不同 skills: 后，SKILLS 只含第二份（避免互相污染）。
        path_a = tmp_path / "a.yaml"
        path_a.write_text(_BASE + _SKILLS_A, encoding="utf-8")
        load_scene(path_a)
        assert "luohan_quan" in SKILLS
        path_b = tmp_path / "b.yaml"
        path_b.write_text(_BASE + _SKILLS_B, encoding="utf-8")
        load_scene(path_b)
        assert set(SKILLS) == {"other_fist"}
        assert "luohan_quan" not in SKILLS

    def test_missing_skills_section_clears_registry(self, tmp_path: Path) -> None:
        path_with = tmp_path / "with.yaml"
        path_with.write_text(_BASE + _SKILLS_A, encoding="utf-8")
        load_scene(path_with)
        path_without = tmp_path / "without.yaml"
        path_without.write_text(_BASE, encoding="utf-8")
        load_scene(path_without)
        assert SKILLS == {}

    def test_force_non_numeric_raises_with_location(self, tmp_path: Path) -> None:
        bad = (
            _BASE
            + """
skills:
  broken:
    type: martial
    level_req: 1
    moves:
      - name: 坏招
        force: not-a-number
        dodge: 1
        damage_type: blunt
"""
        )
        with pytest.raises(SceneLoadError) as exc_info:
            load_scene(_write_scene(tmp_path, bad))
        msg = str(exc_info.value)
        assert "broken" in msg
        assert "force" in msg


class TestSkillBehaviorRegistry:
    def test_register_and_lookup(self) -> None:
        class _Stub:
            def hit_ob(self, ctx, damage):  # noqa: ANN001
                return damage

            def hit_by(self, ctx) -> str | None:  # noqa: ANN001
                return None

            def post_action(self, ctx) -> str | None:  # noqa: ANN001
                return None

        stub = _Stub()
        register_skill_behavior("luohan_quan", stub)
        assert get_skill_behavior("luohan_quan") is stub
        assert get_skill_behavior("missing") is None
