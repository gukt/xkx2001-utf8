"""层1：事件规则 condition -> action（唯一规则表示层）。

覆盖 LPC 事件钩子：``valid_leave``（S1）+ ``accept_object``（S4 ADR-0006）。
薄求值子模块管事件触发即时求值，**不命名"引擎"、不建独立框架**（02 Q2 裁决）。

规则冲突解决：``valid_leave`` 用显式 priority + deny-wins（对齐 LPC ``notify_fail``）；
``accept_object`` 用首匹配（给物品是一次性事件，第一个匹配规则触发）。
533 ``valid_leave`` 实证层1 是正确抽象层（05 §三 Q2）。

S4 扩充（ADR-0005）：方向绑定（``dir``）+ 组合谓词（``all``/``any``/``not``）
+ ``family_eq``/``has_item`` 叶子。
S4 扩充（ADR-0006）：``accept_object`` 事件 + ``set_flag`` 副作用 action +
``npc_id``/``item_id`` 绑定。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

# 支持的事件
EVENT_VALID_LEAVE = "valid_leave"
EVENT_ACCEPT_OBJECT = "accept_object"  # S4 ADR-0006

# 谓词类型（S1 最小集 + S4 扩充；扩充需 ADR，防层1 原语蠕变 -- 05 §五 dissent 3）
PRED_ALWAYS = "always"
PRED_ATTR_LT = "attr_lt"  # actor 属性 < value
PRED_AGE_LT = "age_lt"  # actor 年龄 < value
PRED_PRESENT_NPC = "present_npc"  # 房间内有指定 NPC
PRED_HAS_FLAG = "has_flag"  # actor 有标记
# S4（ADR-0005）
PRED_FAMILY_EQ = "family_eq"  # actor 门派 == value（LPC family/family_name）
PRED_HAS_ITEM = "has_item"  # actor 持有指定物品（LPC present(obj, me)）

ACTION_DENY = "deny"
ACTION_ALLOW = "allow"
ACTION_SET_FLAG = "set_flag"  # S4 ADR-0006：设置 actor 标记（LPC set_temp("marks/X")）


class Predicate(BaseModel):
    """条件谓词。叶子（kind）或组合（all/any/not）。

    组合节点优先于 kind：若 all/any/not 非空则递归求值，忽略 kind。
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: str = PRED_ALWAYS
    attr: str = ""  # attr_lt 的属性名
    value: int = 0
    npc_id: str = ""  # present_npc
    flag: str = ""  # has_flag
    family: str = ""  # family_eq（LPC family/family_name）
    item_id: str = ""  # has_item（LPC present(obj, me)）

    # 组合节点（S4 ADR-0005）；空/None = 非组合，走叶子 kind
    all: list[Predicate] = Field(default_factory=list)
    any: list[Predicate] = Field(default_factory=list)
    not_: Predicate | None = Field(default=None, alias="not")


class EventRule(BaseModel):
    """事件规则：condition -> action。

    ``dir`` 方向绑定（S4 ADR-0005）：空 = 全方向生效（向后兼容 S1-S3）；
    非空 = 仅该方向匹配时规则参与求值（对齐 LPC ``valid_leave(me, dir)`` 的
    ``if (dir == "north")`` 分支）。仅 valid_leave 用。

    ``npc_id`` / ``item_id``（S4 ADR-0006）：accept_object 事件的 NPC + 物品绑定。
    ``flag``：set_flag action 设置的标记名（LPC ``set_temp("marks/X", 1)``）。
    """

    id: str
    event: str  # EVENT_VALID_LEAVE | EVENT_ACCEPT_OBJECT
    condition: Predicate = Field(default_factory=Predicate)
    action: str  # ACTION_DENY | ACTION_ALLOW | ACTION_SET_FLAG
    priority: int = 0
    message: str = ""  # 触发时给玩家的消息
    dir: str = ""  # 方向绑定（S4 ADR-0005），仅 valid_leave
    # S4 ADR-0006：accept_object 绑定
    npc_id: str = ""  # 目标 NPC（accept_object）
    item_id: str = ""  # 给的物品（accept_object）
    flag: str = ""  # set_flag 设置的标记名


