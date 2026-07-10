"""层1：事件规则 condition -> action（唯一规则表示层）。

覆盖 LPC 事件钩子（S1 仅 ``valid_leave``）。薄求值子模块管事件触发即时求值，
**不命名"引擎"、不建独立框架**（02 Q2 裁决）。

规则冲突解决：显式 priority + deny-wins（对齐 LPC ``notify_fail``）+ 首匹配
（03 §二）。533 ``valid_leave`` 实证层1 是正确抽象层（05 §三 Q2）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# S1 支持的事件
EVENT_VALID_LEAVE = "valid_leave"

# 谓词类型（S1 最小集；扩充需 ADR，防层1 原语蠕变 -- 05 §五 dissent 3）
PRED_ALWAYS = "always"
PRED_ATTR_LT = "attr_lt"  # actor 属性 < value
PRED_AGE_LT = "age_lt"  # actor 年龄 < value
PRED_PRESENT_NPC = "present_npc"  # 房间内有指定 NPC
PRED_HAS_FLAG = "has_flag"  # actor 有标记

ACTION_DENY = "deny"
ACTION_ALLOW = "allow"


class Predicate(BaseModel):
    """条件谓词（S1 最小集）。"""

    kind: str = PRED_ALWAYS
    attr: str = ""  # attr_lt 的属性名
    value: int = 0
    npc_id: str = ""  # present_npc
    flag: str = ""  # has_flag


class EventRule(BaseModel):
    """事件规则：condition -> action。"""

    id: str
    event: str  # EVENT_VALID_LEAVE
    condition: Predicate = Field(default_factory=Predicate)
    action: str  # ACTION_DENY | ACTION_ALLOW
    priority: int = 0
    message: str = ""  # deny 时给玩家的消息


@dataclass
class EvalContext:
    """valid_leave 求值上下文（S1-4 由 ECS 构造）。"""

    actor_attrs: dict[str, int] = field(default_factory=dict)
    actor_flags: set[str] = field(default_factory=set)
    dir: str = ""
    npc_ids_in_room: set[str] = field(default_factory=set)


def eval_predicate(p: Predicate, ctx: EvalContext) -> bool:
    """求值单个谓词。"""
    if p.kind == PRED_ALWAYS:
        return True
    if p.kind == PRED_ATTR_LT:
        return ctx.actor_attrs.get(p.attr, 0) < p.value
    if p.kind == PRED_AGE_LT:
        return ctx.actor_attrs.get("age", 0) < p.value
    if p.kind == PRED_PRESENT_NPC:
        return p.npc_id in ctx.npc_ids_in_room
    if p.kind == PRED_HAS_FLAG:
        return p.flag in ctx.actor_flags
    return False


def evaluate(rules: list[EventRule], ctx: EvalContext) -> tuple[bool, str]:
    """求值 valid_leave 规则：deny-wins（任一 deny 命中即拒）。

    按 priority 降序遍历；deny 命中立即返回拒绝；allow 命中不短路（继续找
    更低优先级的 deny，因 deny-wins）。无 deny 命中则允许。
    """
    for rule in sorted(rules, key=lambda r: -r.priority):
        if rule.event != EVENT_VALID_LEAVE:
            continue
        if eval_predicate(rule.condition, ctx) and rule.action == ACTION_DENY:
            return (False, rule.message)
        # allow 命中不短路：deny-wins
    return (True, "")


def load_rules(path: Path | str) -> list[EventRule]:
    """从 YAML 加载规则列表。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [EventRule(**r) for r in (data or [])]
