"""技能数据地基：SkillData 全局注册表 + SkillBehavior 协议（M2-03 / spec A3/B1）。

``SKILLS`` 是顶层 ``skills:`` YAML 段填充的全局字典（不是挂在 entity 上的组件），
与未来 ``FACTIONS``（08 号票）同属"顶层声明式全局注册表"模式。角色身上的
``SkillLevels``（05 号票）只存学会了哪些技能 + 等级/经验，招式内容永远查本表。

每次 ``load_scene`` 会**清空并重建** ``SKILLS``，避免两次加载互相污染。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from mud_engine.errors import SceneLoadError

if TYPE_CHECKING:
    from mud_engine.combat import CombatContext


@dataclass(frozen=True)
class SkillMove:
    """单招只读数据。"""

    name: str
    force: int
    dodge: int
    damage_type: str
    damage: int | None = None
    lvl: int = 0
    text: str = ""


@dataclass(frozen=True)
class SkillData:
    """一条技能的声明式规格（全局注册表条目）。"""

    skill_id: str
    skill_type: str
    level_req: int
    moves: tuple[SkillMove, ...] = ()


SKILLS: dict[str, SkillData] = {}

_SKILL_BEHAVIORS: dict[str, SkillBehavior] = {}


@runtime_checkable
class SkillBehavior(Protocol):
    """可选技能钩子（多数招式只填 SkillData 数值，不实现本协议）。"""

    def hit_ob(self, ctx: CombatContext, damage: int) -> int | str | None: ...

    def hit_by(self, ctx: CombatContext) -> None: ...

    def post_action(self, ctx: CombatContext) -> None: ...


def register_skill_behavior(skill_id: str, behavior: SkillBehavior) -> None:
    """按技能 id 注册 ``SkillBehavior``（与 ``commands.register`` 同构）。"""
    _SKILL_BEHAVIORS[skill_id] = behavior


def get_skill_behavior(skill_id: str) -> SkillBehavior | None:
    """按 id 查询已注册钩子；未注册返回 None（供 16 号票消费）。"""
    return _SKILL_BEHAVIORS.get(skill_id)


def clear_skill_behaviors() -> None:
    """测试/场景重载辅助：清空行为注册表（不进存档的内存态）。"""
    _SKILL_BEHAVIORS.clear()


def load_skills_from_mapping(raw: object | None, scene_path: Path) -> dict[str, SkillData]:
    """解析 ``skills:`` 段为 ``dict[str, SkillData]``；缺省/None 返回空字典。

    结构性错误（非 mapping、缺字段、类型错）抛 ``SceneLoadError``，消息带
    文件路径与技能键（对齐 scene_loader 现有报错风格）。
    """
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的 'skills' 段应是映射，实际是 {type(raw).__name__}"
        )
    result: dict[str, SkillData] = {}
    for skill_id, entry in raw.items():
        key = str(skill_id)
        result[key] = _parse_skill(entry, key, scene_path)
    return result


def replace_skills_registry(skills: dict[str, SkillData]) -> None:
    """用新内容整体替换全局 ``SKILLS``（先 clear 再 update）。"""
    SKILLS.clear()
    SKILLS.update(skills)


def _parse_skill(raw: object, skill_id: str, scene_path: Path) -> SkillData:
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的技能 '{skill_id}' 应是映射，"
            f"实际是 {type(raw).__name__}"
        )
    skill_type = raw.get("type")
    if skill_type is None or skill_type == "":
        raise SceneLoadError(
            f"场景文件 {scene_path} 的技能 '{skill_id}' 缺少必需字段 'type'"
        )
    level_req = _require_int(raw.get("level_req", 0), "level_req", skill_id, scene_path)
    moves_raw = raw.get("moves", ())
    if not isinstance(moves_raw, (list, tuple)):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的技能 '{skill_id}' 的 'moves' 应是列表，"
            f"实际是 {type(moves_raw).__name__}"
        )
    moves = tuple(
        _parse_move(entry, skill_id, index, scene_path)
        for index, entry in enumerate(moves_raw)
    )
    return SkillData(
        skill_id=skill_id,
        skill_type=str(skill_type),
        level_req=level_req,
        moves=moves,
    )


def _parse_move(
    raw: object, skill_id: str, index: int, scene_path: Path
) -> SkillMove:
    label = f"技能 '{skill_id}' 的 moves[{index}]"
    if not isinstance(raw, Mapping):
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{label}应是映射，实际是 {type(raw).__name__}"
        )
    name = raw.get("name")
    if not name:
        raise SceneLoadError(f"场景文件 {scene_path} 的{label}缺少必需字段 'name'")
    force = _require_int(raw.get("force"), "force", skill_id, scene_path, move_index=index)
    dodge = _require_int(raw.get("dodge", 0), "dodge", skill_id, scene_path, move_index=index)
    damage_type = raw.get("damage_type", "blunt")
    damage = None
    if "damage" in raw and raw["damage"] is not None:
        damage = _require_int(raw["damage"], "damage", skill_id, scene_path, move_index=index)
    lvl = _require_int(raw.get("lvl", 0), "lvl", skill_id, scene_path, move_index=index)
    text = str(raw.get("text", "") or "")
    return SkillMove(
        name=str(name),
        force=force,
        dodge=dodge,
        damage_type=str(damage_type),
        damage=damage,
        lvl=lvl,
        text=text,
    )


def _require_int(
    raw: object,
    field: str,
    skill_id: str,
    scene_path: Path,
    *,
    move_index: int | None = None,
) -> int:
    where = f"技能 '{skill_id}'"
    if move_index is not None:
        where = f"{where} 的 moves[{move_index}]"
    if raw is None:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{where}缺少必需字段 '{field}'"
        )
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise SceneLoadError(
            f"场景文件 {scene_path} 的{where}的 '{field}' 应是数字，实际是 {raw!r}"
        ) from exc


__all__ = [
    "SKILLS",
    "SkillBehavior",
    "SkillData",
    "SkillMove",
    "clear_skill_behaviors",
    "get_skill_behavior",
    "load_skills_from_mapping",
    "register_skill_behavior",
    "replace_skills_registry",
]