@dataclass
class EvalContext:
    """事件求值上下文（由 ECS 构造）。

    valid_leave 用 dir/npc_ids_in_room；accept_object 用 npc_id/item_id。
    """

    actor_attrs: dict[str, int] = field(default_factory=dict)
    actor_flags: set[str] = field(default_factory=set)
    dir: str = ""
    npc_ids_in_room: set[str] = field(default_factory=set)
    # S4（ADR-0005）
    actor_family: str = ""
    actor_items: set[str] = field(default_factory=set)
    # S4（ADR-0006）：accept_object 上下文
    npc_id: str = ""  # 目标 NPC prototype_id
    item_id: str = ""  # 给的物品 id


@dataclass
class AcceptObjectResult:
    """accept_object 求值结果（S4 ADR-0006）。"""

    accepted: bool = True  # 是否接受物品
    set_flag: str = ""  # 非空则调用方设置 actor 此标记
    message: str = ""


def eval_predicate(p: Predicate, ctx: EvalContext) -> bool:
    """求值单个谓词（叶子或组合）。"""
    # 组合节点优先
    if p.all:
        return all(eval_predicate(sub, ctx) for sub in p.all)
    if p.any:
        return any(eval_predicate(sub, ctx) for sub in p.any)
    if p.not_ is not None:
        return not eval_predicate(p.not_, ctx)

    # 叶子谓词
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
    if p.kind == PRED_FAMILY_EQ:
        return ctx.actor_family == p.family
    if p.kind == PRED_HAS_ITEM:
        return p.item_id in ctx.actor_items
    return False


def evaluate(rules: list[EventRule], ctx: EvalContext) -> tuple[bool, str]:
    """求值 valid_leave 规则：deny-wins（任一 deny 命中即拒）。

    按 priority 降序遍历；方向不匹配（``rule.dir`` 非空且 ``!= ctx.dir``）的规则
    跳过（S4 ADR-0005 方向绑定）；deny 命中立即返回拒绝；allow 命中不短路
    （继续找更低优先级的 deny，因 deny-wins）。无 deny 命中则允许。
    """
    for rule in sorted(rules, key=lambda r: -r.priority):
        if rule.event != EVENT_VALID_LEAVE:
            continue
        if rule.dir and rule.dir != ctx.dir:
            continue  # 方向绑定：非目标方向的规则不参与
        if eval_predicate(rule.condition, ctx) and rule.action == ACTION_DENY:
            return (False, rule.message)
        # allow 命中不短路：deny-wins
    return (True, "")


def evaluate_accept_object(rules: list[EventRule], ctx: EvalContext) -> AcceptObjectResult:
    """求值 accept_object 规则：首匹配（S4 ADR-0006）。

    按 priority 降序遍历；找第一个 ``event=accept_object`` + ``npc_id`` 匹配 +
    ``item_id`` 匹配 + condition 命中的规则。命中则按 action 返回
    （set_flag=接受+设标记 / deny=拒绝 / allow=接受）。无命中则默认接受。
    """
    for rule in sorted(rules, key=lambda r: -r.priority):
        if rule.event != EVENT_ACCEPT_OBJECT:
            continue
        if rule.npc_id and rule.npc_id != ctx.npc_id:
            continue
        if rule.item_id and rule.item_id != ctx.item_id:
            continue
        if not eval_predicate(rule.condition, ctx):
            continue
        # 首匹配
        if rule.action == ACTION_SET_FLAG:
            return AcceptObjectResult(accepted=True, set_flag=rule.flag, message=rule.message)
        if rule.action == ACTION_DENY:
            return AcceptObjectResult(accepted=False, message=rule.message)
        # allow
        return AcceptObjectResult(accepted=True, message=rule.message)
    return AcceptObjectResult(accepted=True)


def load_rules(path: Path | str) -> list[EventRule]:
    """从 YAML 加载规则列表。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [EventRule(**r) for r in (data or [])]
