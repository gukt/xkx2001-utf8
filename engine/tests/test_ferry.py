"""M2-09：渡口 Ferry + on_tick 翻转出口 + look 文案。"""

from __future__ import annotations

from pathlib import Path

from openmud.components import Exits, Ferry, Position
from openmud.ferry import attach_ferries
from openmud.parsing import execute_line
from openmud.save import restore_world, save_world
from openmud.scene_loader import load_scene
from openmud.tick import TickLoop


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_FERRY_SCENE = """
rooms:
  west_bank:
    name: 西岸渡口
    ferry:
      far_bank: east_bank
      cross_interval: 3
      direction: across
    exits: {}
  east_bank:
    name: 东岸渡口
    ferry:
      far_bank: west_bank
      cross_interval: 3
      direction: across
    exits: {}
player:
  name: 你
  start_room: west_bank
"""


class TestFerry:
    def test_initial_exit_on_bank_a_only(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _FERRY_SCENE))
        west = world.require_component(player_id, Position).room
        ferry = world.require_component(west, Ferry)
        east = ferry.far_bank
        assert "across" in world.require_component(west, Exits).by_direction
        assert "across" not in world.require_component(east, Exits).by_direction

    def test_tick_flips_exits(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _FERRY_SCENE))
        west = world.require_component(player_id, Position).room
        east = world.require_component(west, Ferry).far_bank
        loop = TickLoop(lambda: None, world=world)
        for _ in range(3):
            loop.advance()
        assert "across" not in world.require_component(west, Exits).by_direction
        assert "across" in world.require_component(east, Exits).by_direction
        for _ in range(3):
            loop.advance()
        assert "across" in world.require_component(west, Exits).by_direction
        assert "across" not in world.require_component(east, Exits).by_direction

    def test_look_shows_ferry_status(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _FERRY_SCENE))
        lines = execute_line(world, player_id, "look")
        joined = "\n".join(lines)
        assert "渡船" in joined
        assert "时辰" in joined

    def test_go_across_when_boat_present(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _FERRY_SCENE))
        lines = execute_line(world, player_id, "go across")
        assert any("东岸" in line for line in lines)
        room = world.require_component(player_id, Position).room
        assert world.require_component(room, Ferry).far_bank != room

    def test_attach_ferries_idempotent(self, tmp_path: Path) -> None:
        world, _ = load_scene(_write_scene(tmp_path, _FERRY_SCENE))
        handlers_before = list(world.events.handlers_for("on_tick"))
        attach_ferries(world)
        attach_ferries(world)
        handlers_after = list(world.events.handlers_for("on_tick"))
        # on_tick 上 ferry handler 不因重复 attach 翻倍
        assert handlers_after.count(handlers_before[-1]) == handlers_before.count(
            handlers_before[-1]
        )

    def test_restore_clears_ferries_until_reattach(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _FERRY_SCENE))
        assert world.ferries is not None
        save_world(world, player_id, tmp_path / "save")
        restored = restore_world(tmp_path / "save")
        assert restored is not None
        rworld, _ = restored
        # 存档不带 FerryState；需重新 attach（与 nature/ai 同语义）。
        assert rworld.ferries is None
        attach_ferries(rworld)
        assert rworld.ferries is not None
        assert rworld.ferries.crossings
