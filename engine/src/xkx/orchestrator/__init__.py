"""M2/UGC 创作闭环 Orchestrator（ADR-0053）。

提供意图 -> 生成 -> MCP 校验 -> 自动修订 -> 可审核 CPK 的最小闭环。
"""

from xkx.orchestrator.loop import Orchestrator
from xkx.orchestrator.mcp import (
    MCPFinding,
    MCPVerifier,
    MeasureL4MCP,
    PrecheckMCP,
    SchemaValidatorMCP,
    WorldGraphReachability,
)
from xkx.orchestrator.rag import build_context, load_bible
from xkx.orchestrator.state_machine import Job, JobState, TransitionError
from xkx.orchestrator.types import AssetTask, WorldBible

__all__ = [
    "Orchestrator",
    "WorldBible",
    "load_bible",
    "build_context",
    "AssetTask",
    "Job",
    "JobState",
    "TransitionError",
    "MCPFinding",
    "MCPVerifier",
    "WorldGraphReachability",
    "SchemaValidatorMCP",
    "PrecheckMCP",
    "MeasureL4MCP",
]
