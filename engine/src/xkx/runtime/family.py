"""门派加成声明式载体 + apply_family_bonuses 分发函数（ADR-0030 决策 1）。

题材包 CPK 资产层：把 LPC ``human.c`` ``setup_human`` 中的门派加成分支外提为
声明式 FamilyBonus 列表，引擎层只做字符串匹配 + 公式分发，**不认识任何具体门派名**。

**主题无关性硬门禁**（ADR-0030 决策 4）：本模块源码不得含任何门派名 / 武侠技能名
字面量；``family_name`` / ``condition_skill`` / ``bonus_skill`` 全部由题材包通过
FamilyBonus 字段注入。

[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from xkx.runtime.components import Vitals
from xkx.runtime.ecs import World
from xkx.runtime.query import query, query_skill


@dataclass(frozen=True)
class FamilyBonus:
    """门派加成声明式载体（题材包 CPK 资产，ADR-0030 决策 1）。

    对照 LPC ``human.c`` ``setup_human`` 中的门派加成分支。引擎层只做
    ``family_name == bonus.family_name`` 字符串匹配 + 公式分发，不认识任何具体门派名。

    可序列化（ADR-0022）：字段全基本类型（str/int/bool/None），serialization.py
    按 dataclasses.fields 自动提取，无需额外适配。

    对照 LPC human.c：

    | 字段 | 类型 | 对照 human.c |
    |---|---|---|
    | ``family_name`` | ``str`` | ``my["family"]["family_name"] == "..."`` |
    | ``target`` | ``Literal["max_jing","max_qi"]`` | 加成目标 |
    | ``condition_skill`` | ``str`` | ``ob->query_skill("<条件技能>", 1)`` |
    | ``condition_threshold`` | ``int`` | ``> 阈值`` |
    | ``bonus_skill`` | ``str`` | ``ob->query_skill("<加成技能>")`` |
    | ``divisor`` | ``int`` | ``*(skill/除数)`` 的除数 |
    | ``age_adjusted`` | ``bool`` | 30 岁前补/30 岁后长逻辑 |
    | ``extra_condition_key`` | ``str | None`` | 额外条件 dbase key（门派特有标记） |
    | ``extra_condition_threshold`` | ``int`` | 额外条件阈值 |
    | ``extra_divisor`` | ``int | None`` | 额外条件满足时的除数 |
    """

    family_name: str
    target: Literal["max_jing", "max_qi"]
    condition_skill: str
    condition_threshold: int
    bonus_skill: str
    divisor: int = 10
    age_adjusted: bool = True
    extra_condition_key: str | None = None
    extra_condition_threshold: int = 0
    extra_divisor: int | None = None


def apply_family_bonuses(
    world: World,
    eid: int,
    family_name: str,
    bonuses: list[FamilyBonus],
) -> None:
    """门派加成分发函数（对照 human.c ``setup_human`` 门派加成分支）。

    按 ``family_name`` 过滤匹配的 FamilyBonus，对每条执行：

    1. 条件检查：``query_skill(condition_skill) > condition_threshold``
    2. 年龄调整（``age_adjusted=True`` 时）：
       - ``adjusted_age = condition_skill_level // 2``
       - ``age <= 30``: ``adjusted_age -= age``
       - ``age > 30``: ``adjusted_age -= 30``
    3. 公式计算：``bonus_amount = adjusted_age * (query_skill(bonus_skill) // divisor)``
    4. 额外条件（``extra_condition_key`` 非空时）：满足时**追加**一份用
       ``extra_divisor`` 计算的加成（对照 human.c 行 165-168：额外条件满足时
       在基础加成上追加一份用更小除数计算的加成）

    5. 应用到 ``Vitals.max_jing`` 或 ``Vitals.max_qi``

    ``adjusted_age <= 0`` 时不加成（对照 human.c ``if (xism_age > 0)`` 门控）。

    **不认识任何具体门派名**，只做 ``family_name == bonus.family_name`` 字符串匹配。
    """
    vitals = world.get(eid, Vitals)
    if vitals is None:
        return

    age = _read_age(world, eid)

    for bonus in bonuses:
        if bonus.family_name != family_name:
            continue

        # 1. 条件检查：condition_skill 等级 > threshold（对照 human.c query_skill
        # 第二参数 1 = raw 等级，用 query_skill raw=True 读 levels 原值）
        cond_level = query_skill(world, eid, bonus.condition_skill, raw=True)
        if cond_level <= bonus.condition_threshold:
            continue

        # 2. 年龄调整（human.c 行 113-115 统一逻辑）
        if bonus.age_adjusted:
            adjusted_age = cond_level // 2
            if age <= 30:
                adjusted_age -= age
            else:
                adjusted_age -= 30
        else:
            adjusted_age = cond_level // 2

        if adjusted_age <= 0:
            continue

        # 3. 公式计算（human.c 行 127：skill = xism_age * (skill/10)）
        # bonus_skill 用有效等级（human.c query_skill 无第二参数 = 有效等级）
        bonus_skill_level = query_skill(world, eid, bonus.bonus_skill)
        bonus_amount = adjusted_age * (bonus_skill_level // bonus.divisor)

        # 4. 额外条件（human.c 行 165-168 额外条件分支：满足时追加一份）
        if bonus.extra_condition_key is not None and bonus.extra_divisor is not None:
            extra_val = query(world, eid, bonus.extra_condition_key)
            if isinstance(extra_val, int) and extra_val > bonus.extra_condition_threshold:
                bonus_amount += adjusted_age * (bonus_skill_level // bonus.extra_divisor)

        # 5. 应用
        if bonus.target == "max_jing":
            vitals.max_jing += bonus_amount
        else:
            vitals.max_qi += bonus_amount


def _read_age(world: World, eid: int) -> int:
    """读实体年龄（Attributes.age）。无 Attributes 组件返回 20（成年默认）。"""
    from xkx.runtime.components import Attributes

    attrs = world.get(eid, Attributes)
    return attrs.age if attrs is not None else 20


__all__ = [
    "FamilyBonus",
    "apply_family_bonuses",
]
