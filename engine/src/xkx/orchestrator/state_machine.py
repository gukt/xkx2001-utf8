"""Orchestrator 状态机与 Job 模型。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from xkx.orchestrator.types import AssetTask, WorldBible


class JobState(StrEnum):
    """创作任务状态。"""

    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    VALIDATING = "validating"
    REVISING = "revising"
    PRECHECKING = "prechecking"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"


class TransitionError(ValueError):
    """非法状态跳转。"""


@dataclass
class Job:
    """创作任务。"""

    intent: dict
    bible: WorldBible
    output_dir: Path
    max_revisions: int = 3
    plan: list[AssetTask] = field(default_factory=list)
    assets: dict[str, dict] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    revision_count: int = 0
    state: JobState = JobState.PENDING
    trace: list[dict] = field(default_factory=list)
    token_estimate: int = 0
    review_status: str = "pending"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def transition(self, new_state: JobState) -> None:
        """执行状态跳转；非法跳转抛 TransitionError。"""
        if new_state not in _TRANSITIONS[self.state]:
            raise TransitionError(
                f"非法状态跳转: {self.state.value} -> {new_state.value}"
            )
        self.state = new_state
        self.trace.append({"state": new_state.value})


_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.PENDING: {JobState.PLANNING, JobState.REJECTED},
    JobState.PLANNING: {JobState.GENERATING, JobState.REJECTED},
    JobState.GENERATING: {JobState.VALIDATING, JobState.REJECTED},
    JobState.VALIDATING: {
        JobState.VALIDATING,
        JobState.REVISING,
        JobState.PRECHECKING,
        JobState.REJECTED,
    },
    JobState.REVISING: {JobState.VALIDATING, JobState.REJECTED},
    JobState.PRECHECKING: {JobState.REVIEWING, JobState.REJECTED},
    JobState.REVIEWING: {JobState.APPROVED, JobState.REJECTED},
    JobState.APPROVED: set(),
    JobState.REJECTED: set(),
}
