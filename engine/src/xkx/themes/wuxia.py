"""武侠题材包数据（M3-2，ADR-0031 决策 3）。

题材包数据层：wuxia 题材的 FamilyBonus / class 表等具体数据。本模块含武侠字面量
（武当派等），是题材包资产（类比 ``theme.py`` 的 ``ThemeConfig.wuxia()`` 题材包
配置数据），test_theme_neutrality 不扫描 ``themes/``（题材包数据层，非引擎层）。

[ADR-0031](../../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md)
决策 3 /
[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
决策 5（1-2 门派验证）
"""

from __future__ import annotations

from xkx.runtime.family import FamilyBonus
from xkx.runtime.race import HUMAN_PROFILE
from xkx.runtime.theme import ThemeConfig
from xkx.runtime.theme_registry import ThemeDescriptor

#: 武当派保气标准加成（对照 human.c 行 246-257，ADR-0030 决策 5 标准门派验证）。
#: ``taoism`` > 39 时按 ``force`` 等级加成 ``max_qi``，30 岁后年龄调整。
WUDANG_BONUS = FamilyBonus(
    family_name="武当派",
    target="max_qi",
    condition_skill="taoism",
    condition_threshold=39,
    bonus_skill="force",
    divisor=10,
)


def build_wuxia_descriptor() -> ThemeDescriptor:
    """构造 wuxia 题材描述符（M3 旗舰武侠题材）。

    M3 填 1 条武当派 FamilyBonus（ADR-0030 决策 5 标准），全量 13 门派后置
    M3-1 Wave 2。``class_tables`` M3 空闭环（机制就绪，全量武侠 class 表后置
    M3-1）。
    """
    return ThemeDescriptor(
        theme_id="wuxia",
        race_profile=HUMAN_PROFILE,
        family_bonuses=[WUDANG_BONUS],
        theme_config=ThemeConfig.wuxia(),
    )


__all__ = ["WUDANG_BONUS", "build_wuxia_descriptor"]
