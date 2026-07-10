"""层0/层1 编译到 JSON IR（唯一真相源）。

运行时只消费 IR，与创作语法（YAML）解耦（03 §二）。

S1：IR = pydantic ``model_dump`` + ``schema_version`` 元数据。
后续加 SchemaValidator / CapabilityAuditor / ResourceBudgetChecker /
DependencyResolver 四道校验（03 §三）。

S4 ADR-0007：compile_scene 扩展 ``quests``。
"""

from __future__ import annotations

from xkx.dsl.layer0 import NpcDef, QuestDef, RoomDef

IR_SCHEMA_VERSION = 1


def compile_room(room: RoomDef) -> dict:
    return {"kind": "room", **room.model_dump()}


def compile_npc(npc: NpcDef) -> dict:
    return {"kind": "npc", **npc.model_dump()}


def compile_quest(quest: QuestDef) -> dict:
    """S4 ADR-0007：编译任务 IR。"""
    return {"kind": "quest", **quest.model_dump()}


def compile_scene(
    rooms: list[RoomDef], npcs: list[NpcDef], quests: list[QuestDef] | None = None
) -> dict:
    """编译场景 IR（房间 + NPC + 任务；层1 规则在 S1-3 并入）。"""
    return {
        "schema_version": IR_SCHEMA_VERSION,
        "rooms": [compile_room(r) for r in rooms],
        "npcs": [compile_npc(n) for n in npcs],
        "quests": [compile_quest(q) for q in (quests or [])],
    }
