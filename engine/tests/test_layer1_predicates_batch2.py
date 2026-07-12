"""ADR-0016 第二批层1 谓词集扩充测试（8 类缺口）。

覆盖 ADR-0016 决策 1-8：
1. attr_eq（actor 属性 == value）
2. is_wizard（无参叶子，wizardp(me)）
3. has_item 扩展（item_category / item_name）
4. has_flag 扩展（source=temp）
5. derived_state（busy/fighting/ghost/alive 有限集）
6. status_eq + same_object + mud_age_lt（kill.c deny）
7. has_inquiry + attr_in（ask.c 对话分支）
8. command 事件钩子（前置 deny，verb 绑定）

护栏（dissent 3）：attr_eq 仅 ==；不引入 attr_gt/le/ge；has_item 不计数；
derived_state 统一抽象；attr_in 仅字面量列表；command 仅前置 deny。
"""

from __future__ import annotations

from xkx.dsl.layer1 import (
    ACTION_DENY,
    EVENT_COMMAND,
    EvalContext,
    EventRule,
    Predicate,
    eval_predicate,
    evaluate_command,
)

# ── 决策 1：attr_eq ──────────────────────────────────────────────────


def test_attr_eq_predicate() -> None:
    """attr_eq：actor 属性 == value_str（LPC gender=="女性"）。"""
    p = Predicate(kind="attr_eq", attr="gender", value_str="女性")
    assert eval_predicate(p, EvalContext(actor_attrs={"gender": "女性"})) is True
    assert eval_predicate(p, EvalContext(actor_attrs={"gender": "男性"})) is False
    assert eval_predicate(p, EvalContext(actor_attrs={})) is False  # 缺失 = 不等


def test_attr_eq_with_str_attr_does_not_break_attr_lt() -> None:
    """actor_attrs 现存 str 值时，attr_lt 仍安全取数（非 int 当 0）。"""
    p = Predicate(kind="attr_lt", attr="age", value=18)
    # gender 是 str，但 attr_lt 取 age（int）不受影响
    assert eval_predicate(p, EvalContext(actor_attrs={"gender": "女性", "age": 15})) is True
    # age 缺失或为 str -> 当 0 -> 0<18 True
    assert eval_predicate(p, EvalContext(actor_attrs={"gender": "女性"})) is True


# ── 决策 2：is_wizard ────────────────────────────────────────────────


def test_is_wizard_predicate() -> None:
    """is_wizard：无参叶子（LPC wizardp(me)）。"""
    p = Predicate(kind="is_wizard")
    assert eval_predicate(p, EvalContext(is_wizard=True)) is True
    assert eval_predicate(p, EvalContext(is_wizard=False)) is False
    assert eval_predicate(p, EvalContext()) is False  # 默认非 wizard


# ── 决策 3：has_item 扩展（item_category / item_name） ───────────────


def test_has_item_by_category() -> None:
    """has_item item_category：actor 持有某类物品（LPC 兵刃检查）。"""
    p = Predicate(kind="has_item", item_category="weapon")
    assert eval_predicate(p, EvalContext(actor_item_categories={"weapon": True})) is True
    assert (
        eval_predicate(p, EvalContext(actor_item_categories={"armor": True})) is False
    )
    assert eval_predicate(p, EvalContext(actor_item_categories={})) is False


def test_has_item_by_name() -> None:
    """has_item item_name：actor 持有指定名称物品（LPC present("hong biao", me)）。"""
    p = Predicate(kind="has_item", item_name="hong biao")
    assert eval_predicate(p, EvalContext(actor_item_names={"hong biao"})) is True
    assert eval_predicate(p, EvalContext(actor_item_names=set())) is False


def test_has_item_id_takes_precedence() -> None:
    """三选一优先级：item_id > item_category > item_name。"""
    p = Predicate(kind="has_item", item_id="x", item_category="weapon")
    # item_id 非空 -> 仅查 item_id，category 被忽略
    assert eval_predicate(p, EvalContext(actor_items={"x"})) is True
    assert (
        eval_predicate(p, EvalContext(actor_item_categories={"weapon": True})) is False
    )


def test_has_item_all_empty_is_false() -> None:
    """三者皆空 = 不匹配（保守，避免误 deny）。"""
    p = Predicate(kind="has_item")
    assert eval_predicate(p, EvalContext(actor_items={"x"})) is False


# ── 决策 4：has_flag 扩展（source=temp） ─────────────────────────────


