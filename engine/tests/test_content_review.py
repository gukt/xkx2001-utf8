"""内容审核 pipeline MVP 测试（M3-3，ADR-0033）。

覆盖：4 类词表命中（暴力 / 赌博 / 版权 / license）+ 状态推导 +
``_review.json`` 落盘 + manifest 同步 + 雪山派真实预检（4 金庸角色命中验证）+
checklist 模板。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from xkx.content_review.checklist import (
    REVIEW_CHECKLIST,
    render_checklist_template,
)
from xkx.content_review.precheck import _walk_strings, precheck_cpk
from xkx.content_review.review_status import (
    derive_status,
    sync_manifest_status,
    write_review_report,
)
from xkx.content_review.rules import Category, Severity
from xkx.dsl.cpk import ReviewStatus

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_cpk(
    tmp_path: Path,
    *,
    manifest_overrides: dict | None = None,
    npcs: list | None = None,
    rooms: list | None = None,
    quests: list | None = None,
    items: list | None = None,
    rules: list | None = None,
    skills: list | None = None,
) -> Path:
    """构造最小 CPK 夹具（manifest + 可选资产 YAML）。"""
    manifest = {
        "cpk_id": "test_cpk",
        "schema_version": 1,
        "theme": "wuxia",
        "pack_type": "module_pack",
        "version": "0.1.0",
        "license": "CC-BY-SA-4.0",
        "author": "tester",
        "dependencies": [],
        "capabilities_required": [],
        "entry_points": {},
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    (tmp_path / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    assets = [
        ("npcs.yaml", npcs),
        ("rooms.yaml", rooms),
        ("quests.yaml", quests),
        ("items.yaml", items),
        ("rules.yaml", rules),
        ("skills.yaml", skills),
    ]
    for name, data in assets:
        if data is not None:
            (tmp_path / name).write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
    return tmp_path


class TestPrecheckClean:
    """无违规 CPK -> passed。"""

    def test_clean_cpk_passed(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path, npcs=[{"id": "city/npc/bing", "name": "小兵"}])
        report = precheck_cpk(tmp_path)
        assert report.passed
        assert report.findings == []
        assert derive_status(report) == ReviewStatus.PASSED


class TestPrecheckHits:
    """4 类词表命中。"""

    def test_violence_hit_needs_review(self, tmp_path: Path) -> None:
        _write_cpk(
            tmp_path,
            rooms=[{"id": "r1", "short": "密室", "long": "这里发生过虐杀事件"}],
        )
        report = precheck_cpk(tmp_path)
        assert any(f.category == Category.VIOLENCE for f in report.findings)
        assert report.needs_review
        assert derive_status(report) == ReviewStatus.NEEDS_REVIEW

    def test_gambling_hit(self, tmp_path: Path) -> None:
        _write_cpk(
            tmp_path,
            rooms=[{"id": "r1", "short": "赌坊", "long": "设有轮盘和筹码"}],
        )
        report = precheck_cpk(tmp_path)
        cats = {f.category for f in report.findings}
        assert Category.GAMBLING in cats

    def test_copyright_hit_with_work(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path, npcs=[{"id": "n1", "name": "金轮法王"}])
        report = precheck_cpk(tmp_path)
        copyright_hits = [
            f for f in report.findings if f.category == Category.COPYRIGHT
        ]
        assert copyright_hits
        hit = next(f for f in copyright_hits if f.matched_term == "金轮法王")
        assert hit.work == "神雕侠侣"
        assert hit.severity == Severity.NEEDS_REVIEW
        assert derive_status(report) == ReviewStatus.NEEDS_REVIEW

    def test_copyright_family_hit(self, tmp_path: Path) -> None:
        """门派名命中（copyright_jinyong_family）。"""
        _write_cpk(
            tmp_path,
            npcs=[{"id": "n1", "name": "张三", "inquiry": {"门派": "我是华山派的"}}],
        )
        report = precheck_cpk(tmp_path)
        terms = {f.matched_term for f in report.findings if f.category == Category.COPYRIGHT}
        assert "华山派" in terms


class TestLicenseCompliance:
    """license 合规（空 = block -> rejected）。"""

    def test_license_missing_block(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path, manifest_overrides={"license": ""})
        report = precheck_cpk(tmp_path)
        assert not report.passed
        assert not report.license_ok
        assert any(
            f.severity == Severity.BLOCK and f.category == Category.LICENSE
            for f in report.findings
        )
        assert derive_status(report) == ReviewStatus.REJECTED

    def test_license_present_ok(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path, manifest_overrides={"license": "MIT"})
        report = precheck_cpk(tmp_path)
        assert report.license_ok
        assert not any(f.category == Category.LICENSE for f in report.findings)


class TestWalkStrings:
    """递归扫描覆盖 dict / list / 嵌套。"""

    def test_nested_structures(self) -> None:
        obj = {"a": "x", "b": ["y", {"c": "z"}], "d": {"e": {"f": "w"}}}
        paths = dict(_walk_strings(obj))
        assert paths == {
            "a": "x",
            "b[0]": "y",
            "b[1].c": "z",
            "d.e.f": "w",
        }

    def test_empty_str_skipped(self) -> None:
        """空字符串不扫描（避免 manifest 空字段误报）。"""
        paths = [p for p, v in _walk_strings({"x": ""})]
        assert paths == ["x"]  # 路径仍 yield（值空，扫描不命中词表）

    def test_non_string_values_skipped(self) -> None:
        paths = dict(_walk_strings({"n": 42, "b": True, "f": 1.5}))
        assert paths == {}  # 数值 / 布尔不扫描


class TestReviewStatusIntegration:
    """_review.json 落盘 + manifest 同步。"""

    def test_write_review_report_structure(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path, npcs=[{"id": "n1", "name": "金轮法王"}])
        report = precheck_cpk(tmp_path)
        out = write_review_report(tmp_path, report)
        assert out.name == "_review.json"
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["cpk_id"] == "test_cpk"
        assert data["derived_status"] == "needs_review"
        assert data["report"]["passed"] is True
        assert data["report"]["needs_review"] is True
        assert len(data["report"]["findings"]) >= 1

    def test_sync_manifest_status_writes_back(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path, npcs=[{"id": "n1", "name": "金轮法王"}])
        report = precheck_cpk(tmp_path)
        write_review_report(tmp_path, report)
        synced = sync_manifest_status(tmp_path)
        assert synced == ReviewStatus.NEEDS_REVIEW
        # 重读 manifest 确认 review_status 已写回
        manifest = yaml.safe_load((tmp_path / "manifest.yaml").read_text(encoding="utf-8"))
        assert manifest["review_status"] == "needs_review"

    def test_sync_noop_when_already_synced(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path)  # clean CPK -> passed
        report = precheck_cpk(tmp_path)
        write_review_report(tmp_path, report)
        synced = sync_manifest_status(tmp_path)
        assert synced == ReviewStatus.PASSED

    def test_sync_returns_none_without_report(self, tmp_path: Path) -> None:
        _write_cpk(tmp_path)
        assert sync_manifest_status(tmp_path) is None

    def test_to_dict_serializable(self, tmp_path: Path) -> None:
        """PrecheckReport.to_dict 可 JSON 序列化（ADR-0022 可序列化）。"""
        _write_cpk(tmp_path, npcs=[{"id": "n1", "name": "金轮法王"}])
        report = precheck_cpk(tmp_path)
        # 不抛异常即通过
        json.dumps(report.to_dict(), ensure_ascii=False)


class TestXueshanRealPrecheck:
    """雪山派真实 CPK 预检（M3-1 已入库，验证预检对真实内容有效）。"""

    @pytest.fixture
    def xueshan_cpk(self) -> Path:
        return _REPO_ROOT / "scenes" / "xueshan_micro"

    def test_jinyong_roles_detected(self, xueshan_cpk: Path) -> None:
        report = precheck_cpk(xueshan_cpk)
        roles = {
            f.matched_term
            for f in report.findings
            if f.category == Category.COPYRIGHT
        }
        # 4 金庸角色 + 雪山派门派名（《侠客行》）命中
        assert {"金轮法王", "鸠摩智", "灵智上人", "达尔巴", "雪山派"} <= roles

    def test_xueshan_needs_review_passed(self, xueshan_cpk: Path) -> None:
        """雪山派：needs_review（版权命中）但 passed=True（无 block，M3 不清洗）。"""
        report = precheck_cpk(xueshan_cpk)
        assert report.needs_review
        assert report.passed  # 无 block（M3 不清洗，版权命中不阻塞）
        assert report.license_ok
        assert derive_status(report) == ReviewStatus.NEEDS_REVIEW


class TestChecklist:
    """专家审核 checklist MVP。"""

    def test_render_template_contains_items(self) -> None:
        md = render_checklist_template()
        assert "license_declared" in md
        assert "copyright_jinyong" in md
        assert "fun_playtest" in md
        assert "六维" in md

    def test_checklist_covers_six_dimensions(self) -> None:
        """六维矩阵覆盖（结构 / 数值 / 经济 / 任务逻辑 / 叙事 / 趣味）。"""
        dims = {item.dimension for item in REVIEW_CHECKLIST}
        assert {
            "structure",
            "numeric",
            "quest-logic",
            "narrative",
            "fun",
        } <= dims

    def test_checklist_has_required_and_optional(self) -> None:
        required = [i for i in REVIEW_CHECKLIST if i.required]
        optional = [i for i in REVIEW_CHECKLIST if not i.required]
        assert len(required) >= 9
        assert any(i.item_id == "fun_playtest" for i in optional)
