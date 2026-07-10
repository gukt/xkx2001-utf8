"""SchemaValidator 四道校验测试（S4 ADR-0008）。"""

from __future__ import annotations

from pathlib import Path

from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import load_npcs, load_quests, load_rooms
from xkx.dsl.layer1 import load_rules
from xkx.dsl.validator import SceneValidator, validate

SCENE_DIR = Path(__file__).resolve().parent.parent / "scenes" / "xueshan_micro"


def _base_ir() -> dict:
    return {"schema_version": 1, "rooms": [], "npcs": [], "quests": []}


def test_valid_xueshan_scene() -> None:
    """xueshan 场景 IR 四道校验全绿。"""
    rooms = load_rooms(SCENE_DIR / "rooms.yaml")
    npcs = load_npcs(SCENE_DIR / "npcs.yaml")
    quests = load_quests(SCENE_DIR / "quests.yaml")
    rules = load_rules(SCENE_DIR / "rules.yaml")
    ir = compile_scene(rooms, npcs, quests)
    ir["rules"] = [r.model_dump() for r in rules]
    issues = validate(ir)
    assert issues == []


def test_unknown_field_in_npc() -> None:
    """npc 含未知字段 neili（应为 max_neili）-> schema 警告。"""
    ir = _base_ir()
    ir["npcs"] = [{"id": "n1", "name": "N", "neili": 100}]  # unknown field
    issues = validate(ir)
    assert any("[schema]" in i and "neili" in i for i in issues)


def test_unknown_field_in_room() -> None:
    """room 含未知字段 -> schema 警告。"""
    ir = _base_ir()
    ir["rooms"] = [{"id": "r1", "short": "R", "long": "room", "unknown_key": 1}]
    issues = validate(ir)
    assert any("[schema]" in i and "unknown_key" in i for i in issues)


def test_capability_attack_skill_not_in_skills() -> None:
    """attack_skill 不在 skills 中 -> capability 警告。"""
    ir = _base_ir()
    ir["npcs"] = [{"id": "n1", "name": "N", "attack_skill": "blade", "skills": {"unarmed": 10}}]
    issues = validate(ir)
    assert any("[capability]" in i and "blade" in i for i in issues)


def test_resource_negative_max_qi() -> None:
    """max_qi 为负 -> resource 警告。"""
    ir = _base_ir()
    ir["npcs"] = [{"id": "n1", "name": "N", "max_qi": -10}]
    issues = validate(ir)
    assert any("[resource]" in i and "max_qi" in i for i in issues)


def test_dependency_unknown_npc_in_room() -> None:
    """room.objects 引用未知 npc -> dependency 警告。"""
    ir = _base_ir()
    ir["rooms"] = [{"id": "r1", "short": "R", "long": "room", "objects": {"unknown/npc": 1}}]
    issues = validate(ir)
    assert any("[dependency]" in i and "unknown/npc" in i for i in issues)


def test_dependency_unknown_exit() -> None:
    """room.exits 指向未知 room -> dependency 警告。"""
    ir = _base_ir()
    ir["rooms"] = [{"id": "r1", "short": "R", "long": "room", "exits": {"north": "unknown_room"}}]
    issues = validate(ir)
    assert any("[dependency]" in i and "unknown_room" in i for i in issues)


def test_dependency_unknown_quest_giver() -> None:
    """quest.giver 引用未知 npc -> dependency 警告。"""
    ir = _base_ir()
    ir["quests"] = [
        {
            "id": "q1",
            "name": "Q",
            "giver": "unknown/npc",
            "trigger": "t",
            "objective": {"kind": "give_item", "npc_id": "", "item_id": ""},
        }
    ]
    issues = validate(ir)
    assert any("[dependency]" in i and "unknown/npc" in i for i in issues)


def test_validator_class_exposes_issues() -> None:
    """SceneValidator.validate 返回问题列表；空输入返回空列表。"""
    validator = SceneValidator(_base_ir())
    assert validator.validate() == []
