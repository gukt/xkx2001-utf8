"""Entity Inspector：开发期只读实体检视工具（ADR-0013 PRD 1）。

进程内只读模块，提供实体状态快照检视 + LPC F_DBASE 语义映射 + CLI。
阶段 1 严格只读，不修改组件，不影响 tick（[10-引擎工具链PRD-entity-inspector]
(../../../docs/xkx-arch/10-引擎工具链PRD-entity-inspector.md)）。
"""

from __future__ import annotations

import sys
from dataclasses import fields, is_dataclass
from typing import Any

from xkx.runtime import dbase_map
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
# 单一信源收敛（ADR-0025 决策 6）：LPC_KEY_MAP 从 dbase_map 派生，不再硬编码
# 重复 DBASE_KEY_MAP / PATH_PREFIX_MAP / POSTPONED_KEYS 的映射内容。仅保留
# inspector 特有的展示信息（lpc_scope / field_path 描述格式 / 代表性后置 note）。


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


# 路径前缀 key 展示信息（从 PATH_PREFIX_MAP 派生，附加 inspector 特有描述）
# lpc_scope：marks/ 为 temp（set_temp 语义），skill/ 为 dbase
# field_path：路径访问的描述格式（levels["<id>"] / flags 含 <flag>）
_PATH_PREFIX_INFO: dict[str, tuple[str, str, str]] = {
    "skill": ("dbase", 'levels["<id>"]', "路径：skill/<id> -> levels[<id>]"),
    "marks": ("temp", "flags", "路径：marks/<flag> -> flags 含 <flag>"),
}

# 代表性后置 key 的 note（仅 inspector 列出的代表性条目进 LPC_KEY_MAP，
# 其余 POSTPONED_KEYS 由 lpc_key_mapping 经 classify_key 动态判断）
_POSTPONED_NOTES: dict[str, str] = {
    "title": "后置：阶段 2 称谓系统",
    "nickname": "后置",
    "equipped": "后置：阶段 2 装备系统",
    "weight": "后置：阶段 2 F_MOVE",
    "encumbrance": "后置：阶段 2 F_MOVE",
    "channels": "后置：阶段 2 F_MESSAGE",
}


def _build_lpc_key_map() -> dict[str, LPCKeyMapping]:
    """从 dbase_map 派生 LPC_KEY_MAP（单一信源，ADR-0025 决策 6）。

    - DBASE_KEY_MAP 每个 key -> mapped 条目（component/field_path 取自映射表）
    - PATH_PREFIX_MAP 每个前缀（"skill/" "marks/"）-> 路径前缀条目（描述格式）
    - POSTPONED_KEYS 中代表性 key（_POSTPONED_NOTES）-> 后置条目（mapped=False）
    """
    result: dict[str, LPCKeyMapping] = {}
    # 已映射的简单 key（dbase_map 是单一信源）
    for key, (comp_type, field_name) in dbase_map.DBASE_KEY_MAP.items():
        result[key] = LPCKeyMapping(
            key, "dbase", comp_type, field_name, True, ""
        )
    # 路径前缀 key（前缀 + "/" 作为 LPC_KEY_MAP 的查找键，供 main/lpc_key_mapping
    # 对 skill/xxx、marks/xxx 走前缀匹配）
    for prefix, (comp_type, _field_name) in dbase_map.PATH_PREFIX_MAP.items():
        scope, field_path, note = _PATH_PREFIX_INFO[prefix]
        result[f"{prefix}/"] = LPCKeyMapping(
            f"{prefix}/", scope, comp_type, field_path, True, note
        )
    # 代表性后置 key（仅 _POSTPONED_NOTES 列出的，其余由 classify_key 动态判断）
    for key, note in _POSTPONED_NOTES.items():
        if key in result:
            # 冲突防护：DBASE_KEY_MAP 已映射的 key 不覆盖（不应发生）
            continue
        result[key] = LPCKeyMapping(key, "dbase", None, "", False, note)
    return result


LPC_KEY_MAP: dict[str, LPCKeyMapping] = _build_lpc_key_map()

# 路径前缀（skill/ marks/）：lpc_key_mapping / main 对前缀 key 动态匹配
_PATH_PREFIXES = tuple(f"{prefix}/" for prefix in dbase_map.PATH_PREFIX_MAP)


def _resolve_lpc_key_mapping(key: str) -> LPCKeyMapping:
    """解析 LPC dbase key -> LPCKeyMapping（模块级静态，无需 world）。

    复用 dbase_map.classify_key + resolve_dbase_key（ADR-0025 决策 1/6）：
    - mapped：从 DBASE_KEY_MAP / PATH_PREFIX_MAP 取 component/field_path
    - postponed：mapped=False，note 标注后置原因
    - unknown：mapped=False，note="未映射"

    供 EntityInspector.lpc_key_mapping 与 CLI main 共用，保证两路解析一致。
    """
    cls = dbase_map.classify_key(key)
    if cls == "mapped":
        comp_type, field_name = dbase_map.resolve_dbase_key(key)  # type: ignore[misc]
        # 路径前缀 key（含 "/"）用描述格式展示，简单 key 用字段名
        if "/" in key:
            prefix = key.split("/", 1)[0]
            scope, field_path, note = _PATH_PREFIX_INFO[prefix]
            return LPCKeyMapping(key, scope, comp_type, field_path, True, note)
        return LPCKeyMapping(key, "dbase", comp_type, field_name, True, "")
    if cls == "postponed":
        # 代表性后置 key 有专属 note，其余用通用后置说明
        note = _POSTPONED_NOTES.get(key, "后置：对应子系统未实现")
        return LPCKeyMapping(key, "dbase", None, "", False, note)
    return LPCKeyMapping(key, "dbase", None, "", False, "未映射")


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

        复用 dbase_map.classify_key + resolve_dbase_key（ADR-0025 决策 1/6）：
        精确匹配 + 路径前缀（skill/xxx、marks/xxx）统一走 classify_key 判定，
        不再维护 inspector 本地的映射表重复。
        """
        return _resolve_lpc_key_mapping(key)


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
        # 静态查询（无需 world 实例）：复用 classify_key 派生的映射逻辑
        key = args[1]
        m = _resolve_lpc_key_mapping(key)
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
