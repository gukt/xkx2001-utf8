"""层1 事件规则 + 薄求值器测试（valid_leave + deny-wins + S4 组合谓词）。"""

from __future__ import annotations

from xkx.dsl.layer1 import (
    ACTION_DENY,
    ACTION_SET_FLAG,
    EVENT_ACCEPT_OBJECT,
    EVENT_VALID_LEAVE,
    EvalContext,
    EventRule,
    Predicate,
    evaluate,
    evaluate_accept_object,
)


def _ctx(**kw):  # type: ignore[no-untyped-def]
    return EvalContext(**kw)


def _rule(condition: Predicate, message: str = "", id: str = "r", **kw) -> EventRule:  # type: ignore[no-untyped-def]
    return EventRule(
        id=id,
        event=EVENT_VALID_LEAVE,
        condition=condition,
        action=ACTION_DENY,
        message=message,
        **kw,
    )


# --- S1 基础谓词 ---


def test_allow_when_no_rule() -> None:
    allow, msg = evaluate([], _ctx())
    assert allow is True
    assert msg == ""


def test_deny_age_lt() -> None:
    """仿 duchang：age<18 不得离开。"""
    rule = _rule(Predicate(kind="age_lt", value=18), "小毛孩子往这儿瞎凑合什么?!")
    allow, msg = evaluate([rule], _ctx(actor_attrs={"age": 15}))
    assert allow is False
    assert msg == "小毛孩子往这儿瞎凑合什么?!"
    allow, _ = evaluate([rule], _ctx(actor_attrs={"age": 20}))
    assert allow is True


def test_deny_present_npc() -> None:
    """仿 yamen：守卫在场则 deny。"""
    rule = _rule(Predicate(kind="present_npc", npc_id="city/npc/yayi"), "衙役喝道：威……武……。")
    allow, _ = evaluate([rule], _ctx(npc_ids_in_room={"city/npc/yayi"}))
    assert allow is False
    allow, _ = evaluate([rule], _ctx(npc_ids_in_room=set()))
    assert allow is True


def test_deny_wins_over_allow() -> None:
    """高优先级 allow + 低优先级 deny -> 仍 deny（deny-wins）。"""
    allow_rule = EventRule(
        id="a",
        event=EVENT_VALID_LEAVE,
        condition=Predicate(kind="always"),
        action="allow",
        priority=10,
    )
    deny_rule = _rule(Predicate(kind="always"), priority=0, id="d")
    allow, _ = evaluate([allow_rule, deny_rule], _ctx())
    assert allow is False


def test_high_priority_deny_message() -> None:
    hi = _rule(Predicate(kind="always"), "hi", priority=10, id="hi")
    allow, msg = evaluate([hi], _ctx())
    assert allow is False
    assert msg == "hi"


def test_non_valid_leave_event_ignored() -> None:
    rule = EventRule(
        id="r", event="accept_object", condition=Predicate(kind="always"), action=ACTION_DENY
    )
    allow, _ = evaluate([rule], _ctx())
    assert allow is True


# --- S4 方向绑定（ADR-0005）---


def test_dir_binding_deny_only_matched_dir() -> None:
    """dir=north 的规则仅对 north 方向 deny，其他方向放行。"""
    rule = _rule(Predicate(kind="always"), "挡住", dir="north", id="r")
    allow, _ = evaluate([rule], _ctx(dir="north"))
    assert allow is False
    allow, _ = evaluate([rule], _ctx(dir="eastdown"))
    assert allow is True


def test_dir_empty_applies_all_directions() -> None:
    """dir 空 = 全方向生效（向后兼容 S1-S3）。"""
    rule = _rule(Predicate(kind="always"), "挡住", id="r")
    allow, _ = evaluate([rule], _ctx(dir="north"))
    assert allow is False
    allow, _ = evaluate([rule], _ctx(dir="south"))
    assert allow is False


# --- S4 组合谓词（ADR-0005）---


