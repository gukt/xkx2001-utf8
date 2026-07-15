"""最小 RAG：WorldBible 上下文注入。"""

from __future__ import annotations

from pathlib import Path

import yaml

from xkx.orchestrator.types import AssetTask, WorldBible


def load_bible(path: Path | str) -> WorldBible:
    """从 YAML 加载世界圣经。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return WorldBible(
        theme=data.get("theme", ""),
        region=data.get("region", ""),
        style_guide=data.get("style_guide", ""),
        known_room_ids=list(data.get("known_room_ids", [])),
        known_npc_ids=list(data.get("known_npc_ids", [])),
        constraints=list(data.get("constraints", [])),
        examples=list(data.get("examples", [])),
    )


def build_context(bible: WorldBible, task: AssetTask | None = None) -> str:
    """为指定任务构造 RAG 上下文字符串。"""
    parts = [
        f"theme={bible.theme}",
        f"region={bible.region}",
    ]
    if bible.style_guide:
        parts.append(f"风格指南：{bible.style_guide}")
    if bible.constraints:
        parts.append("全局约束：\n- " + "\n- ".join(bible.constraints))
    if task and task.asset_type == "room":
        parts.append("已知房间 id：" + ", ".join(bible.known_room_ids))
        parts.append("已知 NPC id：" + ", ".join(bible.known_npc_ids))
    return "\n\n".join(parts)
