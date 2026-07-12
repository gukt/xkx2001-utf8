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
阶段 2 扩充（ADR-0016 第二批）：``attr_eq``/``is_wizard``/``derived_state``/
``has_inquiry``/``attr_in`` 叶子 + ``has_item``/``has_flag`` 扩展字段 +
``status_eq``/``same_object``/``mud_age_lt`` + ``command`` 事件类型。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

# 支持的事件
EVENT_VALID_LEAVE = "valid_leave"
EVENT_ACCEPT_OBJECT = "accept_object"  # S4 ADR-0006
EVENT_COMMAND = "command"  # 阶段 2 ADR-0016：命令前置 deny 事件

# 谓词类型（S1 最小集 + S4 扩充；扩充需 ADR，防层1 原语蠕变 -- 05 §五 dissent 3）
PRED_ALWAYS = "always"
PRED_ATTR_LT = "attr_lt"  # actor 属性 < value
PRED_AGE_LT = "age_lt"  # actor 年龄 < value
PRED_PRESENT_NPC = "present_npc"  # 房间内有指定 NPC
PRED_HAS_FLAG = "has_flag"  # actor 有标记
# S4（ADR-0005）
PRED_FAMILY_EQ = "family_eq"  # actor 门派 == value（LPC family/family_name）
PRED_HAS_ITEM = "has_item"  # actor 持有指定物品（LPC present(obj, me)）
# 阶段 2（ADR-0016 第二批）
PRED_ATTR_EQ = "attr_eq"  # actor 属性 == value（LPC query("gender")=="女性"）
PRED_IS_WIZARD = "is_wizard"  # actor 是 wizard（LPC wizardp(me)）
PRED_DERIVED_STATE = "derived_state"  # 派生状态（LPC is_busy/is_fighting/is_ghost/living）
PRED_HAS_INQUIRY = "has_inquiry"  # NPC inquiry 列表含 topic（LPC inquiry/<topic>）
PRED_ATTR_IN = "attr_in"  # actor 属性在字面量枚举集合中（LPC attitude in {...}）
PRED_STATUS_EQ = "status_eq"  # actor 状态标记 == value（LPC query_temp("immortal")）
PRED_SAME_OBJECT = "same_object"  # 两对象同一（LPC 对象引用比较，命令 deny 上下文）
PRED_MUD_AGE_LT = "mud_age_lt"  # actor 游戏年龄 < value（LPC query("mud_age")）

ACTION_DENY = "deny"
ACTION_ALLOW = "allow"
ACTION_SET_FLAG = "set_flag"  # S4 ADR-0006：设置 actor 标记（LPC set_temp("marks/X")）

# has_flag 的 source 取值（ADR-0016 决策 4）：仅 query/temp 两层，不引入第三种存储
FLAG_SOURCE_QUERY = "query"  # LPC query("flag")（默认）
FLAG_SOURCE_TEMP = "temp"  # LPC query_temp("flag")


class Predicate(BaseModel):
    """条件谓词。叶子（kind）或组合（all/any/not）。

    组合节点优先于 kind：若 all/any/not 非空则递归求值，忽略 kind。
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: str = PRED_ALWAYS
    attr: str = ""  # attr_lt/attr_eq/attr_in/status_eq 的属性名
    value: int = 0  # 数值比较（attr_lt/age_lt/mud_age_lt）
    value_str: str = ""  # 字符串值（attr_eq/status_eq）
    values: list[str] = Field(default_factory=list)  # 字面量集合（attr_in）
    npc_id: str = ""  # present_npc
    flag: str = ""  # has_flag/status_eq
    flag_source: str = FLAG_SOURCE_QUERY  # has_flag 的存储层（query/temp）
    family: str = ""  # family_eq（LPC family/family_name）
    # has_item（ADR-0016 决策 3）：item_id/item_category/item_name 三选一
    item_id: str = ""  # 精确物品 id（LPC present(obj, me)）
    item_category: str = ""  # 物品类别（weapon/armor/key 等主题包注册集）
    item_name: str = ""  # 物品名称（LPC present("hong biao", me) 的名称匹配）
    # 阶段 2（ADR-0016）
    state: str = ""  # derived_state 的派生状态名（busy/fighting/ghost/alive 等）
    topic: str = ""  # has_inquiry 的提问 topic（LPC inquiry/<topic>）
    inquiry_npc: str = ""  # has_inquiry 的目标 NPC id（默认 = ctx.npc_id）

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

    ``verb``（阶段 2 ADR-0016）：command 事件的命令动词绑定（对齐 LPC
    ``add_action("do_knock", "knock")`` 的 verb）。空 = 所有 command 事件规则
    参与求值；非空 = 仅该 verb 匹配时参与。command 事件仅覆盖前置 deny
    （层1 管条件，层3 管副作用）。
    """

    id: str
    event: str  # EVENT_VALID_LEAVE | EVENT_ACCEPT_OBJECT | EVENT_COMMAND
    condition: Predicate = Field(default_factory=Predicate)
    action: str  # ACTION_DENY | ACTION_ALLOW | ACTION_SET_FLAG
    priority: int = 0
    message: str = ""  # 触发时给玩家的消息
    dir: str = ""  # 方向绑定（S4 ADR-0005），仅 valid_leave
    verb: str = ""  # 命令动词绑定（阶段 2 ADR-0016），仅 command
    # S4 ADR-0006：accept_object 绑定
    npc_id: str = ""  # 目标 NPC（accept_object）
    item_id: str = ""  # 给的物品（accept_object）
    flag: str = ""  # set_flag 设置的标记名