def test_all_combination() -> None:
    """AND 组合：全满足才 deny。"""
    cond = Predicate(
        all=[
            Predicate(kind="present_npc", npc_id="guard"),
            Predicate(kind="has_flag", flag="vip"),
        ]
    )
    rule = _rule(cond, "deny", id="r")
    # 两者都满足 -> deny
    allow, _ = evaluate([rule], _ctx(npc_ids_in_room={"guard"}, actor_flags={"vip"}))
    assert allow is False
    # 仅一个满足 -> allow
    allow, _ = evaluate([rule], _ctx(npc_ids_in_room={"guard"}, actor_flags=set()))
    assert allow is True
    allow, _ = evaluate([rule], _ctx(npc_ids_in_room=set(), actor_flags={"vip"}))
    assert allow is True


def test_any_combination() -> None:
    """OR 组合：任一满足即 deny。"""
    cond = Predicate(
        any=[
            Predicate(kind="family_eq", family="全真教"),
            Predicate(kind="has_item", item_id="incense"),
        ]
    )
    rule = _rule(cond, "deny", id="r")
    # 门派匹配 -> deny
    allow, _ = evaluate([rule], _ctx(actor_family="全真教"))
    assert allow is False
    # 持物 -> deny
    allow, _ = evaluate([rule], _ctx(actor_items={"incense"}))
    assert allow is False
    # 都不满足 -> allow
    allow, _ = evaluate([rule], _ctx(actor_family="", actor_items=set()))
    assert allow is True


def test_not_combination() -> None:
    """NOT 取反：not(has_item) = 不持物时 deny（allow-wins 等价表达）。"""
    cond = Predicate(not_=Predicate(kind="has_item", item_id="incense"))
    rule = _rule(cond, "deny", id="r")
    # 不持物 -> not(has_item)=True -> deny
    allow, _ = evaluate([rule], _ctx(actor_items=set()))
    assert allow is False
    # 持物 -> not(has_item)=False -> allow
    allow, _ = evaluate([rule], _ctx(actor_items={"incense"}))
    assert allow is True


def test_family_eq_predicate() -> None:
    rule = _rule(Predicate(kind="family_eq", family="雪山派"), "deny", id="r")
    allow, _ = evaluate([rule], _ctx(actor_family="雪山派"))
    assert allow is False
    allow, _ = evaluate([rule], _ctx(actor_family="血刀门"))
    assert allow is True


def test_has_item_predicate() -> None:
    rule = _rule(Predicate(kind="has_item", item_id="suyou_guan"), "deny", id="r")
    allow, _ = evaluate([rule], _ctx(actor_items={"suyou_guan"}))
    assert allow is False
    allow, _ = evaluate([rule], _ctx(actor_items=set()))
    assert allow is True


def test_nested_combination_xueshan_pattern() -> None:
    """xueshan 守卫完整模式：dir=north AND present_npc AND NOT(家族 OR 持物 OR 标记)。

    验证 all + not + any 嵌套组合能表达 LPC valid_leave 完整逻辑（ADR-0005 KPI）。
    """
    cond = Predicate(
        all=[
            Predicate(kind="present_npc", npc_id="xueshan/npc/gelun1"),
            Predicate(
                not_=Predicate(
                    any=[
                        Predicate(kind="family_eq", family="雪山派"),
                        Predicate(kind="family_eq", family="血刀门"),
                        Predicate(kind="has_item", item_id="suyou_guan"),
                        Predicate(kind="has_flag", flag="酥"),
                    ]
                )
            ),
        ]
    )
    rule = _rule(cond, "葛伦布挡住你", dir="north", id="r")

    # 无门派无物品无标记 + 葛伦布在场 -> deny
    allow, _ = evaluate(
        [rule],
        _ctx(
            dir="north",
            npc_ids_in_room={"xueshan/npc/gelun1"},
            actor_family="",
            actor_items=set(),
            actor_flags=set(),
        ),
    )
    assert allow is False
    # 雪山派 -> allow
    allow, _ = evaluate(
        [rule], _ctx(dir="north", npc_ids_in_room={"xueshan/npc/gelun1"}, actor_family="雪山派")
    )
    assert allow is True
    # 持酥油 -> allow
    allow, _ = evaluate(
        [rule],
        _ctx(dir="north", npc_ids_in_room={"xueshan/npc/gelun1"}, actor_items={"suyou_guan"}),
    )
    assert allow is True
    # 葛伦布不在场 -> allow（present_npc 不满足）
    allow, _ = evaluate([rule], _ctx(dir="north", npc_ids_in_room=set(), actor_family=""))
    assert allow is True
    # 非 north 方向 -> allow（方向绑定）
    allow, _ = evaluate(
        [rule], _ctx(dir="eastdown", npc_ids_in_room={"xueshan/npc/gelun1"}, actor_family="")
    )
    assert allow is True


