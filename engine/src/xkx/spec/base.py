"""LPC 规格提取基础类型（任务 1 / ADR-0010）。

每个核心 LPC 函数提取为 ``FunctionSpec``，含六要素：
签名 / 前置条件 / 后置条件 / 不变量 / 副作用（按交织顺序）/ 随机性。

表示格式：pydantic v2 模型，可被 hypothesis 属性测试直接消费（任务 3 衔接），
可序列化为 JSON 供 Agent 消费（M2 衔接）。提取粒度为函数级契约（非逐行翻译）。

9 层规格存放于 ``layer_a_driver.py`` ... ``layer_i_login.py``，均引用本文件的类型。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class LPCParam(BaseModel):
    """LPC 函数参数。"""

    name: str
    lpc_type: str  # LPC 类型字符串，如 "object"、"int"、"string *"
    description: str = ""
    is_varargs_tail: bool = False  # 是否 varargs 尾部参数


class FunctionSignature(BaseModel):
    """函数签名（LPC 原文 + 结构化）。"""

    name: str
    params: list[LPCParam] = Field(default_factory=list)
    return_type: str  # LPC 返回类型，如 "int"、"void"、"object"
    is_varargs: bool = False
    lpc_file: str  # 源文件相对仓库根路径
    line_range: tuple[int, int] | None = None


class Precondition(BaseModel):
    """前置条件：调用前必须满足。"""

    description: str  # 自然语言描述
    lpc_expr: str | None = None  # 对应 LPC 表达式，如 "me && living(me)"
    kind: str = "require"  # require | guard | input_constraint


class Postcondition(BaseModel):
    """后置条件：调用后保证的状态变更或返回值。"""

    description: str
    state_change: str | None = None  # 如 "victim.qi 减少"
    return_value: str | None = None  # 返回值语义，如 "1=命中, 0=未命中"
    kind: str = "ensure"  # ensure | effect | observable


class Invariant(BaseModel):
    """不变量：执行过程中保持。"""

    description: str
    lpc_expr: str | None = None  # 如 "0 <= qi <= eff_qi <= max_qi"
    scope: str = "function"  # function | class | system


class SideEffectType(StrEnum):
    """副作用类型（按 do_attack 副作用交织分类）。"""

    STATE_MUTATION = "state_mutation"  # set/query/receive_damage 等状态变更
    MESSAGE_OUTPUT = "message_output"  # message_vision/tell_room 等消息输出
    OBJECT_LIFECYCLE = "object_lifecycle"  # move/destruct/clone
    CALL_OUT = "call_out"  # 延迟调用
    PERSISTENCE = "persistence"  # save/restore
    EXTERNAL = "external"  # intermud/log 等外部副作用


class SideEffect(BaseModel):
    """副作用条目（按交织顺序排列，不得"先算后 apply"）。

    交织顺序是 do_attack 七步的关键不变量（CLAUDE.md 架构不变量），
    ``order`` 字段记录副作用发生的相对顺序，跨 message 与 state mutation。
    """

    order: int  # 交织顺序，1, 2, 3...
    kind: SideEffectType
    description: str
    lpc_call: str | None = None  # 如 "receive_damage(victim, 'qi', dmg, me)"
    target: str | None = None  # 作用对象，如 "victim.qi"


class RandomSpec(BaseModel):
    """随机性规格：LPC ``random()`` 调用的概率模型。

    combat 确定性范围 = combat-only（CLAUDE.md 架构不变量），29 处 random()
    全部提取概率模型是层 E 的核心产出。
    """

    lpc_call: str  # 原始调用，如 "random(ap+dp)"
    probability_model: str  # 如 "dp/(ap+dp) 闪避概率"
    semantic: str  # 语义，如 "闪避判定"
    seed_inputs: list[str] = Field(default_factory=list)  # 决定 RNG 的输入
    determinism_note: str | None = None  # seeded RNG 说明


class FunctionSpec(BaseModel):
    """函数级规格契约（六要素）。"""

    signature: FunctionSignature
    preconditions: list[Precondition] = Field(default_factory=list)
    postconditions: list[Postcondition] = Field(default_factory=list)
    invariants: list[Invariant] = Field(default_factory=list)
    side_effects: list[SideEffect] = Field(default_factory=list)
    random_specs: list[RandomSpec] = Field(default_factory=list)
    notes: str | None = None  # 边界 case / LPC 特殊行为说明


class LayerSpec(BaseModel):
    """单层规格集合（9 层之一）。"""

    layer_id: str  # "A".."I"
    layer_name: str  # "驱动桥梁" 等
    lpc_files: list[str]
    function_specs: list[FunctionSpec]
    cross_layer_refs: list[str] = Field(default_factory=list)  # 引用其他层的函数名
    notes: str | None = None
