"""Entity Inspector：开发期只读实体检视工具（ADR-0013 PRD 1）。

进程内只读模块，提供实体状态快照检视 + LPC F_DBASE 语义映射 + CLI。
阶段 1 严格只读，不修改组件，不影响 tick（[10-引擎工具链PRD-entity-inspector]
(../../../docs/xkx-arch/10-引擎工具链PRD-entity-inspector.md)）。
"""

from __future__ import annotations

import sys
from dataclasses import fields, is_dataclass
from typing import Any

from xkx.runtime.components import (
    Attributes,
    CombatState,
    Identity,
    Inventory,
    Marks,
    NpcBehavior,
    Position,
    Progression,
    QuestLog,
    RoomComp,
    Skills,
    Vitals,
)
from xkx.runtime.ecs import World

# ---------------------------------------------------------------------------
# LPC F_DBASE key -> ECS 组件字段映射表（PRD §二.3）
# ---------------------------------------------------------------------------


class LPCKeyMapping:
    """LPC dbase key -> ECS 组件字段映射条目。

    ``mapped=False`` 表示该 key 后置/未映射（Inspector 显示 ``(unmapped)``）。
    """

    __slots__ = (
        "lpc_key",
        "lpc_scope",
        "component",
        "field_path",
        "mapped",
        "note",
    )

    def __init__(
        self,
        lpc_key: str,
        lpc_scope: str,
        component: type | None,
        field_path: str,
        mapped: bool,
        note: str = "",
    ) -> None:
        self.lpc_key = lpc_key
        self.lpc_scope = lpc_scope
        self.component = component
        self.field_path = field_path
        self.mapped = mapped
        self.note = note


# (key, scope, component, field_path, note)；mapped = component is not None
_LPC_ENTRIES: list[tuple[str, str, type | None, str, str]] = [
    ("name", "dbase", Identity, "name", ""),
    ("id", "dbase", Identity, "aliases[0]", ""),
    ("title", "dbase", None, "", "后置：阶段 2 称谓系统"),
    ("nickname", "dbase", None, "", "后置"),
    ("family", "dbase", Attributes, "family", ""),
    ("family_name", "dbase", Attributes, "family", ""),
    ("str", "dbase", Attributes, "str_", ""),
    ("dex", "dbase", Attributes, "dex_", ""),
    ("int", "dbase", Attributes, "int_", ""),
    ("con", "dbase", Attributes, "con_", ""),
    ("age", "dbase", Attributes, "age", ""),
    ("gender", "dbase", Attributes, "gender", ""),
    ("qi", "dbase", Vitals, "qi", ""),
    ("max_qi", "dbase", Vitals, "max_qi", ""),
    ("eff_qi", "dbase", Vitals, "eff_qi", ""),
    ("jing", "dbase", Vitals, "jing", ""),
    ("max_jing", "dbase", Vitals, "max_jing", ""),
    ("jingli", "dbase", Vitals, "jingli", ""),
    ("max_jingli", "dbase", Vitals, "max_jingli", ""),
    ("neili", "dbase", Vitals, "neili", ""),
    ("max_neili", "dbase", Vitals, "max_neili", ""),
    ("combat_exp", "dbase", Progression, "combat_exp", ""),
    ("potential", "dbase", Progression, "potential", ""),
    ("skill/", "dbase", Skills, 'levels["<id>"]', "路径：skill/<id> -> levels[<id>]"),
    ("apply_attack", "dbase", Skills, "apply_attack", ""),
    ("apply_dodge", "dbase", Skills, "apply_dodge", ""),
    ("apply_parry", "dbase", Skills, "apply_parry", ""),
    ("apply_damage", "dbase", Skills, "apply_damage", ""),
    ("apply_armor", "dbase", Skills, "apply_armor", ""),
    ("marks/", "temp", Marks, "flags", "路径：marks/<flag> -> flags 含 <flag>"),
    ("inquiry", "dbase", NpcBehavior, "inquiry", ""),
    ("attitude", "dbase", NpcBehavior, "attitude", ""),
    ("chat_chance_combat", "dbase", NpcBehavior, "chat_chance_combat", ""),
    ("chat_msg_combat", "dbase", NpcBehavior, "chat_msg_combat", ""),
    ("short", "dbase", RoomComp, "short", ""),
    ("long", "dbase", RoomComp, "long", ""),
    ("exits", "dbase", RoomComp, "exits", ""),
    ("outdoors", "dbase", RoomComp, "outdoors", ""),
    ("no_fight", "dbase", RoomComp, "no_fight", ""),
    ("equipped", "dbase", None, "", "后置：阶段 2 装备系统"),
    ("weight", "dbase", None, "", "后置：阶段 2 F_MOVE"),
    ("encumbrance", "dbase", None, "", "后置：阶段 2 F_MOVE"),
    ("channels", "dbase", None, "", "后置：阶段 2 F_MESSAGE"),
]

LPC_KEY_MAP: dict[str, LPCKeyMapping] = {
    key: LPCKeyMapping(key, scope, comp, field, comp is not None, note)
    for key, scope, comp, field, note in _LPC_ENTRIES
}

# 路径前缀（skill/ marks/）：lpc_key_mapping 对前缀 key 动态匹配
_PATH_PREFIXES = ("skill/", "marks/")


# ---------------------------------------------------------------------------
# 组件名 <-> 类型 映射（CLI + snapshot 用）
# ---------------------------------------------------------------------------


COMPONENT_NAMES: dict[str, type] = {
    "identity": Identity,
    "position": Position,
    "attributes": Attributes,
    "vitals": Vitals,
    "progression": Progression,
    "skills": Skills,
    "combat": CombatState,
    "npc": NpcBehavior,
    "inventory": Inventory,
    "marks": Marks,
    "quest": QuestLog,
    "room": RoomComp,
}


