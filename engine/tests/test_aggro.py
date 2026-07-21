"""M2-19：NPC aggro 行为——条件通过后 try_engage 同房间玩家。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import Engaged, Identity, PlayerSession
from mud_engine.scene_loader import load_scene
from mud_engine.tick import TickLoop


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """
rooms:
  wild:
    name: 野外
    exits: {}
npcs:
  wolf:
    name: 野狼
    in_room: wild
    vitals:
      qi_current: 50
      qi_max: 50
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
    behaviors:
      - kind: aggro
player:
  name: 你
  start_room: wild
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
"""


def _wolf(world, player_id):
    for e in world.entities_with(Identity):
        if e != player_id and world.require_component(e, Identity).name == "野狼":
            return e
    raise AssertionError("野狼未找到")


class TestAggroBehavior:
    def test_aggro_engages_player_without_attack_command(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        wolf = _wolf(world, player_id)
        assert not world.has_component(player_id, Engaged)
        loop = TickLoop(lambda: None, world=world)
        loop.advance()
        assert world.require_component(wolf, Engaged).opponent == player_id
        assert world.require_component(player_id, Engaged).opponent == wolf

    def test_already_engaged_player_not_re_aggroed(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        wolf = _wolf(world, player_id)
        from mud_engine.ai import spawn_from_blueprint
        from mud_engine.components import Position

        bp = world.spawners["wolf"]
        room = world.require_component(player_id, Position).room
        wolf2 = spawn_from_blueprint(world, bp, room=room)
        loop = TickLoop(lambda: None, world=world)
        loop.advance()
        engaged_wolves = [e for e in (wolf, wolf2) if world.has_component(e, Engaged)]
        assert len(engaged_wolves) == 1
        assert world.require_component(player_id, Engaged).opponent == engaged_wolves[0]
