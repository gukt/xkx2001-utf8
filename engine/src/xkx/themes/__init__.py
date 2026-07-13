"""题材包数据层（M3-2，ADR-0031 决策 3）。

题材包具体数据（FamilyBonus / class 表）所在层。与引擎层 ``runtime/`` 分离：

- ``runtime/`` 不含武侠字面量（test_theme_neutrality 硬门禁）。
- ``themes/`` 含题材包数据（类比 ``theme.py`` 的 ``ThemeConfig.wuxia()`` 题材包
  配置数据，允许武侠字面量）。

``default_registry()`` 构造 M3 默认注册表（wuxia + default 2 题材）。

[ADR-0031](../../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md)
决策 3 /
[03 §五](../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

from xkx.runtime.theme_registry import ThemeRegistry
from xkx.themes.default import build_default_descriptor
from xkx.themes.wuxia import build_wuxia_descriptor


def default_registry() -> ThemeRegistry:
    """M3 默认注册表：wuxia 旗舰 + default 非武侠测试 2 题材。

    启动期静态加载，无运行时热插拔（04 §六不做清单）。第二题材真实存在且需
    不停服切换时才议运行时热插拔。
    """
    registry = ThemeRegistry()
    registry.register(build_wuxia_descriptor())
    registry.register(build_default_descriptor())
    return registry


__all__ = ["default_registry"]
