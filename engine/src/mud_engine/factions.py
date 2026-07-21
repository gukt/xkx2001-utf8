"""门派/阵营全局注册表（M2-08 / spec E1）。

``FACTIONS`` 由顶层 ``factions:`` YAML 段填充；角色只挂轻量 ``Faction`` 组件。
写法对齐 ``skills.py``（允许重复实现，不强制抽共享 helper）。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from mud_engine.ai import condition_from_data
from mud_engine.conditions import Condition
from mud_engine.errors import SceneLoadError

FACTIONS: dict[str, FactionDefinition] = {}


@dataclass(frozen=True)
class FactionDefinition:
    """一条门派的声明式规格。"""

    faction_id: str
    display_name: str
    join_condition: Condition | None = None
    skill_pool: frozenset[str] = field(default_factory=frozenset)
    map_skill: dict[str, str] = field(default_factory=dict)


def load_factions_from_mapping(
    raw: object | None, scene_path: Path
) -> dict[str, FactionDefinition]:
    """解析 ``factions:`` 段；缺省/None 返回空字典。"""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 'factions' 段应是映射，实际是 {type(raw).__name__}"
        )
    result: dict[str, FactionDefinition] = {}
    for faction_id, entry in raw.items():
        key = str(faction_id)
        result[key] = _parse_faction(entry, key, scene_path)
    return result


def replace_factions_registry(factions: dict[str, FactionDefinition]) -> None:
    """用新内容整体替换全局 ``FACTIONS``。"""
    FACTIONS.clear()
    FACTIONS.update(factions)


def _parse_faction(raw: object, faction_id: str, scene_path: Path) -> FactionDefinition:
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的门派 '{faction_id}' 应是映射，实际是 {type(raw).__name__}"
        )
    display = raw.get("display_name") or raw.get("name") or faction_id
    join_raw = raw.get("join_condition")
    join_condition = None
    if join_raw is not None:
        if not isinstance(join_raw, Mapping):
            raise SceneLoadError(
                f"场景文件 {scene_path} 的门派 '{faction_id}' 的 "
                f"'join_condition' 应是映射，实际是 {type(join_raw).__name__}"
            )
        join_condition = condition_from_data(dict(join_raw))
    pool_raw = raw.get("skill_pool", ())
    if not isinstance(pool_raw, (list, tuple, set, frozenset)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的门派 '{faction_id}' 的 "
            f"'skill_pool' 应是列表，实际是 {type(pool_raw).__name__}"
        )
    map_raw = raw.get("map_skill", {})
    if map_raw is None:
        map_raw = {}
    if not isinstance(map_raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的门派 '{faction_id}' 的 "
            f"'map_skill' 应是映射，实际是 {type(map_raw).__name__}"
        )
    return FactionDefinition(
        faction_id=faction_id,
        display_name=str(display),
        join_condition=join_condition,
        skill_pool=frozenset(str(s) for s in pool_raw),
        map_skill={str(k): str(v) for k, v in map_raw.items()},
    )


__all__ = [
    "FACTIONS",
    "FactionDefinition",
    "load_factions_from_mapping",
    "replace_factions_registry",
]
