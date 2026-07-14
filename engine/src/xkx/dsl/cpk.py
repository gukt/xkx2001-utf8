"""CPK manifest 数据模型（M3-2，ADR-0031 决策 1）。

对齐 [03 §四](../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md) CPK manifest 结构，
M3 范围简化（provenance / market / resource_quota 后置）。

**module_pack vs ugc**（03 §五三层粒度）：

- ``module_pack``（受信任开发者，StdLib 级）：进程级无沙箱 Python，
  ``capabilities_required`` / ``resource_quota`` 不强制（信任）。M3 全部 CPK 是
  module_pack（官方 StdLib）。
- ``ugc``（创作者，沙箱）：RestrictedPython 受限，``capabilities_required`` /
  ``resource_quota`` 强制。后置 Wave 3 / M3 后。

**Provenance 简化**（03 §四硬约束 4 + 用户决策 5）：M3 开发期只用 ``version`` +
``author`` 简单署名；全量 provenance（``content_hash`` blake3 / ``parents`` /
``prompt_hash`` / ``legacy_authors``）后置门3（首次对外发布前强制回填）。

**Market Day1 预留**（03 §四 + §八）：``MarketFields`` 字段存在但 M3 不实现浏览 /
搜索 / 安装 / 评分 / 分账功能（后置 M3 后）。

[ADR-0031](../../../docs/adr/ADR-0031-cpk-format-and-themeregistry-static-loading.md)
决策 1 /
[03 §四](../../../docs/xkx-arch/03-DSL-UGC与Agent协作.md)
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

CPK_MANIFEST_SCHEMA_VERSION = 1

#: CPK 类型（03 §五三层粒度）。M3 全部 module_pack，ugc 后置 Wave 3。
PackType = Literal["module_pack", "ugc"]


class ReviewStatus(StrEnum):
    """CPK 审核状态（M3-3，ADR-0033 决策 3）。

    预检 / 专家审核后更新（[03 §八] 预检结果与 CPK manifest 关联）。M3 默认
    ``pending``，预检后按 [review_status](../content_review/review_status.py)
    推导：有 block -> ``rejected`` / 有 needs_review -> ``needs_review`` /
    否则 ``passed``。详细 findings 落 ``_review.json``，manifest 只存状态
    （资产 / 审核元数据分离，避免审核迭代污染资产真相源）。
    """

    PENDING = "pending"
    PASSED = "passed"
    NEEDS_REVIEW = "needs_review"
    REJECTED = "rejected"


class CpkDependency(BaseModel):
    """CPK 依赖声明（对照 03 §四 ``dependencies``）。

    M3 微场景无跨包依赖（线性），``version_range`` 留空。networkx 拓扑排序 +
    环检测后置 UGC（03 §三 DependencyResolver）。
    """

    cpk_id: str
    version_range: str = ""


class MarketFields(BaseModel):
    """创作者经济 Day1 预留字段（03 §四 + §八，M3 不实现功能）。

    阶段 -1~2 仅预留字段，浏览 / 搜索 / 安装 / 评分 / 分账后置 M3 后。
    可序列化（ADR-0022）：字段全基本类型 + list 容器。
    """

    title: str = ""
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    author_id: str = ""
    revenue_share: float = 0.0
    price: int = 0


class Provenance(BaseModel):
    """CPK 溯源（03 §四，M3 后置门3）。

    M3 开发期 ``CpkManifest.provenance=None``（只用 ``version`` + ``author`` 简单
    署名）。首次对外发布前（门3）强制回填全量溯源：``content_hash`` blake3 内容
    寻址 + ``parents`` 父版本链 + ``prompt_hash`` Agent prompt 哈希 +
    ``legacy_authors`` 历史作者署名。
    """

    content_hash: str = ""  # blake3 内容寻址，门3 强制回填
    parents: list[str] = Field(default_factory=list)
    author_type: str = ""  # "agent" | "human"
    author_id: str = ""
    model: str = ""  # LLM 模型 id（Agent 产出时）
    prompt_hash: str = ""  # sha256 Agent prompt 哈希
    legacy_authors: list[str] = Field(default_factory=list)


class ResourceQuota(BaseModel):
    """UGC 沙箱资源配额（03 §三，M3 后置 UGC）。

    ``module_pack`` 进程级无沙箱不强制；``ugc`` RestrictedPython 强制 fuel /
    墙钟 / 内存 / call_out 配额（不可妥协硬约束）。M3 全 module_pack，``None``。
    """

    fuel_per_tick: int = 0
    wall_time_ms: int = 0
    memory_mb: int = 0
    call_out_quota: int = 0


class CpkManifest(BaseModel):
    """CPK manifest（对齐 03 §四，M3 简化）。

    M3 全部 ``module_pack``（官方 StdLib），``provenance`` / ``resource_quota``
    后置（None）。``market`` Day1 预留字段存在但不实现功能。

    对照 03 §四 manifest YAML 结构::

        cpk_id: wuxia_xueshan_micro
        schema_version: 1
        theme: wuxia
        pack_type: module_pack
        version: 0.1.0
        license: CC-BY-SA-4.0
        author: xkx-core
        dependencies: []
        capabilities_required: []
        entry_points:
          main_scene: xueshan/dshanlu
        market: {title: "", tags: [], ...}

    可序列化（ADR-0022）：pydantic v2 ``model_dump`` -> JSON 往返，
    ``Day1 预留 market 字段往返`` 是 ADR-0031 验收标准。
    """

    cpk_id: str
    schema_version: int = CPK_MANIFEST_SCHEMA_VERSION
    theme: str
    pack_type: PackType = "module_pack"
    version: str = "0.1.0"
    license: str = "CC-BY-SA-4.0"
    author: str = ""  # 开发期简单署名（全量 provenance 后置门3）
    dependencies: list[CpkDependency] = Field(default_factory=list)
    capabilities_required: list[str] = Field(default_factory=list)
    entry_points: dict[str, str] = Field(default_factory=dict)  # main_scene -> room_id
    market: MarketFields = Field(default_factory=MarketFields)
    review_status: ReviewStatus = ReviewStatus.PENDING  # M3-3 预检状态
    provenance: Provenance | None = None  # M3 None，门3 强制回填
    resource_quota: ResourceQuota | None = None  # M3 None，UGC 后置


__all__ = [
    "CPK_MANIFEST_SCHEMA_VERSION",
    "PackType",
    "ReviewStatus",
    "CpkDependency",
    "MarketFields",
    "Provenance",
    "ResourceQuota",
    "CpkManifest",
]
