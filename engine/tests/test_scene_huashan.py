"""M2-21：华山村场景内容（教程向导 + 教学木桩 + NoDeathZone）。

Seam：``load_scene(MVP)`` + ``execute_line`` / ``handle_vitals_depleted``。
"""

from __future__ import annotations

from pathlib import Path

from openmud.components import Identity, NoDeathZone, Position, Unconscious, Vitals
from openmud.death_flow import handle_vitals_depleted
from openmud.parsing import execute_line
from openmud.scenes import MVP_SCENE_PATH, load_mvp_scene
from openmud.tick import TickLoop
from openmud.world import EntityId, World


def _room_by_key(world: World, key: str) -> EntityId:
    assert world.room_ids is not None
    return world.room_ids[key]


def _npc_named(world: World, name: str, *, exclude: EntityId | None = None) -> EntityId:
    for entity in world.entities_with(Identity):
        if exclude is not None and entity == exclude:
            continue
        if world.require_component(entity, Identity).name == name:
            return entity
    raise AssertionError(f"NPC {name!r} not found")


class TestHuashanVillage:
    def test_mvp_scene_file_exists(self) -> None:
        assert Path(MVP_SCENE_PATH).is_file()

    def test_rooms_use_huashan_prefix(self) -> None:
        world, _ = load_mvp_scene()
        assert world.room_ids is not None
        huashan = [k for k in world.room_ids if k.startswith("huashan_")]
        assert set(huashan) >= {"huashan_birth", "huashan_guide", "huashan_training"}

    def test_player_starts_in_birth_room(self) -> None:
        world, player_id = load_mvp_scene()
        room = world.require_component(player_id, Position).room
        assert room == _room_by_key(world, "huashan_birth")

    def test_guide_answers_basic_topics_and_where_to_go(self) -> None:
        world, player_id = load_mvp_scene()
        execute_line(world, player_id, "go north")
        for topic, needle in (
            ("移动", "go"),
            ("查看", "look"),
            ("拾取", "get"),
            ("战斗", "attack"),
            ("去哪", "扬州"),
        ):
            lines = execute_line(world, player_id, f"ask 向导 about {topic}")
            joined = "\n".join(lines)
            assert needle in joined, f"topic={topic!r} lines={lines!r}"
        where = execute_line(world, player_id, "ask 向导 about 去哪")
        where_text = "\n".join(where)
        assert "扬州" in where_text and ("少林" in where_text or "门派" in where_text)

    def test_training_dummy_combat_broadcast(self) -> None:
        world, player_id = load_mvp_scene()
        execute_line(world, player_id, "go north")
        execute_line(world, player_id, "go east")
        dummy = _npc_named(world, "稻草人", exclude=player_id)
        assert world.has_component(dummy, Vitals)
        # 教学木桩不应反击：无 Behaviors / AIController（spawn 路径亦不挂 AI）
        from openmud.components import AIController, Behaviors

        assert not world.has_component(dummy, Behaviors)
        assert not world.has_component(dummy, AIController)

        lines = execute_line(world, player_id, "attack 稻草人")
        assert any("交战" in line for line in lines)
        before = world.require_component(dummy, Vitals).qi_current
        TickLoop(lambda: None, world=world).advance()
        after = world.require_component(dummy, Vitals).qi_current
        assert after < before
        assert any("气血" in m or "稻草人" in m for m in world.pending_messages)

    def test_training_room_is_no_death_zone(self) -> None:
        world, player_id = load_mvp_scene()
        training = _room_by_key(world, "huashan_training")
        assert world.has_component(training, NoDeathZone)
        world.require_component(player_id, Position).room = training
        vitals = world.require_component(player_id, Vitals)
        vitals.qi_current = 0
        handle_vitals_depleted(world, player_id)
        assert world.has_component(player_id, Unconscious)
        assert not any("死而复生" in m for m in world.pending_messages)

    def test_script_birth_ask_attack(self) -> None:
        """端到端片段：出生 -> ask 战斗 -> attack 木桩 -> 完整播报。"""
        world, player_id = load_mvp_scene()
        execute_line(world, player_id, "go north")
        ask = execute_line(world, player_id, "ask 向导 about 战斗")
        assert any("attack" in line or "战斗" in line for line in ask)
        execute_line(world, player_id, "go east")
        execute_line(world, player_id, "attack 稻草人")
        TickLoop(lambda: None, world=world).advance()
        assert any("气血" in m for m in world.pending_messages)