# ---------------------------------------------------------------------------
# 序列化辅助
# ---------------------------------------------------------------------------


def _serialize(value: Any) -> Any:
    """序列化单个值为 JSON 兼容类型（set -> sorted list）。"""
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _component_to_dict(comp: Any) -> dict[str, Any]:
    """dataclass 组件 -> dict（set 转 sorted list，保证确定性输出）。"""
    if not is_dataclass(comp):
        return {}
    return {f.name: _serialize(getattr(comp, f.name)) for f in fields(comp)}


# ---------------------------------------------------------------------------
# EntityInspector
# ---------------------------------------------------------------------------


class EntityInspector:
    """实体检视器（只读，PRD §三.2 程序化 API）。"""

    def __init__(self, world: World) -> None:
        self._world = world

    def snapshot(self, eid: int) -> dict[str, Any]:
        """返回实体全部组件的快照 dict。"""
        components: dict[str, dict[str, Any]] = {}
        for name, ct in COMPONENT_NAMES.items():
            comp = self._world.get(eid, ct)
            if comp is not None:
                components[name] = _component_to_dict(comp)
        return {"entity_id": eid, "components": components}

    def query_by_component(self, *comp_types: type) -> list[int]:
        """返回同时拥有指定组件类型的实体 id 列表。"""
        return list(self._world.entities_with(*comp_types))

    def query_by_room(self, room_id: str) -> list[int]:
        """返回指定房间内所有实体 id。"""
        return list(self._world.entities_in_room(room_id))

    def query_by_name(self, keyword: str) -> list[int]:
        """按 Identity.name 模糊匹配（包含子串）。"""
        result: list[int] = []
        for eid in self._world.entities_with(Identity):
            ident = self._world.get(eid, Identity)
            if ident and keyword in ident.name:
                result.append(eid)
        return result

    def component_snapshot(self, eid: int, comp_type: type) -> dict[str, Any] | None:
        """返回单组件快照 dict（无则 None）。"""
        comp = self._world.get(eid, comp_type)
        if comp is None:
            return None
        return _component_to_dict(comp)

    def lpc_key_mapping(self, key: str) -> LPCKeyMapping:
        """查询 LPC dbase key 对应的 ECS 组件/字段。

        精确匹配优先；skill/xxx、marks/xxx 走路径前缀匹配。
        """
        if key in LPC_KEY_MAP:
            return LPC_KEY_MAP[key]
        for prefix in _PATH_PREFIXES:
            if key.startswith(prefix):
                base = LPC_KEY_MAP[prefix]
                return LPCKeyMapping(
                    key, base.lpc_scope, base.component, base.field_path, True, base.note
                )
        return LPCKeyMapping(key, "dbase", None, "", False, "未映射")


# ---------------------------------------------------------------------------
# CLI（inspect --map <lpc_key>；实体检视需在引擎调试 shell 中调用 API）
# ---------------------------------------------------------------------------


def _format_entity_snapshot(inspector: EntityInspector, eid: int) -> str:
    """格式化实体快照为人类可读文本（PRD §三.1 输出格式）。"""
    snap = inspector.snapshot(eid)
    ident = snap["components"].get("identity", {})
    pos = snap["components"].get("position", {})
    name = ident.get("name", "?")
    tag = "[player]" if ident.get("is_player") else "[npc]"
    room = pos.get("room_id", "?")
    lines = [f"Entity #{eid}  {tag}  {name}  room: {room}"]
    for comp_name, fields_dict in snap["components"].items():
        lines.append(f"  {comp_name}:")
        for k, v in fields_dict.items():
            lines.append(f"    {k:<16} {v}")
    return "\n".join(lines)


def _format_entity_list(inspector: EntityInspector) -> str:
    """格式化实体列表（entity_id + name + tag + room）。"""
    lines = [f"  {'#eid':<6} {'name':<10} {'tag':<9} room"]
    for eid in inspector.query_by_component(Identity):
        ident = inspector._world.get(eid, Identity)  # noqa: SLF001
        pos = inspector._world.get(eid, Position)  # noqa: SLF001
        name = ident.name if ident else "?"
        tag = "[player]" if (ident and ident.is_player) else "[npc]"
        room = pos.room_id if pos else "-"
        lines.append(f"  #{eid:<5} {name:<10} {tag:<9} {room}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """inspect CLI（--map 查询 LPC 映射；实体检视需引擎 shell 调 API）。"""
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "--map":
        if len(args) < 2:
            print("用法: inspect --map <lpc_key>")
            return 1
        # 静态查询（无需 world 实例）
        key = args[1]
        if key in LPC_KEY_MAP:
            m = LPC_KEY_MAP[key]
        else:
            matched = False
            m = None
            for prefix in _PATH_PREFIXES:
                if key.startswith(prefix):
                    base = LPC_KEY_MAP[prefix]
                    m = LPCKeyMapping(
                        key, base.lpc_scope, base.component, base.field_path, True, base.note
                    )
                    matched = True
                    break
            if not matched:
                m = LPCKeyMapping(key, "dbase", None, "", False, "未映射")
        comp_name = m.component.__name__ if m.component else "(unmapped)"
        print(f"  LPC key: {m.lpc_key}")
        print(f"  Component: {comp_name}")
        print(f"  Field: {m.field_path or '(none)'}")
        print(f"  Scope: {m.lpc_scope}")
        print(f"  Mapped: {m.mapped}")
        if m.note:
            print(f"  Note: {m.note}")
        return 0
    print("用法: inspect --map <lpc_key>")
    print("  （实体检视需在引擎调试 shell 中调用 EntityInspector API）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
