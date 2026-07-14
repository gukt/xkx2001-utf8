"""生成编排（ADR-0036）：build prompt -> call LLM -> 解析 YAML。

每个 generate_* 返回 v0 dict（LLM 原始产出，未经人工修订）。v0 落盘后由人工
修订为 v1 入 CPK，measure_revision 度量 v0->v1 semantic_ratio（kill criteria 5）。
"""

from __future__ import annotations

import re
from typing import Any

import yaml

from xkx.content_gen.llm_client import LLMClient
from xkx.content_gen.prompts import (
    build_item_prompt,
    build_npc_prompt,
    build_quest_prompt,
    build_room_prompt,
    build_skill_prompt,
)

_FENCE_RE = re.compile(r"```(?:ya?ml|yaml)?\s*\n(.*?)```", re.DOTALL)


def extract_yaml(text: str) -> str:
    """从 LLM 响应提取 YAML 文本。

    优先取 ```` ```yaml ... ``` ```` 围栏；无围栏则去掉常见前后解释文字（取第一个
    YAML 语义行 ``key:`` 或 ``- `` 到末尾）。
    """
    m = _FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    # 无围栏：定位首个 YAML 行（key: 或 - ）
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        stripped = ln.strip()
        if stripped and (":" in stripped or stripped.startswith("- ")):
            start = i
            break
    return "\n".join(lines[start:]).strip()


def _parse(text: str) -> Any:
    """解析 LLM 响应为 Python 对象（dict 或 list）。"""
    yaml_text = extract_yaml(text)
    if not yaml_text:
        raise ValueError("LLM 响应无可解析 YAML")
    return yaml.safe_load(yaml_text)


def generate_npc(llm: LLMClient, lpc_source: str, npc_id: str) -> dict[str, Any]:
    """生成 NpcDef v0 dict（含可选 apprentice 拜师配置）。"""
    raw = llm.chat(build_npc_prompt(lpc_source, npc_id))
    data = _parse(raw)
    if not isinstance(data, dict):
        raise ValueError(f"generate_npc({npc_id}) 期望 dict，得到 {type(data).__name__}")
    data.setdefault("id", npc_id)
    return data


def generate_skill(llm: LLMClient, lpc_source: str, skill_id: str) -> dict[str, Any]:
    """生成 SkillData v0 dict（练功 bool stub，rich 条件 GAP 注释）。"""
    raw = llm.chat(build_skill_prompt(lpc_source, skill_id))
    data = _parse(raw)
    if not isinstance(data, dict):
        raise ValueError(f"generate_skill({skill_id}) 期望 dict，得到 {type(data).__name__}")
    data.setdefault("skill_id", skill_id)
    return data


def generate_quest(llm: LLMClient, lpc_source: str, quest_id: str) -> dict[str, Any]:
    """生成 QuestDef v0 dict（多步 objectives + time-gate）。"""
    raw = llm.chat(build_quest_prompt(lpc_source, quest_id))
    data = _parse(raw)
    if not isinstance(data, dict):
        raise ValueError(f"generate_quest({quest_id}) 期望 dict，得到 {type(data).__name__}")
    data.setdefault("id", quest_id)
    return data


def generate_room(
    llm: LLMClient,
    lpc_source: str,
    room_id: str,
    known_room_ids: list[str] | None = None,
    known_npc_ids: list[str] | None = None,
) -> dict[str, Any]:
    """生成 RoomDef v0 dict。

    known_room_ids / known_npc_ids：注入范围裁剪指令，消除幻觉引用（第 4 轮）。
    """
    raw = llm.chat(build_room_prompt(lpc_source, room_id, known_room_ids, known_npc_ids))
    data = _parse(raw)
    if not isinstance(data, dict):
        raise ValueError(f"generate_room({room_id}) 期望 dict，得到 {type(data).__name__}")
    data.setdefault("id", room_id)
    return data


def generate_item(llm: LLMClient, lpc_source: str, item_id: str) -> dict[str, Any]:
    """生成 ItemDef v0 dict。"""
    raw = llm.chat(build_item_prompt(lpc_source, item_id))
    data = _parse(raw)
    if not isinstance(data, dict):
        raise ValueError(f"generate_item({item_id}) 期望 dict，得到 {type(data).__name__}")
    data.setdefault("id", item_id)
    return data
