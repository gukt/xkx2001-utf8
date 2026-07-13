"""ThemeRegistry 静态加载（M3-2，ADR-0031 决策 3）。

启动时静态注册表（``dict[theme_id -> ThemeDescriptor]``），无运行时热插拔
（[04 §六](../../../docs/xkx-arch/04-迁移路径与避坑清单.md) 不做清单"题材包运行时
热插拔"）。M3 注册 wuxia + default 2 题材，题材包具体数据在 [xkx.themes](../themes/)
模块，本模块只提供注册机制。

**主题无关性**（[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
决策 4）：本模块源码不含门派名 / 武侠房间路径字面量。题材包具体数据（门派
FamilyBonus / class 表）由 ``xkx.themes`` 注入（题材包数据层，类比
``theme.py`` 的 ``ThemeConfig.wuxia()`` 题材包配置数据）。

[ADR-0031](../../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md)
决策 3 /
[03 §五](../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from xkx.runtime.family import FamilyBonus
from xkx.runtime.race import RaceProfile
from xkx.runtime.theme import ThemeConfig


@dataclass(frozen=True)
class ThemeDescriptor:
    """题材包描述符（03 §五）。

    题材包资产载体：题材包启动期注入引擎层。M3 由 ``xkx.themes`` 构造 wuxia /
    default 2 题材描述符注册到 ThemeRegistry。

    对照 03 §五 ThemeRegistry 每题材注册：component_schemas / condition_predicates
    / action_verbs / combat_resolver_impl / default_assets /
    themed_governance_policies。M3 简化：component_schemas 复用引擎内置（wuxia
    无额外组件）/ combat_resolver 复用 ADR-0023 CombatKernel（题材无关）/
    governance_policies 复用 ADR-0029 GovernanceSystem（平台级 fail-closed）。
    """

    theme_id: str
    race_profile: RaceProfile
    family_bonuses: list[FamilyBonus] = field(default_factory=list)
    theme_config: ThemeConfig | None = None
    # ADR-0028 class 分支表（set_class_tables 注入），M3 空闭环，全量后置 M3-1
    class_tables: dict = field(default_factory=dict)
    condition_predicates: set[str] = field(default_factory=set)
    action_verbs: set[str] = field(default_factory=set)
    governance_policies: dict = field(default_factory=dict)


class ThemeRegistry:
    """题材包静态注册表（03 §五，启动时加载）。

    ``dict[theme_id -> ThemeDescriptor]``，无运行时 unload / 版本协商 / 隔离
    （04 §六不做清单）。第二题材真实存在且需不停服切换时才议运行时热插拔。
    """

    def __init__(self) -> None:
        self._themes: dict[str, ThemeDescriptor] = {}

    def register(self, descriptor: ThemeDescriptor) -> None:
        """注册题材描述符（启动期，重复注册覆盖）。"""
        self._themes[descriptor.theme_id] = descriptor

    def get(self, theme_id: str) -> ThemeDescriptor | None:
        """查题材描述符，未注册返回 None。"""
        return self._themes.get(theme_id)

    def require(self, theme_id: str) -> ThemeDescriptor:
        """查题材描述符，未注册 raise KeyError（CPK manifest 校验用）。"""
        descriptor = self._themes.get(theme_id)
        if descriptor is None:
            raise KeyError(f"题材未注册: {theme_id}")
        return descriptor

    def __contains__(self, theme_id: str) -> bool:
        return theme_id in self._themes

    def theme_ids(self) -> list[str]:
        return list(self._themes.keys())


__all__ = ["ThemeDescriptor", "ThemeRegistry"]
