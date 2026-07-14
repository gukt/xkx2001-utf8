"""CpkManifest 数据模型测试（M3-2，ADR-0031 决策 1）。"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from xkx.dsl.cpk import (
    CPK_MANIFEST_SCHEMA_VERSION,
    CpkDependency,
    CpkManifest,
    MarketFields,
    Provenance,
    ResourceQuota,
    ReviewStatus,
)


class TestCpkManifest:
    """CpkManifest 模型校验（对齐 03 §四，M3 简化）。"""

    def test_minimal_module_pack_manifest(self) -> None:
        """最小 module_pack manifest（M3 默认：provenance/resource_quota None）。"""
        m = CpkManifest(cpk_id="test_cpk", theme="wuxia")
        assert m.cpk_id == "test_cpk"
        assert m.schema_version == CPK_MANIFEST_SCHEMA_VERSION
        assert m.theme == "wuxia"
        assert m.pack_type == "module_pack"
        assert m.version == "0.1.0"
        assert m.license == "CC-BY-SA-4.0"
        assert m.provenance is None  # M3 后置门3
        assert m.resource_quota is None  # M3 后置 UGC
        assert m.dependencies == []
        assert m.capabilities_required == []
        assert m.entry_points == {}
        assert m.review_status == ReviewStatus.PENDING  # M3-3 预检状态

    def test_pack_type_module_pack_vs_ugc(self) -> None:
        """module_pack（M3 全部）vs ugc（后置 Wave 3）。"""
        m_module = CpkManifest(cpk_id="m", theme="wuxia", pack_type="module_pack")
        m_ugc = CpkManifest(cpk_id="u", theme="wuxia", pack_type="ugc")
        assert m_module.pack_type == "module_pack"
        assert m_ugc.pack_type == "ugc"

    def test_invalid_pack_type_rejected(self) -> None:
        """非法 pack_type 被拒（pydantic Literal 校验）。"""
        with pytest.raises(ValidationError):
            CpkManifest(cpk_id="x", theme="wuxia", pack_type="invalid")  # type: ignore[arg-type]

    def test_entry_points_main_scene(self) -> None:
        """entry_points.main_scene 标识 CPK 入口房间。"""
        m = CpkManifest(
            cpk_id="xueshan",
            theme="wuxia",
            entry_points={"main_scene": "xueshan/dshanlu"},
        )
        assert m.entry_points["main_scene"] == "xueshan/dshanlu"

    def test_market_day1_fields_roundtrip(self) -> None:
        """market Day1 预留字段序列化往返（ADR-0031 验收标准）。"""
        m = CpkManifest(
            cpk_id="x",
            theme="wuxia",
            market=MarketFields(
                title="少林派扩展包",
                tags=["wuxia", "shaolin"],
                author_id="creator_42",
                revenue_share=0.7,
                price=0,
            ),
        )
        dumped = m.model_dump()
        assert dumped["market"]["title"] == "少林派扩展包"
        assert dumped["market"]["revenue_share"] == 0.7
        # JSON 往返（ADR-0022 可序列化）
        m2 = CpkManifest.model_validate(json.loads(json.dumps(dumped)))
        assert m2.market.title == "少林派扩展包"
        assert m2.market.revenue_share == 0.7

    def test_provenance_post_m3(self) -> None:
        """provenance M3 后置门3（开发期 None，门3 后全量回填）。"""
        m = CpkManifest(cpk_id="x", theme="wuxia")
        assert m.provenance is None
        m_full = CpkManifest(
            cpk_id="x",
            theme="wuxia",
            provenance=Provenance(
                content_hash="blake3:abc",
                parents=["v2"],
                author_type="agent",
                model="claude",
            ),
        )
        assert m_full.provenance is not None
        assert m_full.provenance.content_hash == "blake3:abc"

    def test_resource_quota_post_ugc(self) -> None:
        """resource_quota M3 后置 UGC（module_pack 不强制）。"""
        m = CpkManifest(cpk_id="x", theme="wuxia")
        assert m.resource_quota is None
        m_ugc = CpkManifest(
            cpk_id="u",
            theme="wuxia",
            pack_type="ugc",
            resource_quota=ResourceQuota(fuel_per_tick=50000, wall_time_ms=50),
        )
        assert m_ugc.resource_quota is not None
        assert m_ugc.resource_quota.fuel_per_tick == 50000

    def test_dependencies(self) -> None:
        """dependencies 声明（M3 微场景空，跨包依赖后置 UGC）。"""
        m = CpkManifest(
            cpk_id="x",
            theme="wuxia",
            dependencies=[CpkDependency(cpk_id="wuxia_core", version_range="^2.0")],
        )
        assert m.dependencies[0].cpk_id == "wuxia_core"
        assert m.dependencies[0].version_range == "^2.0"

    def test_full_manifest_json_roundtrip(self) -> None:
        """完整 manifest JSON 序列化往返（ADR-0022 可序列化）。"""
        m = CpkManifest(
            cpk_id="wuxia_xueshan_micro",
            theme="wuxia",
            entry_points={"main_scene": "xueshan/dshanlu"},
            author="xkx-core",
        )
        dumped = m.model_dump()
        m2 = CpkManifest.model_validate(dumped)
        assert m2 == m


class TestReviewStatus:
    """审核状态字段（M3-3，ADR-0033 决策 3）。"""

    def test_default_pending(self) -> None:
        """新 manifest 默认 pending（未预检）。"""
        m = CpkManifest(cpk_id="x", theme="wuxia")
        assert m.review_status == ReviewStatus.PENDING
        assert m.review_status == "pending"  # StrEnum str 兼容

    def test_four_statuses(self) -> None:
        """四态（pending / passed / needs_review / rejected）。"""
        for status in ReviewStatus:
            m = CpkManifest(cpk_id="x", theme="wuxia", review_status=status)
            assert m.review_status == status

    def test_review_status_json_roundtrip(self) -> None:
        """review_status JSON 往返（ADR-0022 可序列化）。"""
        m = CpkManifest(
            cpk_id="x", theme="wuxia", review_status=ReviewStatus.NEEDS_REVIEW
        )
        dumped = json.loads(json.dumps(m.model_dump(mode="json")))
        m2 = CpkManifest.model_validate(dumped)
        assert m2.review_status == ReviewStatus.NEEDS_REVIEW

    def test_review_status_from_string(self) -> None:
        """从字符串构造（YAML 加载 manifest 场景，[review_status.sync_manifest_status]）。"""
        m = CpkManifest(cpk_id="x", theme="wuxia", review_status="passed")
        assert m.review_status == ReviewStatus.PASSED
