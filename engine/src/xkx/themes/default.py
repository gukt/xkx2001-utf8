"""非武侠测试题材包数据（M3-2，ADR-0031 决策 3）。

default 题材用于非武侠主题无关性验证（academy / age_of_sail 2 CPK）。本模块含
非武侠 FamilyBonus（海盗帮），验证 FamilyBonus 载体主题无关性边界
（[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
决策 5 非武侠验证）。

[ADR-0031](../../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md)
决策 3
"""

from __future__ import annotations

from xkx.runtime.family import FamilyBonus
from xkx.runtime.race import HUMAN_PROFILE
from xkx.runtime.theme import ThemeConfig
from xkx.runtime.theme_registry import ThemeDescriptor

#: 海盗帮航行加成（非武侠 FamilyBonus 边界验证，ADR-0030 决策 5）。
#: ``sailing`` > 39 时按 ``navigation`` 等级加成 ``max_qi``。
PIRATE_BONUS = FamilyBonus(
    family_name="海盗帮",
    target="max_qi",
    condition_skill="sailing",
    condition_threshold=39,
    bonus_skill="navigation",
    divisor=10,
)


def build_default_descriptor() -> ThemeDescriptor:
    """构造 default 非武侠测试题材描述符。

    承载 academy / age_of_sail 2 CPK + 海盗帮 FamilyBonus（非武侠边界验证）。
    """
    return ThemeDescriptor(
        theme_id="default",
        race_profile=HUMAN_PROFILE,
        family_bonuses=[PIRATE_BONUS],
        theme_config=ThemeConfig.default(),
    )


__all__ = ["PIRATE_BONUS", "build_default_descriptor"]
