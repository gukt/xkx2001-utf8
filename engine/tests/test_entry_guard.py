"""M2-11：EntryGuard + EntityGateContext 门槏。"""

from __future__ import annotations

from pathlib import Path

from mud_engine.conditions import ConditionContext, Predicate, StubContext, evaluate
from mud_engine.entity_gate import EntityGateContext
from mud_engine.parsing import execute_line
from mud_engine.scene_loader import load_scene


def _write_scene(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "scene.yaml"
    path.write_text(content, encoding="utf-8")
    return path


_SCENE = """
rooms:
  gate:
    name: 山门外
    exits:
      north: temple
  temple:
    name: 山门内
    exits:
      south: gate
    entry_guard:
      condition:
        field: faction_id
        value: shaolin
      deny_message: 非少林弟子不得入内。
factions:
  shaolin:
    display_name: 少林
    skill_pool: []
items:
  sword:
    name: 钢刀
    placed_in: gate
    tags: [weapon, edged]
player:
  name: 你
  start_room: gate
"""


class TestEntityGateContextProtocol:
    def test_satisfies_condition_context(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        ctx = EntityGateContext(world, player_id)
        assert isinstance(ctx, ConditionContext)
        assert isinstance(StubContext(), ConditionContext)

    def test_edged_weapon_detection(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        # 先把钢刀捡进物品栏
        execute_line(world, player_id, "get 钢刀")
        ctx = EntityGateContext(world, player_id)
        assert ctx.is_wielding_edged_weapon is True
        assert evaluate(Predicate("is_wielding_edged_weapon"), ctx) is True


class TestEntryGuard:
    def test_deny_without_faction(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        lines = execute_line(world, player_id, "go north")
        assert any("非少林" in line for line in lines)
        # 仍在门外
        look = execute_line(world, player_id, "look")
        assert any("山门外" in line for line in look)

    def test_allow_with_faction(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        lines = execute_line(world, player_id, "go north")
        assert not any("非少林" in line for line in lines)
        look = execute_line(world, player_id, "look")
        assert any("山门内" in line for line in look)

    def test_unguarded_room_unaffected(self, tmp_path: Path) -> None:
        world, player_id = load_scene(_write_scene(tmp_path, _SCENE))
        execute_line(world, player_id, "join 少林")
        execute_line(world, player_id, "go north")
        lines = execute_line(world, player_id, "go south")
        assert any("山门外" in line for line in lines)
