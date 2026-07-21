"""M2-20：同名目标序号消歧（ask / attack）。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.components import Engaged, Identity
from mud_engine.matching import Ambiguous, IndexOutOfRange, ResolvedEntity, match_entity_target
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """
rooms:
  gate:
    name: 城门
    exits: {}
npcs:
  guard:
    name: 官兵
    in_room: gate
    count: 2
    inquiry:
      default: 闲人免进。
      weather: 天晴。
    vitals:
      qi_current: 40
      qi_max: 40
      neili_current: 0
      neili_max: 0
      jingli_current: 10
      jingli_max: 10
player:
  name: 你
  start_room: gate
  vitals:
    qi: 100
    qi_max: 100
    neili: 50
    neili_max: 50
    jingli: 50
    jingli_max: 50
"""


def _guards(world, player_id):
    found = []
    for e in sorted(world.entities_with(Identity)):
        if e == player_id:
            continue
        if world.require_component(e, Identity).name == "官兵":
            found.append(e)
    return found


class TestMatchEntityTarget:
    def test_index_picks_nth_by_entity_id(self) -> None:
        cands = [("官兵", (), 10), ("官兵", (), 20), ("官兵", (), 5)]
        r = match_entity_target("官兵 2", cands)
        assert isinstance(r, ResolvedEntity)
        assert r.entity_id == 10  # 排序后 5,10,20 → 第 2 个是 10

    def test_no_index_ambiguous(self) -> None:
        cands = [("官兵", (), 1), ("官兵", (), 2)]
        r = match_entity_target("官兵", cands)
        assert isinstance(r, Ambiguous)

    def test_index_out_of_range(self) -> None:
        cands = [("官兵", (), 1)]
        r = match_entity_target("官兵 3", cands)
        assert isinstance(r, IndexOutOfRange)


class TestAskAttackDisambiguation:
    def test_ask_with_index(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        g1, g2 = _guards(world, player_id)
        lines = execute_line(world, player_id, "ask 官兵 1 about weather")
        assert any("天晴" in line for line in lines)
        lines = execute_line(world, player_id, "ask 官兵 2 about weather")
        assert any("天晴" in line for line in lines)

    def test_ask_without_index_ambiguous(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "ask 官兵 about weather")
        assert any("不确定" in line for line in lines)

    def test_attack_index_hits_specific_entity(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        g1, g2 = _guards(world, player_id)
        execute_line(world, player_id, "attack 官兵 2")
        assert world.require_component(player_id, Engaged).opponent == g2
        # 脱离再打另一个
        from mud_engine.combat_system import clear_engagement

        clear_engagement(world, player_id, reason="disengage")
        execute_line(world, player_id, "attack 官兵 1")
        assert world.require_component(player_id, Engaged).opponent == g1

    def test_index_out_of_range_message(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "attack 官兵 9")
        assert any("第 9 个" in line for line in lines)

    def test_single_instance_index_optional(self, tmp_path: Path) -> None:
        scene = _SCENE.replace("count: 2", "count: 1")
        world, player_id = load_scene(_write_scene(tmp_path, scene))
        lines = execute_line(world, player_id, "ask 官兵 about weather")
        assert any("天晴" in line for line in lines)
        lines = execute_line(world, player_id, "ask 官兵 1 about weather")
        assert any("天晴" in line for line in lines)