@dataclass
class EvalContext:
    """事件求值上下文（由 ECS 构造）。

    valid_leave 用 dir/npc_ids_in_room；accept_object 用 npc_id/item_id；
    command 用 verb/target_id（阶段 2 ADR-0016）。
    """

    # actor 属性（int 数值或 str 字面量，如 gender/attitude/mud_age）
    actor_attrs: dict[str, int | str] = field(default_factory=dict)
    actor_flags: set[str] = field(default_factory=set)  # query("flag") 层标记
    actor_temp_flags: set[str] = field(default_factory=set)  # query_temp 层标记
    dir: str = ""
    npc_ids_in_room: set[str] = field(default_factory=set)
    # S4（ADR-0005）
    actor_family: str = ""
    actor_items: set[str] = field(default_factory=set)
    # ADR-0016 决策 3：has_item 的 item_category/item_name 扩展。
    # actor_item_categories：类别 -> 是否持有（如 {"weapon": True}）。
    # actor_item_names：持有物品名称集合（LPC present("hong biao", me)）。
    actor_item_categories: dict[str, bool] = field(default_factory=dict)
    actor_item_names: set[str] = field(default_factory=set)
    # S4（ADR-0006）：accept_object 上下文
    npc_id: str = ""  # 目标 NPC prototype_id
    item_id: str = ""  # 给的物品 id
    # 阶段 2（ADR-0016）
    is_wizard: bool = False  # actor 是否 wizard（LPC wizardp）
    # 派生状态集合（actor 当前满足的派生状态，由层3 ECS 推导填充）。
    # 取值有限枚举（主题包注册）：busy/fighting/ghost/alive 等。
    actor_derived_states: set[str] = field(default_factory=set)
    # NPC 的 inquiry topic 列表（当前目标 NPC 可提问项，由层2 对话树维护）。
    # 默认取 ctx.npc_id 的 inquiry；规则可指定 inquiry_npc 覆盖。
    npc_inquiries: set[str] = field(default_factory=set)
    # command 事件上下文
    verb: str = ""  # 当前命令动词（LPC query_verb）
    target_id: str = ""  # 命令目标对象 id（LPC kill <target> 的 target，same_object 用）


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
        return _num_attr(ctx.actor_attrs, p.attr) < p.value
    if p.kind == PRED_AGE_LT:
        return _num_attr(ctx.actor_attrs, "age") < p.value
    if p.kind == PRED_PRESENT_NPC:
        return p.npc_id in ctx.npc_ids_in_room
    if p.kind == PRED_HAS_FLAG:
        return p.flag in _flag_set(ctx, p.flag_source)
    if p.kind == PRED_FAMILY_EQ:
        return ctx.actor_family == p.family
    if p.kind == PRED_HAS_ITEM:
        return _has_item_match(p, ctx)
    # 阶段 2（ADR-0016 第二批）叶子谓词
    if p.kind == PRED_ATTR_EQ:
        return _str_attr(ctx.actor_attrs, p.attr) == p.value_str
    if p.kind == PRED_IS_WIZARD:
        return ctx.is_wizard
    if p.kind == PRED_DERIVED_STATE:
        return p.state in ctx.actor_derived_states
    if p.kind == PRED_HAS_INQUIRY:
        return p.topic in ctx.npc_inquiries
    if p.kind == PRED_ATTR_IN:
        return _str_attr(ctx.actor_attrs, p.attr) in p.values
    if p.kind == PRED_STATUS_EQ:
        # 状态标记 == value：在指定存储层中存在该标记名（LPC query_temp("immortal")）。
        # value_str 空表示"标记存在"（任意值）；非空表示标记的值 == value_str
        # （约定集合元素形如 ``flag`` 或 ``flag=value``，_flag_value 解出 value）。
        flag_set = _flag_set(ctx, p.flag_source)
        if p.value_str == "":
            return p.flag in flag_set  # 仅判存在
        # 标记必须存在且值相等
        return _flag_value(ctx, p.flag_source, p.flag) == p.value_str
    if p.kind == PRED_SAME_OBJECT:
        # 两对象同一（命令 deny 上下文）：actor 与 target 同一对象。
        # 默认比较 actor 与 ctx.target_id；actor_id 由调用方填入 actor_attrs["id"]。
        actor_id = _str_attr(ctx.actor_attrs, "id")
        return bool(actor_id) and actor_id == ctx.target_id
    if p.kind == PRED_MUD_AGE_LT:
        return _num_attr(ctx.actor_attrs, "mud_age") < p.value
    return False


