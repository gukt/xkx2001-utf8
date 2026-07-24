"""M2-08：FactionDefinition 全局注册表 + Faction 组件 + join。"""

from __future__ import annotations

from pathlib import Path

import pytest

from openmud.components import Faction
from openmud.errors import SceneLoadError
from openmud.factions import FACTIONS
from openmud.parsing import execute_line
from openmud.save import restore_world, save_world
from openmud.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_FACTIONS = """
factions:
  open_sect:
    display_name: 散人门
    skill_pool: [basic_fist]
    map_skill:
      martial: basic_fist
  night_only:
    display_name: 夜行门
    join_condition:
      predicate: is_night
    skill_pool: []
"""


class TestFactionFramework:
    def test_factions_yaml_loads_registry(self, tmp_path: Path) -> None:
        scene = (
            _FACTIONS
            + """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
"""
        )
        load_scene(_write_scene(tmp_path, scene))
        assert set(FACTIONS) == {"open_sect", "night_only"}
        assert FACTIONS["open_sect"].display_name == "散人门"
        assert "basic_fist" in FACTIONS["open_sect"].skill_pool
        assert FACTIONS["open_sect"].map_skill["martial"] == "basic_fist"

    def test_join_open_faction(self, tmp_path: Path) -> None:
        scene = (
            _FACTIONS
            + """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "join 散人门")
        assert any("加入了散人门" in line for line in lines)
        assert world.require_component(player_id, Faction).faction_id == "open_sect"

    def test_join_condition_failure_gives_reason(self, tmp_path: Path) -> None:
        scene = (
            _FACTIONS
            + """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        # 固定白天相位，避免真实时钟偶然落在夜里导致门槏误过。
        assert world.nature is not None
        for index, phase in enumerate(world.nature.phases):
            if phase.name == "day":
                world.nature.phase_index = index
                break
        lines = execute_line(world, player_id, "join 夜行门")
        assert any("无法加入" in line for line in lines)
        faction = world.get_component(player_id, Faction)
        assert faction is None or faction.faction_id != "night_only"

    def test_join_overwrites_existing_faction(self, tmp_path: Path) -> None:
        scene = (
            _FACTIONS
            + """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
  faction: open_sect
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        assert world.require_component(player_id, Faction).faction_id == "open_sect"
        # MVP：允许直接覆盖（见 join 命令注释）。把相位拨到 night 以满足门槏。
        assert world.nature is not None
        for index, phase in enumerate(world.nature.phases):
            if phase.name == "night":
                world.nature.phase_index = index
                break
        execute_line(world, player_id, "join 夜行门")
        assert world.require_component(player_id, Faction).faction_id == "night_only"

    def test_unknown_faction_ref_fails_at_load(self, tmp_path: Path) -> None:
        scene = """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
  faction: no_such_sect
"""
        with pytest.raises(SceneLoadError, match="门派"):
            load_scene(_write_scene(tmp_path, scene))

    def test_faction_survives_save_restore(self, tmp_path: Path) -> None:
        scene = (
            _FACTIONS
            + """
rooms:
  yard:
    name: 院子
    exits: {}
player:
  name: 你
  start_room: yard
  faction: open_sect
"""
        )
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        assert restored[0].require_component(restored[1], Faction).faction_id == "open_sect"