# --- S4 accept_object 事件（ADR-0006）---


def _acc_rule(
    npc_id: str = "", item_id: str = "", action: str = ACTION_SET_FLAG, id: str = "r", **kw
) -> EventRule:  # type: ignore[no-untyped-def]
    return EventRule(
        id=id,
        event=EVENT_ACCEPT_OBJECT,
        condition=Predicate(kind="always"),
        action=action,
        npc_id=npc_id,
        item_id=item_id,
        **kw,
    )


def test_accept_object_set_flag() -> None:
    """给匹配物品 -> set_flag + 接受（LPC set_temp("marks/X", 1)）。"""
    rule = _acc_rule(npc_id="gelun1", item_id="suyou_guan", flag="酥", message="佛爷保佑施主")
    result = evaluate_accept_object([rule], _ctx(npc_id="gelun1", item_id="suyou_guan"))
    assert result.accepted is True
    assert result.set_flag == "酥"
    assert result.message == "佛爷保佑施主"


def test_accept_object_deny() -> None:
    """给匹配物品 -> deny（拒绝接受）。"""
    rule = _acc_rule(npc_id="gelun1", item_id="wrong", action=ACTION_DENY, message="迷惑")
    result = evaluate_accept_object([rule], _ctx(npc_id="gelun1", item_id="wrong"))
    assert result.accepted is False
    assert result.set_flag == ""
    assert result.message == "迷惑"


def test_accept_object_no_match_default_accept() -> None:
    """无匹配规则 -> 默认接受（无副作用）。"""
    rule = _acc_rule(npc_id="gelun1", item_id="suyou_guan", flag="酥")
    # npc_id 不匹配 -> 跳过 -> 默认接受
    result = evaluate_accept_object([rule], _ctx(npc_id="other", item_id="suyou_guan"))
    assert result.accepted is True
    assert result.set_flag == ""
    # item_id 不匹配 -> 跳过 -> 默认接受
    result = evaluate_accept_object([rule], _ctx(npc_id="gelun1", item_id="other"))
    assert result.accepted is True
    assert result.set_flag == ""


def test_accept_object_npc_and_item_filter() -> None:
    """npc_id + item_id 双重过滤：仅两者都匹配才触发。"""
    rule = _acc_rule(npc_id="gelun1", item_id="suyou_guan", flag="酥")
    # 都匹配 -> set_flag
    result = evaluate_accept_object([rule], _ctx(npc_id="gelun1", item_id="suyou_guan"))
    assert result.set_flag == "酥"
    # npc 不匹配 -> 跳过
    result = evaluate_accept_object([rule], _ctx(npc_id="other", item_id="suyou_guan"))
    assert result.set_flag == ""
    # item 不匹配 -> 跳过
    result = evaluate_accept_object([rule], _ctx(npc_id="gelun1", item_id="other"))
    assert result.set_flag == ""


def test_accept_object_priority_first_match() -> None:
    """首匹配：高 priority 规则先触发，低 priority 不覆盖。"""
    hi = _acc_rule(
        npc_id="gelun1", item_id="suyou_guan", flag="酥", message="hi", priority=10, id="hi"
    )
    lo = _acc_rule(
        npc_id="gelun1", item_id="suyou_guan", flag="other", message="lo", priority=0, id="lo"
    )
    result = evaluate_accept_object([lo, hi], _ctx(npc_id="gelun1", item_id="suyou_guan"))
    assert result.set_flag == "酥"  # 高 priority 先匹配
    assert result.message == "hi"
