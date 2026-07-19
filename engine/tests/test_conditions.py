"""通用条件表达式求值器的单元测试：纯函数直测（10 号票 acceptance 第 8 条）。

覆盖：字面量谓词 / 相等比较 / 布尔组合（and/or/not）/ 多规则 any/all 聚合
（§12 不互斥）/ stub context 注入与协议契约 / 形状错误与深度上限守卫
（避坑清单 §F）。按 Given/When 分组，方法名只写 Then。
"""

import pytest

from mud_engine.conditions import (
    MAX_DEPTH,
    And,
    ConditionContext,
    ConditionError,
    Equals,
    Not,
    Or,
    Predicate,
    StubContext,
    evaluate,
    evaluate_all,
    evaluate_any,
)

# 覆盖"白天/夜里 × 晴/雨"四象限的典型 stub 场景，给大多数用例复用。
DAY_DRY = StubContext(phase="day", is_night=False, is_day=True, is_raining=False)
NIGHT_DRY = StubContext(phase="night", is_night=True, is_day=False, is_raining=False)
NIGHT_RAIN = StubContext(phase="night", is_night=True, is_day=False, is_raining=True)
DAY_RAIN = StubContext(phase="day", is_night=False, is_day=True, is_raining=True)


class TestPredicate:
    def test_is_night_true_at_night(self) -> None:
        assert evaluate(Predicate("is_night"), NIGHT_DRY) is True

    def test_is_night_false_by_day(self) -> None:
        assert evaluate(Predicate("is_night"), DAY_DRY) is False

    def test_is_day_reflects_day_flag(self) -> None:
        assert evaluate(Predicate("is_day"), DAY_DRY) is True
        assert evaluate(Predicate("is_day"), NIGHT_DRY) is False

    def test_is_raining_reflects_rain_flag(self) -> None:
        assert evaluate(Predicate("is_raining"), NIGHT_RAIN) is True
        assert evaluate(Predicate("is_raining"), DAY_DRY) is False


class TestEquals:
    def test_matches_when_phase_equals_value(self) -> None:
        assert evaluate(Equals("phase", "night"), NIGHT_DRY) is True

    def test_does_not_match_when_phase_differs(self) -> None:
        assert evaluate(Equals("phase", "night"), DAY_DRY) is False

    def test_intermediate_phase_dawn(self) -> None:
        # is_night/is_day 都 False 的中间态时辰，靠 phase == X 仍可精确判定。
        dawn = StubContext(phase="dawn", is_night=False, is_day=False, is_raining=False)
        assert evaluate(Equals("phase", "dawn"), dawn) is True
        assert evaluate(Equals("phase", "night"), dawn) is False


class TestBooleanComposition:
    def test_and_requires_all_parts(self) -> None:
        cond = And((Predicate("is_night"), Predicate("is_raining")))
        assert evaluate(cond, NIGHT_RAIN) is True
        assert evaluate(cond, NIGHT_DRY) is False
        assert evaluate(cond, DAY_RAIN) is False

    def test_or_satisfies_any_part(self) -> None:
        cond = Or((Predicate("is_night"), Predicate("is_raining")))
        assert evaluate(cond, NIGHT_DRY) is True
        assert evaluate(cond, DAY_RAIN) is True
        assert evaluate(cond, DAY_DRY) is False

    def test_not_negates(self) -> None:
        assert evaluate(Not(Predicate("is_night")), DAY_DRY) is True
        assert evaluate(Not(Predicate("is_night")), NIGHT_DRY) is False

    def test_nested_and_or_not(self) -> None:
        # (is_night or is_raining) and not is_day -> "夜里或下雨，且不是白天"
        cond = And(
            (
                Or((Predicate("is_night"), Predicate("is_raining"))),
                Not(Predicate("is_day")),
            )
        )
        assert evaluate(cond, NIGHT_DRY) is True
        assert evaluate(cond, NIGHT_RAIN) is True
        assert evaluate(cond, DAY_RAIN) is False
        assert evaluate(cond, DAY_DRY) is False

    def test_empty_and_is_true(self) -> None:
        assert evaluate(And(()), DAY_DRY) is True

    def test_empty_or_is_false(self) -> None:
        assert evaluate(Or(()), DAY_DRY) is False