def _num_attr(attrs: dict[str, int | str], name: str) -> int:
    """安全取数值属性（非 int 当 0）。"""
    val = attrs.get(name, 0)
    return val if isinstance(val, int) else 0


def _str_attr(attrs: dict[str, int | str], name: str) -> str:
    """安全取字符串属性（非 str 当空串）。"""
    val = attrs.get(name, "")
    return val if isinstance(val, str) else ""


def _flag_set(ctx: EvalContext, source: str) -> set[str]:
    """按 source 取标记集合（ADR-0016 决策 4：query/temp 两层）。"""
    if source == FLAG_SOURCE_TEMP:
        return ctx.actor_temp_flags
    return ctx.actor_flags  # 默认 query 层


def _flag_value(ctx: EvalContext, source: str, flag: str) -> str:
    """取标记的值（用于 status_eq 比较）。

    层1 仅存"标记是否存在"的集合语义；标记的值比较（== value_str）由层3
    在填充 EvalContext 时把 ``flag=value`` 编码进集合，此处解出 value。
    约定：集合元素形如 ``flag`` 或 ``flag=value``；后者 value_str 取等号后段。
    """
    for item in _flag_set(ctx, source):
        if item == flag:
            return ""  # 存在但无显式值
        if item.startswith(flag + "="):
            return item[len(flag) + 1 :]
    return ""


def _has_item_match(p: Predicate, ctx: EvalContext) -> bool:
    """has_item 三选一匹配（ADR-0016 决策 3）。

    - item_id：精确物品 id（LPC present(obj, me)）
    - item_category：物品类别（weapon/armor/key，主题包注册集）
    - item_name：物品名称（LPC present("hong biao", me)）

    层1 EvalContext 仅存 actor_items 集合（id）与 actor_item_categories
    /actor_item_names 字典；三选一优先级 item_id > item_category > item_name。
    """
    if p.item_id:
        return p.item_id in ctx.actor_items
    if p.item_category:
        cats = ctx.actor_item_categories
        return bool(cats.get(p.item_category))
    if p.item_name:
        return p.item_name in ctx.actor_item_names
    return False  # 三者皆空 = 不匹配（保守，避免误 deny）


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


def evaluate_command(rules: list[EventRule], ctx: EvalContext) -> tuple[bool, str]:
    """求值 command 规则：deny-wins 前置 deny（阶段 2 ADR-0016 决策 8）。

    对齐 LPC ``add_action("do_knock", "knock")`` 的命令前置检查：命令主体
    （副作用）仍层3，层1 仅管前置 deny 条件。按 priority 降序遍历；
    verb 不匹配（``rule.verb`` 非空且 ``!= ctx.verb``）的规则跳过；
    deny 命中立即返回拒绝；allow 命中不短路（deny-wins）。无 deny 命中则允许。
    """
    for rule in sorted(rules, key=lambda r: -r.priority):
        if rule.event != EVENT_COMMAND:
            continue
        if rule.verb and rule.verb != ctx.verb:
            continue  # verb 绑定：非目标 verb 的规则不参与
        if eval_predicate(rule.condition, ctx) and rule.action == ACTION_DENY:
            return (False, rule.message)
        # allow 命中不短路：deny-wins
    return (True, "")


def load_rules(path: Path | str) -> list[EventRule]:
    """从 YAML 加载规则列表。"""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return [EventRule(**r) for r in (data or [])]
