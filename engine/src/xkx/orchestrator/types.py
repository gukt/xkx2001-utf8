"""Orchestrator 共享数据类型（避免循环导入）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WorldBible:
    """世界圣经：约束创作者意图的一致性上下文。"""

    theme: str = ""
    region: str = ""
    style_guide: str = ""
    known_room_ids: list[str] = field(default_factory=list)
    known_npc_ids: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


@dataclass
class AssetTask:
    """单个资产生成任务。"""

    asset_type: str
    asset_id: str
    lpc_path: str
    depends_on: list[str] = field(default_factory=list)
    event_type: str = ""  # 仅 rule 资产使用
