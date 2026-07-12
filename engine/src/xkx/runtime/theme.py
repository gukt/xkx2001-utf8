"""题材包房间路径配置（阶段 2.7，ADR-0030 决策 2）。

把引擎层硬编码的题材特定房间路径外提为题材包注入，类比 ADR-0028 决策 6 class
分支表注入 + ADR-0003 武器映射外提。核心引擎（governance/death/cli）改读
``world.theme_config`` 而非模块级常量，源码不含武侠房间路径字面量（shaolin/
dali/xueshan/huashan/wudang/emei 作为路径前缀）。

**ThemeConfig** 是题材包资产载体（类比 ADR-0028 ``CLASS_TITLE_TABLE`` 题材包
数据）：

- ``ThemeConfig.default()``：非武侠测试默认配置（``test/`` 前缀路径），供
  ``build_world(theme_config=None)`` 默认注入 + 非武侠微场景验证。
- ``ThemeConfig.wuxia()``：武侠题材配置（xueshan/death/city/shaolin/dali 路径），
  由武侠题材包注入。本方法体含武侠路径是允许的（题材包配置数据，类比
  ``CLASS_TITLE_TABLE`` 题材包数据），但本模块不得含门派名（武当/少林等中文）。

**注入方式**（[world.py](world.py) ``build_world``）：``theme_config: ThemeConfig
| None = None``，``None`` 时用 ``ThemeConfig.default()``。生产路径由题材包注入
武侠配置，测试用默认或自定义非武侠配置。

[ADR-0030](../../../docs/adr/ADR-0030-family-content-pack-boundary-race-extraction.md)
决策 2 /
[ADR-0029](../../../docs/adr/ADR-0029-world-governance-system.md) 开放问题 3
（房间路径常量先例）
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ThemeConfig:
    """题材包房间路径配置（ADR-0030 决策 2）。

    引擎层接口，题材包注入。核心引擎（governance/death/cli）通过
    ``world.theme_config`` 读取房间路径，不硬编码武侠路径字面量。

    Attributes:
        start_room: 起始房间（cli.py 玩家出生点，对照 ``START_ROOM``）。
        death_room: 阴间入口（death.py die 玩家 move 目标，对照 ``DEATH_ROOM``）。
        revive_room: 还阳房间（governance.py 主路径还阳 + 黑无常活人传送 +
            隐藏路径还阳，对照 ``REVIVE_ROOM`` / ``HIDDEN_REVIVE_ROOM`` /
            ``BGARGOYLE_LIVING_TELEPORT``）。
        jail_rooms: 监狱类型 -> 释放房间映射（governance.py release_from_jail，
            对照 ``JAIL_ROOMS``，如 ``{"city_jail": "city/yamen", ...}``）。
    """

    start_room: str
    death_room: str
    revive_room: str
    jail_rooms: dict[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls) -> ThemeConfig:
        """非武侠测试默认配置（``test/`` 前缀路径）。

        供 ``build_world(theme_config=None)`` 默认注入 + 非武侠微场景验证。
        路径均用 ``test/`` 前缀（非武侠题材），确保核心引擎默认无武侠烙印。
        """
        return cls(
            start_room="test/start",
            death_room="test/death",
            revive_room="test/revive",
            jail_rooms={"city_jail": "test/yamen"},
        )

    @classmethod
    def wuxia(cls) -> ThemeConfig:
        """武侠题材配置（xueshan/death/city/shaolin/dali 路径）。

        由武侠题材包注入。本方法体含武侠房间路径是允许的（题材包配置数据，
        类比 ADR-0028 ``CLASS_TITLE_TABLE`` 题材包数据），但本模块不含门派名
        （武当/少林等中文）。
        """
        return cls(
            start_room="xueshan/shanmen",
            death_room="death/gate",
            revive_room="city/wumiao",
            jail_rooms={
                "city_jail": "city/yamen",
                "dali_jail": "dali/taihejie5",
                "bonze_jail": "shaolin/guangchang1",
            },
        )
