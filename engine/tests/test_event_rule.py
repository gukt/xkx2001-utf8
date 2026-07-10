"""层1 事件规则 + 薄求值器测试（valid_leave + deny-wins）。"""

from __future__ import annotations

from xkx.dsl.layer1 import (
    ACTION_DENY,
    EVENT_VALID_LEAVE,
    EvalContext,
    EventRule,
    Predicate,
    evaluate,
)


def _ctx(**kw):  # type: ignore[no-untyped-def]
    return EvalContext(**kw)


def test_allow_when_no_rule() -> None:
    allow, msg = evaluate([], _ctx())
    assert allow is True
    assert msg == ""


def test_deny_age_lt() -> None:
    """仿 duchang：age<18 不得离开。"""
    rule = EventRule(
        id="r1",
        event=EVENT_VALID_LEAVE,
        condition=Predicate(kind="age_lt", value=18),
        action=ACTION_DENY,
        message="小毛孩子往这儿瞎凑合什么?!",
    )
    allow, msg = evaluate([rule], _ctx(actor_attrs={"age": 15}))
    assert allow is False
    assert msg == "小毛孩子往这儿瞎凑合什么?!"
    allow, _ = evaluate([rule], _ctx(actor_attrs={"age": 20}))
    assert allow is True


def test_deny_present_npc() -> None:
    """仿 yamen：守卫在场则 deny。"""
    rule = EventRule(
        id="r1",
        event=EVENT_VALID_LEAVE,
        condition=Predicate(kind="present_npc", npc_id="city/npc/yayi"),
        action=ACTION_DENY,
        message="衙役喝道：威……武……。",
    )
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
    deny_rule = EventRule(
        id="d",
        event=EVENT_VALID_LEAVE,
        condition=Predicate(kind="always"),
        action=ACTION_DENY,
        priority=0,
    )
    allow, _ = evaluate([allow_rule, deny_rule], _ctx())
    assert allow is False


def test_high_priority_deny_message() -> None:
    hi = EventRule(
        id="hi",
        event=EVENT_VALID_LEAVE,
        condition=Predicate(kind="always"),
        action=ACTION_DENY,
        priority=10,
        message="hi",
    )
    allow, msg = evaluate([hi], _ctx())
    assert allow is False
    assert msg == "hi"


def test_non_valid_leave_event_ignored() -> None:
    rule = EventRule(
        id="r",
        event="accept_object",
        condition=Predicate(kind="always"),
        action=ACTION_DENY,
    )
    allow, _ = evaluate([rule], _ctx())
    assert allow is True
