"""M2-2 评审工作台测试：REST + WebSocket（fastapi TestClient）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from xkx.workbench.app import create_app


def _write_job(tmp_path: Path, job_id: str, review_status: str = "pending") -> None:
    job_dir = tmp_path / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    job_state = {
        "job_id": job_id,
        "state": "REJECTED" if review_status == "rejected" else "APPROVED",
        "review_status": review_status,
        "revision_count": 0,
        "token_estimate": 0,
        "assets": [],
    }
    (job_dir / "job_state.json").write_text(json.dumps(job_state), encoding="utf-8")
    (job_dir / "manifest.yaml").write_text(
        "cpk_id: test\nreview_status: pending\n", encoding="utf-8"
    )
    (job_dir / "revision_trace.json").write_text(json.dumps({"trace": []}), encoding="utf-8")
    (job_dir / "_review.json").write_text(
        json.dumps({"derived_status": review_status, "report": {"findings": []}}),
        encoding="utf-8",
    )


def test_list_jobs(tmp_path: Path) -> None:
    _write_job(tmp_path, "j1")
    _write_job(tmp_path, "j2")
    app = create_app(tmp_path, static_dir=tmp_path / "no_static")
    client = TestClient(app)
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert {j["job_id"] for j in data} == {"j1", "j2"}


def test_get_job(tmp_path: Path) -> None:
    _write_job(tmp_path, "j1")
    app = create_app(tmp_path, static_dir=tmp_path / "no_static")
    client = TestClient(app)
    resp = client.get("/api/jobs/j1")
    assert resp.status_code == 200
    assert resp.json()["job_id"] == "j1"


def test_get_job_not_found(tmp_path: Path) -> None:
    app = create_app(tmp_path, static_dir=tmp_path / "no_static")
    client = TestClient(app)
    resp = client.get("/api/jobs/missing")
    assert resp.status_code == 404


def test_review_job(tmp_path: Path) -> None:
    _write_job(tmp_path, "j1", review_status="needs_review")
    app = create_app(tmp_path, static_dir=tmp_path / "no_static")
    client = TestClient(app)
    resp = client.post(
        "/api/jobs/j1/review",
        json={"decision": "approve", "comment": " looks good"},
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "passed"
    job_state = json.loads((tmp_path / "j1" / "job_state.json").read_text())
    assert job_state["state"] == "APPROVED"
    manifest = (tmp_path / "j1" / "manifest.yaml").read_text()
    assert "passed" in manifest


def test_get_asset(tmp_path: Path) -> None:
    _write_job(tmp_path, "j1")
    (tmp_path / "j1" / "npcs.yaml").write_text(
        "- id: xueshan/npc/test\n  name: 测试\n",
        encoding="utf-8",
    )
    app = create_app(tmp_path, static_dir=tmp_path / "no_static")
    client = TestClient(app)
    resp = client.get("/api/jobs/j1/assets/npcs/xueshan/npc/test")
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "测试"


def test_websocket_connect(tmp_path: Path) -> None:
    app = create_app(tmp_path, static_dir=tmp_path / "no_static")
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text("ping")
