"""Capability Registry：把创作意图拆解为可调度生成任务。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from xkx.content_gen.generate import (
    generate_item,
    generate_npc,
    generate_quest,
    generate_room,
    generate_rule,
    generate_skill,
)
from xkx.content_gen.llm_client import LLMClient
from xkx.orchestrator.types import AssetTask, WorldBible

_GENERATORS: dict[str, Callable[..., dict[str, Any]]] = {
    "room": generate_room,
    "npc": generate_npc,
    "skill": generate_skill,
    "quest": generate_quest,
    "item": generate_item,
    "rule": generate_rule,
}


CAPABILITY_NAMES: dict[str, str] = {
    "room": "worldbuilder",
    "npc": "narrator",
    "quest": "narrator",
    "item": "balancer",
    "skill": "balancer",
    "rule": "behaviorist",
}


def task_key(task: AssetTask) -> str:
    """任务唯一键。"""
    return f"{task.asset_type}:{task.asset_id}"


def generate_plan(intent: dict, bible: WorldBible) -> list[AssetTask]:
    """从意图 YAML 生成按依赖拓扑排序的 asset 任务列表。"""
    raw_assets = intent.get("assets", [])
    tasks: list[AssetTask] = []
    for entry in raw_assets:
        tasks.append(
            AssetTask(
                asset_type=entry["type"],
                asset_id=entry["id"],
                lpc_path=entry["lpc"],
                depends_on=list(entry.get("depends_on", [])),
                event_type=entry.get("event", ""),
            )
        )
    return _topo_sort(tasks)


def _topo_sort(tasks: list[AssetTask]) -> list[AssetTask]:
    """按 depends_on 做简单拓扑排序（忽略缺失依赖）。"""
    by_key = {task_key(t): t for t in tasks}
    order: list[AssetTask] = []
    visited: set[str] = set()

    def visit(task: AssetTask) -> None:
        key = task_key(task)
        if key in visited:
            return
        visited.add(key)
        for dep in task.depends_on:
            if dep in by_key:
                visit(by_key[dep])
        order.append(task)

    for task in tasks:
        visit(task)
    return order


def generate_asset(task: AssetTask, llm: LLMClient, bible: WorldBible) -> dict[str, Any]:
    """调度对应 content_gen 函数生成单个 asset dict。"""
    lpc_source = Path(task.lpc_path).read_text(
        encoding="utf-8", errors="replace"
    )
    gen_fn = _GENERATORS[task.asset_type]
    kwargs: dict[str, Any] = {}
    if task.asset_type == "room":
        kwargs["known_room_ids"] = bible.known_room_ids
        kwargs["known_npc_ids"] = bible.known_npc_ids
    elif task.asset_type == "rule":
        kwargs["event_type"] = task.event_type or "valid_leave"
    return gen_fn(llm, lpc_source, task.asset_id, **kwargs)
