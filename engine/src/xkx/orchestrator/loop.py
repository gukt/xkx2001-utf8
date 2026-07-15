"""Orchestrator 主闭环：生成 -> 校验 -> 修订 -> 审核。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from xkx.content_gen.generate import revise_asset
from xkx.content_gen.llm_client import LLMClient
from xkx.content_review.precheck import precheck_cpk
from xkx.content_review.review_status import (
    ReviewStatus,
    derive_status,
    sync_manifest_status,
    write_review_report,
)
from xkx.dsl.cpk import CpkManifest, Provenance
from xkx.dsl.cpk import ReviewStatus as CpkReviewStatus
from xkx.dsl.cpk_loader import load_cpk
from xkx.orchestrator.capabilities import (
    generate_asset,
    generate_plan,
    task_key,
)
from xkx.orchestrator.mcp import MCPFinding, MCPVerifier, default_verifiers
from xkx.orchestrator.rag import build_context
from xkx.orchestrator.state_machine import Job, JobState
from xkx.orchestrator.types import AssetTask, WorldBible

_ASSET_FILE: dict[str, str] = {
    "room": "rooms.yaml",
    "npc": "npcs.yaml",
    "skill": "skills.yaml",
    "quest": "quests.yaml",
    "item": "items.yaml",
    "rule": "rules.yaml",
}

_ID_RE = re.compile(r"`([^`]+)`")


def _estimate_tokens(obj: object) -> int:
    """非常粗略的 token 估算（字符数 / 4）。"""
    return len(json.dumps(obj, ensure_ascii=False)) // 4


class Orchestrator:
    """M2 创作闭环编排器。"""

    def __init__(
        self,
        llm: LLMClient,
        bible: WorldBible,
        output_dir: Path | str,
        *,
        max_revisions: int = 3,
        verifiers: list[MCPVerifier] | None = None,
        skip_l4: bool = False,
    ) -> None:
        self.llm = llm
        self.bible = bible
        self.output_dir = Path(output_dir)
        self.max_revisions = max_revisions
        self.verifiers = verifiers if verifiers is not None else default_verifiers(skip_l4)

    def create_job(self, intent_path: Path | str) -> Job:
        """从意图 YAML 创建 Job。"""
        intent = yaml.safe_load(Path(intent_path).read_text(encoding="utf-8")) or {}
        cpk_id = intent.get("cpk_id", "m2_demo")
        out_dir = self.output_dir / cpk_id
        return Job(
            intent=intent,
            bible=self.bible,
            output_dir=out_dir,
            max_revisions=self.max_revisions,
        )

    def run(self, job: Job) -> Job:
        """跑完整创作闭环。"""
        self._plan(job)
        self._generate(job)
        for _ in range(job.max_revisions + 1):
            self._assemble(job)
            self._verify(job)
            if not job.issues:
                job.transition(JobState.PRECHECKING)
                break
            if job.revision_count >= job.max_revisions:
                job.transition(JobState.PRECHECKING)
                break
            job.transition(JobState.REVISING)
            self._revise(job)
        self._precheck(job)
        self._finalize(job)
        return job

    def _plan(self, job: Job) -> None:
        job.transition(JobState.PLANNING)
        job.plan = generate_plan(job.intent, job.bible)
        job.trace.append({"plan": [task_key(t) for t in job.plan]})
        job.transition(JobState.GENERATING)

    def _generate(self, job: Job) -> None:
        for task in job.plan:
            try:
                asset = generate_asset(task, self.llm, job.bible)
            except Exception as e:  # noqa: BLE001
                msg = f"生成失败 {task_key(task)}: {e}"
                job.trace.append({"error": msg})
                job.issues.append(msg)
                asset = {"id": task.asset_id, "_generation_error": str(e)}
            job.assets[task_key(task)] = asset
            job.token_estimate += _estimate_tokens(asset)

    def _assemble(self, job: Job) -> None:
        out = job.output_dir
        out.mkdir(parents=True, exist_ok=True)
        manifest = self._build_manifest(job)
        manifest_path = out / "manifest.yaml"
        manifest_path.write_text(
            yaml.safe_dump(
                manifest.model_dump(mode="json"),
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        grouped: dict[str, list[dict[str, Any]]] = {k: [] for k in _ASSET_FILE}
        for task in job.plan:
            key = task_key(task)
            asset = job.assets.get(key, {})
            if asset and "_generation_error" not in asset:
                grouped[task.asset_type].append(asset)
        for asset_type, file_name in _ASSET_FILE.items():
            items = grouped[asset_type]
            if not items:
                continue
            (out / file_name).write_text(
                yaml.safe_dump(
                    items,
                    allow_unicode=True,
                    sort_keys=False,
                    default_flow_style=False,
                ),
                encoding="utf-8",
            )

    def _build_manifest(self, job: Job) -> CpkManifest:
        intent = job.intent
        model = getattr(self.llm, "model", "")
        manifest_data: dict[str, Any] = {
            "cpk_id": intent.get("cpk_id", "m2_demo"),
            "theme": intent.get("theme", job.bible.theme or "default"),
            "pack_type": "module_pack",
            "version": intent.get("version", "0.1.0"),
            "license": intent.get("license", "CC-BY-SA-4.0"),
            "author": intent.get("author", "xkx-agent"),
            "dependencies": intent.get("dependencies", []),
            "capabilities_required": intent.get("capabilities_required", []),
            "entry_points": {
                "main_scene": intent.get("entry_scene", "")
            },
            "review_status": CpkReviewStatus.PENDING.value,
            "provenance": Provenance(
                author_type="agent",
                model=model,
                prompt_hash="",
            ).model_dump(mode="json"),
        }
        return CpkManifest.model_validate(manifest_data)

    def _verify(self, job: Job) -> None:
        job.transition(JobState.VALIDATING)
        job.issues = []
        try:
            manifest, ir, rules, _skills = load_cpk(job.output_dir, registry=None)
            ir = dict(ir)
            ir["rules"] = [r.model_dump(mode="json") for r in rules]
        except Exception as e:  # noqa: BLE001
            job.issues.append(f"CPK 加载失败: {e}")
            return

        findings: list[MCPFinding] = []
        for verifier in self.verifiers:
            findings.extend(verifier.verify(job.output_dir, manifest, ir))
        job.issues = [
            f"[{f.verifier}] {f.message}" for f in findings if f.severity == "error"
        ]
        job.trace.append({
            "revision": job.revision_count,
            "findings": [
                {"severity": f.severity, "verifier": f.verifier, "msg": f.message}
                for f in findings
            ],
        })

    def _revise(self, job: Job) -> None:
        grouped: dict[str, list[str]] = {}
        for issue in job.issues:
            task = _asset_for_issue(issue, job.plan)
            if task is None:
                continue
            grouped.setdefault(task_key(task), []).append(issue)
        for key, issues in grouped.items():
            task = _task_by_key(key, job.plan)
            if task is None:
                continue
            current = job.assets.get(key, {})
            if not current or "_generation_error" in current:
                continue
            rag_context = build_context(job.bible, task)
            try:
                revised = revise_asset(
                    self.llm,
                    task.asset_type,
                    task.asset_id,
                    current,
                    issues,
                    rag_context,
                )
            except Exception as e:  # noqa: BLE001
                job.trace.append({"revise_error": f"{key}: {e}"})
                continue
            job.assets[key] = revised
            job.token_estimate += _estimate_tokens(revised)
        job.revision_count += 1
        job.transition(JobState.VALIDATING)

    def _precheck(self, job: Job) -> None:
        try:
            report = precheck_cpk(job.output_dir)
        except Exception as e:  # noqa: BLE001
            job.review_status = CpkReviewStatus.REJECTED.value
            job.trace.append({"precheck_error": str(e)})
            job.transition(JobState.REVIEWING)
            return

        precheck_status = derive_status(report)
        if job.issues:
            job.review_status = CpkReviewStatus.REJECTED.value
        elif precheck_status == ReviewStatus.NEEDS_REVIEW:
            job.review_status = CpkReviewStatus.NEEDS_REVIEW.value
        elif precheck_status == ReviewStatus.REJECTED:
            job.review_status = CpkReviewStatus.REJECTED.value
        else:
            job.review_status = CpkReviewStatus.PASSED.value

        write_review_report(job.output_dir, report)
        sync_manifest_status(job.output_dir)
        job.trace.append({
            "review_status": job.review_status,
            "precheck_findings": len(report.findings),
        })
        job.transition(JobState.REVIEWING)

    def _finalize(self, job: Job) -> None:
        if job.review_status == CpkReviewStatus.PASSED.value:
            job.transition(JobState.APPROVED)
        else:
            job.transition(JobState.REJECTED)
        self._write_revision_trace(job)
        self._write_job_state(job)

    def _write_revision_trace(self, job: Job) -> None:
        trace_path = job.output_dir / "revision_trace.json"
        trace_path.write_text(
            json.dumps(
                {
                    "job_id": job.id,
                    "review_status": job.review_status,
                    "revision_count": job.revision_count,
                    "token_estimate": job.token_estimate,
                    "trace": job.trace,
                    "final_issues": job.issues,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_job_state(self, job: Job) -> None:
        state_path = job.output_dir / "job_state.json"
        state_path.write_text(
            json.dumps(
                {
                    "job_id": job.id,
                    "state": job.state.value,
                    "review_status": job.review_status,
                    "revision_count": job.revision_count,
                    "token_estimate": job.token_estimate,
                    "assets": list(job.assets.keys()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _asset_for_issue(issue: str, plan: list[AssetTask]) -> AssetTask | None:
    """从 issue 文本中定位对应 asset task（按反引号 id 匹配）。"""
    ids = _ID_RE.findall(issue)
    for candidate in ids:
        for task in plan:
            if candidate == task.asset_id:
                return task
    return None


def _task_by_key(key: str, plan: list[AssetTask]) -> AssetTask | None:
    for task in plan:
        if task_key(task) == key:
            return task
    return None