def test_has_flag_source_query_default() -> None:
    """has_flag 默认查 query 层（LPC query("flag")）。"""
    p = Predicate(kind="has_flag", flag="酥")
    assert eval_predicate(p, EvalContext(actor_flags={"酥"})) is True
    # temp 层标记不计入 query 层
    assert (
        eval_predicate(p, EvalContext(actor_temp_flags={"酥"})) is False
    )


def test_has_flag_source_temp() -> None:
    """has_flag source=temp：查 query_temp 层（LPC query_temp("biao")）。"""
    p = Predicate(kind="has_flag", flag="biao", flag_source="temp")
    assert eval_predicate(p, EvalContext(actor_temp_flags={"biao"})) is True
    assert eval_predicate(p, EvalContext(actor_flags={"biao"})) is False


# ── 决策 5：derived_state ────────────────────────────────────────────


def test_derived_state_predicate() -> None:
    """derived_state：actor 派生状态（LPC is_busy/is_fighting/is_ghost/living）。"""
    assert (
        eval_predicate(
            Predicate(kind="derived_state", state="busy"),
            EvalContext(actor_derived_states={"busy", "alive"}),
        )
        is True
    )
    assert (
        eval_predicate(
            Predicate(kind="derived_state", state="fighting"),
            EvalContext(actor_derived_states={"busy"}),
        )
        is False
    )
    assert (
        eval_predicate(
            Predicate(kind="derived_state", state="ghost"), EvalContext()
        )
        is False
    )


# ── 决策 6：status_eq + same_object + mud_age_lt ──────────────────────


def test_status_eq_exists() -> None:
    """status_eq value_str 空 = 标记存在（任意值）。"""
    p = Predicate(kind="status_eq", flag="surrender/ownder", flag_source="temp")
    assert (
        eval_predicate(p, EvalContext(actor_temp_flags={"surrender/ownder"})) is True
    )
    assert eval_predicate(p, EvalContext(actor_temp_flags=set())) is False


def test_status_eq_value_match() -> None:
    """status_eq value_str 非空 = 标记值 == value_str（kill.c last_persuader == target id）。

    约定集合元素形如 ``flag=value``；_flag_value 解出等号后段。
    """
    p = Predicate(
        kind="status_eq",
        flag="last_persuader",
        flag_source="temp",
        value_str="city/npc/zhang",
    )
    assert (
        eval_predicate(
            p,
            EvalContext(actor_temp_flags={"last_persuader=city/npc/zhang"}),
        )
        is True
    )
    assert (
        eval_predicate(
            p,
            EvalContext(actor_temp_flags={"last_persuader=city/npc/li"}),
        )
        is False
    )


def test_same_object_predicate() -> None:
    """same_object：actor 与 target 同一（kill.c "自身投降" target==me）。"""
    p = Predicate(kind="same_object")
    # actor_attrs["id"] == ctx.target_id -> 同一
    assert (
        eval_predicate(
            p, EvalContext(actor_attrs={"id": "player1"}, target_id="player1")
        )
        is True
    )
    assert (
        eval_predicate(
            p, EvalContext(actor_attrs={"id": "player1"}, target_id="player2")
        )
        is False
    )
    # actor 无 id -> 不匹配
    assert eval_predicate(p, EvalContext(target_id="player1")) is False


def test_mud_age_lt_predicate() -> None:
    """mud_age_lt：actor 游戏年龄 < value（kill.c mud_age < 18000 内疚门禁）。"""
    p = Predicate(kind="mud_age_lt", value=18000)
    assert eval_predicate(p, EvalContext(actor_attrs={"mud_age": 17999})) is True
    assert eval_predicate(p, EvalContext(actor_attrs={"mud_age": 18000})) is False
    assert eval_predicate(p, EvalContext(actor_attrs={})) is True  # 缺失 = 0 < 18000


# ── 决策 7：has_inquiry + attr_in ────────────────────────────────────


def test_has_inquiry_predicate() -> None:
    """has_inquiry：NPC inquiry 列表含 topic（ask.c inquiry/<topic>）。"""
    p = Predicate(kind="has_inquiry", topic="shenghuo")
    assert eval_predicate(p, EvalContext(npc_inquiries={"shenghuo", "wugong"})) is True
    assert eval_predicate(p, EvalContext(npc_inquiries={"wugong"})) is False


def test_attr_in_predicate() -> None:
    """attr_in：actor 属性在字面量枚举集合中（ask.c attitude in {good,bad}）。"""
    p = Predicate(kind="attr_in", attr="attitude", values=["good", "bad"])
    assert eval_predicate(p, EvalContext(actor_attrs={"attitude": "good"})) is True
    assert eval_predicate(p, EvalContext(actor_attrs={"attitude": "bad"})) is True
    assert eval_predicate(p, EvalContext(actor_attrs={"attitude": "peaceful"})) is False
    assert eval_predicate(p, EvalContext(actor_attrs={})) is False


