"""M2-06：死亡状态机纯函数 + Unconscious/Dead/NoDeathZone 组件。"""

from __future__ import annotations

from pathlib import Path

from openmud.components import Dead, NoDeathZone, Unconscious
from openmud.death import DeathState, next_death_state
from openmud.save import restore_world, save_world
from openmud.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


class TestNextDeathState:
    def test_alive_in_no_death_zone_becomes_unconscious(self) -> None:
        assert next_death_state(DeathState.ALIVE, in_no_death_zone=True) is DeathState.UNCONSCIOUS

    def test_alive_outside_becomes_unconscious(self) -> None:
        assert next_death_state(DeathState.ALIVE, in_no_death_zone=False) is DeathState.UNCONSCIOUS

    def test_unconscious_in_no_death_zone_stays_unconscious(self) -> None:
        assert (
            next_death_state(DeathState.UNCONSCIOUS, in_no_death_zone=True)
            is DeathState.UNCONSCIOUS
        )

    def test_unconscious_outside_becomes_dead(self) -> None:
        assert next_death_state(DeathState.UNCONSCIOUS, in_no_death_zone=False) is DeathState.DEAD

    def test_not_depleted_keeps_state(self) -> None:
        assert (
            next_death_state(DeathState.ALIVE, in_no_death_zone=False, vitals_depleted=False)
            is DeathState.ALIVE
        )


class TestNoDeathZoneAndMarkers:
    def test_no_death_yaml_attaches_marker(self, tmp_path: Path) -> None:
        scene = """
rooms:
  arena:
    name: 擂台
    no_death: true
    exits: {}
player:
  name: 你
  start_room: arena
"""
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        from openmud.components import Position

        room = world.require_component(player_id, Position).room
        assert world.has_component(room, NoDeathZone)

    def test_unconscious_and_dead_survive_save_restore(self, tmp_path: Path) -> None:
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
        world.add_component(player_id, Unconscious())
        save_world(world, player_id, tmp_path / "save1")
        r1 = restore_world(tmp_path / "save1")
        assert r1 is not None
        assert r1[0].has_component(r1[1], Unconscious)

        world2, player2 = load_scene(_write_scene(tmp_path, scene))
        world2.add_component(player2, Dead())
        save_world(world2, player2, tmp_path / "save2")
        r2 = restore_world(tmp_path / "save2")
        assert r2 is not None
        assert r2[0].has_component(r2[1], Dead)
