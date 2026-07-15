"""Orchestrator 状态机与闭环测试。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from xkx.orchestrator.loop import Orchestrator
from xkx.orchestrator.mcp import (
    PrecheckMCP,
    SchemaValidatorMCP,
    WorldGraphReachability,
)
from xkx.orchestrator.rag import WorldBible
from xkx.orchestrator.state_machine import Job, JobState, TransitionError


class FakeLLMClient:
    """测试用 LLMClient：按队列返回 YAML 字符串。"""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []
        self.model = "fake"

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        self.calls.append(messages)
        if not self.responses:
            raise RuntimeError("FakeLLMClient 响应耗尽")
        return self.responses.pop(0)


@pytest.fixture
def bible() -> WorldBible:
    return WorldBible(
        theme="wuxia",
        region="xueshan",
        known_room_ids=["xueshan/r1"],
        known_npc_ids=[],
    )


def _room_yaml(
    room_id: str = "xueshan/r1",
    exits: dict[str, str] | None = None,
) -> str:
    exits = exits or {}
    if exits:
        exits_part = "exits:\n" + "\n".join(
            f"    {k}: {v}" for k, v in exits.items()
        )
    else:
        exits_part = "exits: {}"
    return (
        f"id: {room_id}\n"
        "short: 山路\n"
        "long: 一条山路\n"
        "objects: {}\n"
        "items: []\n"
        "outdoors: true\n"
        "no_fight: false\n"
        "doors: {}\n"
        f"{exits_part}\n"
    )


def test_state_machine_valid_transition():
    job = Job(intent={}, bible=WorldBible(), output_dir=Path("/tmp"))
    job.transition(JobState.PLANNING)
    job.transition(JobState.GENERATING)
    assert job.state == JobState.GENERATING


def test_state_machine_invalid_transition_raises():
    job = Job(intent={}, bible=WorldBible(), output_dir=Path("/tmp"))
    with pytest.raises(TransitionError):
        job.transition(JobState.APPROVED)


def test_topological_sort_dependencies():
    from xkx.orchestrator.capabilities import generate_plan

    intent = {
        "assets": [
            {"type": "room", "id": "xueshan/r1", "lpc": "/tmp/r1.c"},
            {
                "type": "npc",
                "id": "xueshan/npc/n1",
                "lpc": "/tmp/n1.c",
                "depends_on": ["room:xueshan/r1"],
            },
        ]
    }
    plan = generate_plan(intent, WorldBible())
    assert [t.asset_id for t in plan] == ["xueshan/r1", "xueshan/npc/n1"]


def test_orchestrator_one_shot_approved(tmp_path: Path, bible: WorldBible):
    lpc_path = tmp_path / "r1.c"
    lpc_path.write_text("// test lpc\n", encoding="utf-8")
    llm = FakeLLMClient([_room_yaml()])
    orchestrator = Orchestrator(
        llm=llm,
        bible=bible,
        output_dir=tmp_path,
        max_revisions=1,
        verifiers=[WorldGraphReachability(), SchemaValidatorMCP(), PrecheckMCP()],
    )
    intent_path = tmp_path / "intent.yaml"
    intent_path.write_text(
        "cpk_id: demo\n"
        "theme: wuxia\n"
        "entry_scene: xueshan/r1\n"
        "assets:\n"
        "  - type: room\n"
        "    id: xueshan/r1\n"
        f"    lpc: {lpc_path}\n",
        encoding="utf-8",
    )
    job = orchestrator.create_job(intent_path)
    orchestrator.run(job)
    assert job.state == JobState.APPROVED
    assert (job.output_dir / "manifest.yaml").exists()
    assert (job.output_dir / "rooms.yaml").exists()
    assert (job.output_dir / "_review.json").exists()


def test_orchestrator_revision_then_approved(tmp_path: Path, bible: WorldBible):
    lpc_path = tmp_path / "r1.c"
    lpc_path.write_text("// test lpc\n", encoding="utf-8")
    llm = FakeLLMClient([
        _room_yaml(exits={"east": "xueshan/unknown"}),
        _room_yaml(),
    ])
    orchestrator = Orchestrator(
        llm=llm,
        bible=bible,
        output_dir=tmp_path,
        max_revisions=2,
        verifiers=[WorldGraphReachability(), SchemaValidatorMCP(), PrecheckMCP()],
    )
    intent_path = tmp_path / "intent.yaml"
    intent_path.write_text(
        "cpk_id: demo\n"
        "theme: wuxia\n"
        "entry_scene: xueshan/r1\n"
        "assets:\n"
        "  - type: room\n"
        "    id: xueshan/r1\n"
        f"    lpc: {lpc_path}\n",
        encoding="utf-8",
    )
    job = orchestrator.create_job(intent_path)
    orchestrator.run(job)
    assert job.state == JobState.APPROVED
    assert job.revision_count == 1


def test_orchestrator_max_revisions_rejected(tmp_path: Path, bible: WorldBible):
    lpc_path = tmp_path / "r1.c"
    lpc_path.write_text("// test lpc\n", encoding="utf-8")
    llm = FakeLLMClient([
        _room_yaml(exits={"east": "xueshan/unknown"}),
        _room_yaml(exits={"east": "xueshan/unknown"}),
    ])
    orchestrator = Orchestrator(
        llm=llm,
        bible=bible,
        output_dir=tmp_path,
        max_revisions=1,
        verifiers=[WorldGraphReachability(), SchemaValidatorMCP(), PrecheckMCP()],
    )
    intent_path = tmp_path / "intent.yaml"
    intent_path.write_text(
        "cpk_id: demo\n"
        "theme: wuxia\n"
        "entry_scene: xueshan/r1\n"
        "assets:\n"
        "  - type: room\n"
        "    id: xueshan/r1\n"
        f"    lpc: {lpc_path}\n",
        encoding="utf-8",
    )
    job = orchestrator.create_job(intent_path)
    orchestrator.run(job)
    assert job.state == JobState.REJECTED
    assert job.revision_count == 1