def test_attr_in_empty_values_is_false() -> None:
    """attr_in 空列表 = 永不命中（护栏：仅字面量列表，不开放任意匹配）。"""
    p = Predicate(kind="attr_in", attr="attitude", values=[])
    assert eval_predicate(p, EvalContext(actor_attrs={"attitude": "good"})) is False


# ── 决策 8：command 事件钩子 ─────────────────────────────────────────


def _cmd_rule(
    condition: Predicate, verb: str = "", message: str = "", id: str = "r"
) -> EventRule:
    return EventRule(
        id=id,
        event=EVENT_COMMAND,
        condition=condition,
        action=ACTION_DENY,
        verb=verb,
        message=message,
    )


def test_command_deny_verb_binding() -> None:
    """command 事件 verb 绑定：仅匹配 verb 的规则参与（对齐 add_action verb）。"""
    rule = _cmd_rule(Predicate(kind="always"), verb="knock", message="挡住")
    # verb 匹配 -> deny
    allow, msg = evaluate_command([rule], EvalContext(verb="knock"))
    assert allow is False
    assert msg == "挡住"
    # verb 不匹配 -> 放行
    allow, _ = evaluate_command([rule], EvalContext(verb="enter"))
    assert allow is True


def test_command_deny_wins() -> None:
    """command 事件 deny-wins：任一 deny 命中即拒。"""
    rules = [
        _cmd_rule(Predicate(kind="always"), verb="kill", message="不准战斗", id="d1"),
    ]
    allow, msg = evaluate_command(rules, EvalContext(verb="kill"))
    assert allow is False
    assert msg == "不准战斗"


def test_command_no_deny_allows() -> None:
    """command 无 deny 命中 -> 允许（命令主体交层3）。"""
    rules = [_cmd_rule(Predicate(kind="is_wizard"), verb="knock", message="挡")]
    # 非 wizard -> 条件不满足 -> 不 deny -> 允许
    allow, _ = evaluate_command(rules, EvalContext(verb="knock", is_wizard=False))
    assert allow is True


def test_command_verb_empty_applies_all() -> None:
    """verb 空 = 对所有 command 事件生效。"""
    rule = _cmd_rule(Predicate(kind="always"), verb="", message="挡")
    allow, _ = evaluate_command([rule], EvalContext(verb="anything"))
    assert allow is False


def test_command_ignores_other_events() -> None:
    """command 求值忽略非 command 事件规则。"""
    other = EventRule(
        id="v",
        event="valid_leave",
        condition=Predicate(kind="always"),
        action=ACTION_DENY,
        message="leave deny",
    )
    allow, _ = evaluate_command([other], EvalContext(verb="kill"))
    assert allow is True  # valid_leave 规则不参与 command 求值


def test_command_kill_deny_pattern() -> None:
    """kill.c 否决模式：目标已投降本 actor -> deny（same_object）。"""
    rule = _cmd_rule(
        Predicate(kind="same_object"),
        verb="kill",
        message="他/她已经投降了,你现在不能杀！",
    )
    # target == actor -> deny
    allow, msg = evaluate_command(
        [rule],
        EvalContext(verb="kill", actor_attrs={"id": "p1"}, target_id="p1"),
    )
    assert allow is False
    assert "投降" in msg
    # target != actor -> 允许
    allow, _ = evaluate_command(
        [rule],
        EvalContext(verb="kill", actor_attrs={"id": "p1"}, target_id="p2"),
    )
    assert allow is True


# ── 组合：新谓词与 all/any/not 嵌套 ──────────────────────────────────


def test_nested_combination_kill_immortal_pattern() -> None:
    """kill.c immortal deny 模式：is_wizard AND NOT(目标 immortal)。"""
    cond = Predicate(
        all=[
            Predicate(kind="is_wizard"),
            Predicate(
                not_=Predicate(
                    kind="derived_state", state="immortal"
                )
            ),
        ]
    )
    # actor wizard + 目标非 immortal -> deny
    assert eval_predicate(
        cond, EvalContext(is_wizard=True, actor_derived_states=set())
    ) is True
    # actor 非 wizard -> 不 deny
    assert eval_predicate(
        cond, EvalContext(is_wizard=False, actor_derived_states=set())
    ) is False
