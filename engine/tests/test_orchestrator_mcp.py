"""MCP 校验器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from xkx.dsl.cpk import CpkManifest
from xkx.dsl.ir import compile_scene
from xkx.dsl.layer0 import RoomDef
from xkx.orchestrator.mcp import (
    MeasureL4MCP,
    PrecheckMCP,
    SchemaValidatorMCP,
    WorldGraphReachability,
)


@pytest.fixture
def tmp_cpk(tmp_path: Path) -> Path:
    """创建一个最小 CPK 目录。"""
    cpk_dir = tmp_path / "cpk"
    cpk_dir.mkdir()
    manifest = CpkManifest(
        cpk_id="test",
        theme="default",
        license="CC0-1.0",
        entry_points={"main_scene": "r1"},
    )
    (cpk_dir / "manifest.yaml").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    return cpk_dir


def _make_ir(rooms: list[dict]) -> dict:
    """辅助：从 room dict 构造 IR。"""
    room_defs = [RoomDef.model_validate(r) for r in rooms]
    return compile_scene(room_defs, [], [], [])


def test_world_graph_all_reachable():
    ir = _make_ir([
        {"id": "r1", "short": "a", "long": "aa", "exits": {"east": "r2"}},
        {"id": "r2", "short": "b", "long": "bb", "exits": {"west": "r1"}},
    ])
    manifest = CpkManifest(
        cpk_id="t",
        theme="default",
        entry_points={"main_scene": "r1"},
    )
    v = WorldGraphReachability()
    findings = v.verify(Path("."), manifest, ir)
    assert not any(f.severity == "error" for f in findings)


def test_world_graph_missing_entry():
    ir = _make_ir([{"id": "r1", "short": "a", "long": "aa", "exits": {}}])
    manifest = CpkManifest(
        cpk_id="t",
        theme="default",
        entry_points={},
    )
    v = WorldGraphReachability()
    findings = v.verify(Path("."), manifest, ir)
    assert any("main_scene" in f.message for f in findings)


def test_world_graph_unknown_exit():
    ir = _make_ir([
        {"id": "r1", "short": "a", "long": "aa", "exits": {"east": "r_unknown"}},
    ])
    manifest = CpkManifest(
        cpk_id="t",
        theme="default",
        entry_points={"main_scene": "r1"},
    )
    v = WorldGraphReachability()
    findings = v.verify(Path("."), manifest, ir)
    assert any("r_unknown" in f.message for f in findings)


def test_world_graph_unreachable_room():
    ir = _make_ir([
        {"id": "r1", "short": "a", "long": "aa", "exits": {}},
        {"id": "r2", "short": "b", "long": "bb", "exits": {}},
    ])
    manifest = CpkManifest(
        cpk_id="t",
        theme="default",
        entry_points={"main_scene": "r1"},
    )
    v = WorldGraphReachability()
    findings = v.verify(Path("."), manifest, ir)
    assert any("r2" in f.message and "不可达" in f.message for f in findings)


def test_schema_validator_detects_unknown_field():
    ir = _make_ir([{"id": "r1", "short": "a", "long": "aa", "exits": {}}])
    ir["rooms"][0]["unknown_field"] = "x"
    ir["rules"] = []
    v = SchemaValidatorMCP()
    findings = v.verify(Path("."), None, ir)  # type: ignore[arg-type]
    assert findings


def test_schema_validator_clean_ir():
    ir = _make_ir([{"id": "r1", "short": "a", "long": "aa", "exits": {}}])
    ir["rules"] = []
    v = SchemaValidatorMCP()
    findings = v.verify(Path("."), None, ir)  # type: ignore[arg-type]
    assert not findings


def test_precheck_detects_missing_license(tmp_cpk: Path):
    manifest = CpkManifest(
        cpk_id="test",
        theme="default",
        license="",
        entry_points={"main_scene": "r1"},
    )
    (tmp_cpk / "manifest.yaml").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    v = PrecheckMCP()
    findings = v.verify(tmp_cpk, manifest, {})
    assert any("license" in f.message for f in findings)


def test_precheck_passes(tmp_cpk: Path):
    manifest = CpkManifest(
        cpk_id="test",
        theme="default",
        license="CC0-1.0",
        entry_points={"main_scene": "r1"},
    )
    (tmp_cpk / "manifest.yaml").write_text(
        manifest.model_dump_json(), encoding="utf-8"
    )
    v = PrecheckMCP()
    findings = v.verify(tmp_cpk, manifest, {})
    assert not any(f.severity == "error" for f in findings)


def test_measure_l4_on_xueshan_micro():
    """在真实 xueshan_micro 上跑 L4，验证接入无异常。"""
    scene_dir = Path(__file__).resolve().parents[1] / "scenes" / "xueshan_micro"
    manifest = CpkManifest(
        cpk_id="xueshan_micro",
        theme="wuxia",
        license="CC-BY-SA-4.0",
        entry_points={"main_scene": "xueshan/dshanlu"},
    )
    v = MeasureL4MCP()
    findings = v.verify(scene_dir, manifest, {})
    info_msgs = [f.message for f in findings if f.severity == "info"]
    error_msgs = [f.message for f in findings if f.severity == "error"]
    assert any("L4 通过" in m for m in info_msgs), f"errors: {error_msgs}"
