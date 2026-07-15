"""FastAPI REST endpoints for M2-2 评审工作台。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from xkx.content_gen.llm_client import create_llm_client
from xkx.orchestrator.loop import Orchestrator
from xkx.orchestrator.rag import load_bible
from xkx.workbench.runner import run_orchestrator_streaming

try:
    from fastapi import APIRouter, BackgroundTasks, HTTPException
except ImportError as exc:  # pragma: no cover - 无 workbench extra 时占位
    APIRouter = object  # type: ignore[misc, assignment]
    BackgroundTasks = object  # type: ignore[misc, assignment]
    HTTPException = Exception  # type: ignore[misc, assignment]
    _FASTAPI_AVAILABLE = False
    _IMPORT_ERROR = exc
else:
    _FASTAPI_AVAILABLE = True
    _IMPORT_ERROR = None


class WorkbenchState:
    """共享运行时状态（输出目录 + 正在运行的 job 集合）。"""

    def __init__(self, output_dir: Path | str) -> None:
        self.output_dir = Path(output_dir)
        self.running_jobs: set[str] = set()


def _assert_fastapi() -> None:
    if not _FASTAPI_AVAILABLE:
        raise _IMPORT_ERROR or ImportError("fastapi 未安装")


def _list_job_dirs(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return [p for p in output_dir.iterdir() if p.is_dir() and (p / "job_state.json").is_file()]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def make_router(state: WorkbenchState, manager: Any) -> APIRouter:
    """创建并返回评审工作台 REST router。"""
    _assert_fastapi()
    router = APIRouter()

    @router.post("/jobs")
    async def create_job(
        request: dict[str, Any], background_tasks: BackgroundTasks
    ) -> dict[str, Any]:
        intent_path = Path(request.get("intent", ""))
        bible_path = Path(request.get("bible", ""))
        provider = request.get("provider", "volcano")
        max_revisions = request.get("max_revisions", 3)
        skip_l4 = request.get("skip_l4", False)
        if not intent_path.is_file() or not bible_path.is_file():
            raise HTTPException(status_code=400, detail="intent 或 bible 路径不存在")

        bible = load_bible(bible_path)
        llm = create_llm_client(provider)
        orchestrator = Orchestrator(
            llm=llm,
            bible=bible,
            output_dir=state.output_dir,
            max_revisions=max_revisions,
            skip_l4=skip_l4,
        )
        job = orchestrator.create_job(intent_path)
        job_id = job.output_dir.name

        async def _run() -> None:
            state.running_jobs.add(job_id)
            try:
                await run_orchestrator_streaming(orchestrator, job, manager, job_id)
            finally:
                state.running_jobs.discard(job_id)

        background_tasks.add_task(_run)
        return {"job_id": job_id, "state": "PENDING"}

    @router.get("/jobs")
    async def list_jobs() -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        for p in _list_job_dirs(state.output_dir):
            job_state = _read_json(p / "job_state.json")
            jobs.append({
                "job_id": job_state.get("job_id", p.name),
                "state": job_state.get("state"),
                "review_status": job_state.get("review_status"),
                "revision_count": job_state.get("revision_count"),
                "running": p.name in state.running_jobs,
            })
        return jobs

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> dict[str, Any]:
        job_dir = state.output_dir / job_id
        if not (job_dir / "job_state.json").exists():
            raise HTTPException(status_code=404, detail=f"Job {job_id} 不存在")
        return {
            "job_id": job_id,
            "running": job_id in state.running_jobs,
            "job_state": _read_json(job_dir / "job_state.json"),
            "manifest": _read_yaml(job_dir / "manifest.yaml"),
            "revision_trace": _read_yaml(job_dir / "revision_trace.json"),
            "review": _read_yaml(job_dir / "_review.json"),
        }

    @router.get("/jobs/{job_id}/assets/{asset_type}/{asset_id:path}")
    async def get_asset(job_id: str, asset_type: str, asset_id: str) -> dict[str, Any]:
        if asset_type not in ("rooms", "npcs", "quests", "items", "skills", "rules"):
            raise HTTPException(status_code=400, detail=f"未知 asset_type: {asset_type}")
        job_dir = state.output_dir / job_id
        path = job_dir / f"{asset_type}.yaml"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"{asset_type}.yaml 不存在")
        data = _read_yaml(path) or []
        for item in data:
            if item.get("id") == asset_id or item.get("skill_id") == asset_id:
                return {"asset_type": asset_type, "asset_id": asset_id, "data": item}
        raise HTTPException(status_code=404, detail=f"Asset {asset_id} 不存在")

    @router.post("/jobs/{job_id}/review")
    async def review_job(job_id: str, verdict: dict[str, Any]) -> dict[str, Any]:
        job_dir = state.output_dir / job_id
        if not (job_dir / "job_state.json").exists():
            raise HTTPException(status_code=404, detail=f"Job {job_id} 不存在")
        if job_id in state.running_jobs:
            raise HTTPException(status_code=409, detail="Job 仍在运行中，无法评审")

        decision = verdict.get("decision", "")
        comment = verdict.get("comment", "")
        if decision not in ("approve", "reject"):
            raise HTTPException(status_code=400, detail="decision 必须是 approve 或 reject")

        review_status = "passed" if decision == "approve" else "rejected"
        # 更新 _review.json
        review_path = job_dir / "_review.json"
        review = _read_json(review_path) if review_path.exists() else {}
        review.setdefault("report", {})
        review["derived_status"] = review_status
        review["manual_verdict"] = {"decision": decision, "comment": comment}
        review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

        # 更新 manifest.yaml
        manifest_path = job_dir / "manifest.yaml"
        manifest = _read_yaml(manifest_path) or {}
        manifest["review_status"] = review_status
        manifest_path.write_text(
            yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        # 更新 job_state.json
        job_state_path = job_dir / "job_state.json"
        job_state = _read_json(job_state_path)
        job_state["review_status"] = review_status
        job_state["state"] = "APPROVED" if decision == "approve" else "REJECTED"
        job_state_path.write_text(
            json.dumps(job_state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        return {"job_id": job_id, "review_status": review_status}

    return router
