"""MCP 校验层：验证 CPK 草稿的结构、可达性、合规性与可跑通性。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

# measure_revision 会导入 runtime；作为创作期工具仅被 orchestrator 调用。
from tools.measure_revision import check_scene

from xkx.content_review.precheck import precheck_cpk
from xkx.content_review.rules import Severity
from xkx.dsl.cpk import CpkManifest
from xkx.dsl.validator import validate


@dataclass
class MCPFinding:
    """单次校验发现。"""

    severity: str  # error | warning | info
    verifier: str
    message: str
    asset: str = ""


class MCPVerifier(Protocol):
    """MCP 校验器协议。"""

    name: str

    def verify(
        self, cpk_dir: Path, manifest: CpkManifest, ir: dict[str, Any]
    ) -> list[MCPFinding]: ...


class WorldGraphReachability:
    """world-graph MCP：检查房间可达性与 exit 合法性（纯 stdlib BFS）。"""

    name = "world_graph"

    def verify(
        self, cpk_dir: Path, manifest: CpkManifest, ir: dict[str, Any]
    ) -> list[MCPFinding]:
        rooms = ir.get("rooms", [])
        room_ids = {r.get("id") for r in rooms if r.get("id")}
        start = manifest.entry_points.get("main_scene", "")
        findings: list[MCPFinding] = []
        if not start:
            findings.append(
                MCPFinding(
                    "error", self.name, "manifest.entry_points.main_scene 未设置"
                )
            )
            return findings
        if start not in room_ids:
            findings.append(
                MCPFinding(
                    "error",
                    self.name,
                    f"入口房间 `{start}` 不存在于 rooms",
                    asset=start,
                )
            )
            return findings

        adj = {
            r.get("id"): list(r.get("exits", {}).values())
            for r in rooms
            if r.get("id")
        }
        visited: set[str] = set()
        queue: deque[str] = deque([start])
        visited.add(start)
        while queue:
            cur = queue.popleft()
            for target in adj.get(cur, []):
                if target not in room_ids:
                    findings.append(
                        MCPFinding(
                            "error",
                            self.name,
                            f"room `{cur}` 的 exit 指向未知房间 `{target}`",
                            asset=cur,
                        )
                    )
                    continue
                if target not in visited:
                    visited.add(target)
                    queue.append(target)

        for rid in sorted(room_ids - visited):
            findings.append(
                MCPFinding(
                    "error",
                    self.name,
                    f"room `{rid}` 从入口不可达",
                    asset=rid,
                )
            )
        return findings


class SchemaValidatorMCP:
    """schema MCP：调用 dsl.validator 做四道校验。"""

    name = "schema"

    def verify(
        self, cpk_dir: Path, manifest: CpkManifest, ir: dict[str, Any]
    ) -> list[MCPFinding]:
        return [
            MCPFinding("error", self.name, msg) for msg in validate(ir)
        ]


class PrecheckMCP:
    """precheck MCP：调用 content_review 扫描合规风险。"""

    name = "precheck"

    def verify(
        self, cpk_dir: Path, manifest: CpkManifest, ir: dict[str, Any]
    ) -> list[MCPFinding]:
        report = precheck_cpk(cpk_dir)
        findings: list[MCPFinding] = []
        for finding in report.findings:
            sev = "error" if finding.severity == Severity.BLOCK else "warning"
            findings.append(
                MCPFinding(
                    sev,
                    self.name,
                    f"{finding.file}:{finding.field_path} "
                    f"{finding.rule_id}({finding.matched_term})",
                )
            )
        if not report.license_ok:
            findings.append(
                MCPFinding("error", self.name, f"license: {report.license_note}")
            )
        return findings


class MeasureL4MCP:
    """measure L4 MCP：端到端可跑通性（go + kill + 确定性重放）。"""

    name = "measure_l4"

    def verify(
        self, cpk_dir: Path, manifest: CpkManifest, ir: dict[str, Any]
    ) -> list[MCPFinding]:
        try:
            results, validation_issues, ok = check_scene(cpk_dir)
        except Exception as e:  # noqa: BLE001
            return [MCPFinding("error", self.name, f"L4 异常: {e}")]
        findings: list[MCPFinding] = []
        for result in results:
            if not result.ok:
                findings.append(
                    MCPFinding(
                        "error",
                        self.name,
                        f"{result.level}: {result.error}",
                    )
                )
        for issue in validation_issues:
            findings.append(MCPFinding("error", self.name, f"validation: {issue}"))
        if ok and not findings:
            findings.append(MCPFinding("info", self.name, "L4 通过"))
        return findings


def default_verifiers(skip_l4: bool = False) -> list[MCPVerifier]:
    """默认 MCP 校验器列表。"""
    verifiers: list[MCPVerifier] = [
        WorldGraphReachability(),
        SchemaValidatorMCP(),
        PrecheckMCP(),
    ]
    if not skip_l4:
        verifiers.append(MeasureL4MCP())
    return verifiers