class TestAnyAllAggregation:
    # §12 多规则按 any/all 聚合不互斥：多条规则并存聚合判定，不是 if/elif 互斥选择。

    def test_any_true_when_any_rule_holds(self) -> None:
        rules = [Predicate("is_night"), Predicate("is_day")]
        assert evaluate_any(rules, DAY_DRY) is True
        assert evaluate_any(rules, NIGHT_DRY) is True

    def test_any_false_when_no_rule_holds(self) -> None:
        rules = [Predicate("is_night"), Predicate("is_raining")]
        assert evaluate_any(rules, DAY_DRY) is False

    def test_all_true_when_every_rule_holds(self) -> None:
        rules = [Predicate("is_night"), Predicate("is_raining")]
        assert evaluate_all(rules, NIGHT_RAIN) is True

    def test_all_false_when_any_rule_fails(self) -> None:
        rules = [Predicate("is_night"), Predicate("is_raining")]
        assert evaluate_all(rules, NIGHT_DRY) is False

    def test_empty_any_is_false(self) -> None:
        assert evaluate_any([], DAY_DRY) is False

    def test_empty_all_is_true(self) -> None:
        assert evaluate_all([], DAY_DRY) is True

    def test_any_evaluates_all_rules_not_short_circuit(self) -> None:
        # 不短路：第二条规则即使 any 已可定，仍应被求值（§12 不互斥）。
        # 用一个会抛错的坏规则放第二位，若短路则不抛、若不短路则抛。
        rules: list = [Predicate("is_day"), Predicate("no_such_predicate")]
        with pytest.raises(ConditionError):
            evaluate_any(rules, DAY_DRY)


class TestStubContextProtocol:
    def test_stub_satisfies_context_protocol(self) -> None:
        # runtime_checkable 契约：stub 实现了查询协议，B 块 NatureState 同构替换。
        assert isinstance(StubContext(), ConditionContext)

    def test_default_stub_is_daytime_dry(self) -> None:
        ctx = StubContext()
        assert ctx.phase == "day"
        assert ctx.is_night is False
        assert ctx.is_day is True
        assert ctx.is_raining is False

    def test_stub_accepts_injected_values(self) -> None:
        ctx = StubContext(phase="night", is_night=True, is_day=False, is_raining=True)
        assert evaluate(Predicate("is_raining"), ctx) is True
        assert evaluate(Equals("phase", "night"), ctx) is True


class WhenPredicateNameUnknown:
    def test_raises_condition_error(self) -> None:
        with pytest.raises(ConditionError):
            evaluate(Predicate("no_such_predicate"), DAY_DRY)


class WhenPredicateTargetsNonBoolField:
    # phase 是 str 不是 bool；字面量谓词只用于 bool 属性，phase 应走 Equals 比较。

    def test_raises_condition_error(self) -> None:
        with pytest.raises(ConditionError):
            evaluate(Predicate("phase"), DAY_DRY)


class WhenEqualsFieldUnknown:
    def test_raises_condition_error(self) -> None:
        with pytest.raises(ConditionError):
            evaluate(Equals("no_such_field", "x"), DAY_DRY)


class WhenNodeTypeUnknown:
    def test_raises_condition_error(self) -> None:
        with pytest.raises(ConditionError):
            evaluate("not_a_node", DAY_DRY)  # type: ignore[arg-type]


class TestNestingDepth:
    # 避坑清单 §F 深度上限：受限 AST 的无循环/深度约束。M1 结构化字面量由构造者
    # 保证无环，深度守卫是防御性 + 声明设计意图，M3 受限 AST 解析器复用同形字段。

    def test_depth_at_limit_is_allowed(self) -> None:
        cond = _nest_not(MAX_DEPTH)
        result = evaluate(cond, DAY_DRY)
        assert isinstance(result, bool)

    def test_depth_over_limit_raises(self) -> None:
        cond = _nest_not(MAX_DEPTH + 1)
        with pytest.raises(ConditionError):
            evaluate(cond, DAY_DRY)


def _nest_not(depth: int):
    """构造 depth 层嵌套 Not(Predicate("is_night"))。"""
    cond = Predicate("is_night")
    for _ in range(depth):
        cond = Not(cond)
    return cond
