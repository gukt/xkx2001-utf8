"""通用条件表达式求值器最小版（10 号票，块 A 地基 A2）。

是门条件 / 物品使用限制 / NPC 行为条件三类动态规则的**共同条件子语言地基**
（spec 块 A user story 8、40），替代 LPC 散落各处字符串 ``if`` 比较的反例
（research/03-nature.md「Nature」节）。M1 只求值、不解析--表达式由结构化
Python 字面量构造，B 块 Nature 落地时 ``NatureState`` 实现 ``ConditionContext``
协议即可接入真实查询，求值器无感切换（依赖倒置：求值器依赖协议，不依赖具体
NatureState，spec 块 B user story 17/19）。

**表达式形状按"未来可换受限 AST"设计**（避坑清单 §F，spec 块 A user story 9）：

- 五种 frozen dataclass 节点构成**白名单运算符集合**（谓词 / 相等 / and / or /
  not），没有裸 Python lambda、没有 ``eval``、没有字符串解析--M3 落地受限 AST
  解析器时，解析器产出这些节点即可，**字段形状不变**。
- 节点是纯数据，求值只读 ``context`` 属性，**无副作用**；树状嵌套**无循环**；
- ``MAX_DEPTH`` 守卫锁定**深度上限**。M1 阶段表达式由构造者保证无环，守卫是
  防御性 + 声明设计意图，M3 解析器复用同形字段即可套用真正的深度约束。

纯函数：``evaluate`` / ``evaluate_any`` / ``evaluate_all`` 都不依赖其他引擎模块
（只依赖 ``ConditionContext`` 协议），可独立直测（spec §测试 seam「条件求值器
纯函数直测」）。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

# 字面量值类型。M1 只测 ``str``（``phase == "night"``），但形状按受限 AST 设计
# 保留 ``int`` / ``float`` / ``bool``，未来加数值比较（``weight > 10``）无需改
# ``Equals`` 字段形状（避坑清单 §F）。
Value = str | int | float | bool


@runtime_checkable
class ConditionContext(Protocol):
    """条件求值的查询协议：求值器只通过这个协议读世界状态，不直接依赖 NatureState。

    M1 用 ``StubContext``（本模块）注入任意测试值；B 块 Nature 落地时
    ``NatureState`` 实现这个协议，求值器零改动接入真实时辰 / 天气查询（依赖
    倒置）。未来扩展查询面（如玩家在场、季节）只需往协议加属性，旧 handler
    不破坏（增量扩展）。

    用 ``@runtime_checkable`` 让契约测试能 ``isinstance`` 断言 stub / 真实
    实现都符合协议（见 ``test_conditions.TestStubContextProtocol``，与
    ``events.TickContext`` 契约测试同思路）。
    """

    @property
    def phase(self) -> str:
        """当前时辰名（如 ``"night"`` / ``"day"`` / ``"dawn"``），供 ``phase == X`` 比较。"""
        ...

    @property
    def is_night(self) -> bool:
        """是否夜里（高阶概念，未必只是 ``phase == "night"``）。"""
        ...

    @property
    def is_day(self) -> bool:
        """是否白天。"""
        ...

    @property
    def is_raining(self) -> bool:
        """是否在下雨。"""
        ...


# ---- 表达式节点：结构化字面量，受限 AST 的可解析形状 ----


@dataclass(frozen=True)
class Predicate:
    """字面量谓词：查 ``context`` 上某 ``bool`` 属性（``is_night`` / ``is_day`` / ``is_raining``）。

    只接受 ``bool`` 属性--非 bool 属性（如 ``phase`` 是 ``str``）应走 ``Equals``
    比较，类型不符在求值时抛 ``ConditionError``，避免静默把 ``"night"`` 当真值。
    """

    name: str  # context 协议上的 bool 属性名


@dataclass(frozen=True)
class Equals:
    """相等比较：查 ``context`` 上某属性 == 字面量值，如 ``phase == "night"``。"""

    field: str  # context 协议上的属性名
    value: Value  # 字面量值，如 "night"


@dataclass(frozen=True)
class And:
    """逻辑与：所有子条件都真才真。空 ``parts`` 视为真（``all([])`` 语义）。"""

    parts: tuple[Condition, ...]


@dataclass(frozen=True)
class Or:
    """逻辑或：任一子条件为真即真。空 ``parts`` 视为假（``any([])`` 语义）。"""

    parts: tuple[Condition, ...]


@dataclass(frozen=True)
class Not:
    """逻辑非：取反子条件。"""

    operand: Condition


# 条件表达式 = 上述五种节点之一。``from __future__ import annotations`` 让
# ``And`` / ``Or`` / ``Not`` 的字段注解延迟求值，此别名可定义在节点之后。
Condition = Predicate | Equals | And | Or | Not


@dataclass
class StubContext:
    """M1 stub：可注入任意 ``phase`` / ``is_night`` / ``is_day`` / ``is_raining`` 的测试 context。

    B 块 Nature 落地时 ``NatureState`` 实现同一 ``ConditionContext`` 协议替换本 stub。
    非 frozen：Nature 状态是运行时态（时辰会推进），可变更符合语义；frozen 的约束
    留给表达式节点（纯数据、可哈希、可作 dict key / 存档值）。
    """

    phase: str = "day"
    is_night: bool = False
    is_day: bool = True
    is_raining: bool = False


class ConditionError(ValueError):
    """条件表达式形状 / 求值错误：未知谓词名、未知字段、谓词非 bool、深度超限、未知节点。"""


# 受限 AST 深度上限（避坑清单 §F）。M1 表达式由构造者保证无环，守卫是防御性 +
# 声明设计意图；M3 受限 AST 解析器解析外部字符串时这套深度约束真正生效。
MAX_DEPTH = 32


def evaluate(condition: Condition, context: ConditionContext) -> bool:
    """求值单个条件表达式，返回 ``True`` / ``False``。

    纯函数：只读 ``context``、无副作用。形状 / 求值错误抛 ``ConditionError``
    （未知谓词名、未知字段、谓词非 bool、深度超限、未知节点类型）。
    """
    return _evaluate(condition, context, 0)


def evaluate_any(rules: Iterable[Condition], context: ConditionContext) -> bool:
    """多规则按 ``any`` 聚合（§12 不互斥）：任一规则成立即真。

    **不短路**：先全部求值再聚合（与 ``events.dispatch`` 同一"多规则不互斥"精神
    --每条规则独立参与判定，不是 ``if/elif`` 互斥选择）。条件虽是纯查询无副作用，
    但显式展开让"坏规则"在第二条位置也能被求值暴露，而非被短路吞掉。
    """
    results = [evaluate(rule, context) for rule in rules]
    return any(results)


def evaluate_all(rules: Iterable[Condition], context: ConditionContext) -> bool:
    """多规则按 ``all`` 聚合（§12 不互斥）：所有规则都成立才真。不短路（同 ``evaluate_any``）。"""
    results = [evaluate(rule, context) for rule in rules]
    return all(results)


def _evaluate(condition: Condition, context: ConditionContext, depth: int) -> bool:
    if depth > MAX_DEPTH:
        raise ConditionError(f"condition nesting exceeds max depth {MAX_DEPTH}")
    match condition:
        case Predicate():
            return _lookup_bool(condition.name, context)
        case Equals():
            return _lookup(condition.field, context) == condition.value
        case And():
            return all(_evaluate(part, context, depth + 1) for part in condition.parts)
        case Or():
            return any(_evaluate(part, context, depth + 1) for part in condition.parts)
        case Not():
            return not _evaluate(condition.operand, context, depth + 1)
        case _:
            raise ConditionError(f"unknown condition node: {condition!r}")


def _lookup(field: str, context: ConditionContext) -> object:
    """从 context 读属性，未知属性抛 ``ConditionError``（不静默当 None）。"""
    try:
        return getattr(context, field)
    except AttributeError:
        raise ConditionError(f"unknown context field: {field!r}") from None


def _lookup_bool(field: str, context: ConditionContext) -> bool:
    """读 context 的 bool 属性；非 bool 值抛 ``ConditionError``。

    字面量谓词只用于 bool 属性--``phase`` 这类 ``str`` 属性应走 ``Equals`` 比较，
    误用谓词在求值时即暴露，而非把 ``"night"`` 当真值静默通过。
    """
    value = _lookup(field, context)
    if not isinstance(value, bool):
        raise ConditionError(f"predicate {field!r} must be bool, got {type(value).__name__}")
    return value


__all__ = [
    "MAX_DEPTH",
    "And",
    "Condition",
    "ConditionContext",
    "ConditionError",
    "Equals",
    "Not",
    "Or",
    "Predicate",
    "StubContext",
    "Value",
    "evaluate",
    "evaluate_all",
    "evaluate_any",
]
