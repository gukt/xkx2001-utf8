"""LOGIN_D 登录状态机测试（ADR-0024 决策 5）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from xkx.runtime.account import AccountService
from xkx.runtime.login import (
    LoginMachine,
    LoginSession,
    LoginState,
)


@pytest.fixture
def machine(tmp_path: Path) -> LoginMachine:
    return LoginMachine(AccountService(tmp_path))


def _new_session() -> LoginSession:
    return LoginSession()


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------


def test_start_returns_get_id_prompt(machine: LoginMachine) -> None:
    """start 返回 GET_ID 状态 + prompt。"""
    prompt = machine.start()
    assert prompt.state == LoginState.GET_ID
    assert "英文名" in prompt.prompt
    assert prompt.done is False


# ---------------------------------------------------------------------------
# 老玩家登录
# ---------------------------------------------------------------------------


class TestOldPlayerLogin:
    def test_full_flow(self, tmp_path: Path) -> None:
        """老玩家完整登录：GET_ID -> GET_PASSWD -> DONE。"""
        svc = AccountService(tmp_path)
        svc.register("alice", "爱丽丝", "secret1")
        machine = LoginMachine(svc)
        session = _new_session()

        p1 = machine.handle(session, "alice")
        assert p1.state == LoginState.GET_PASSWD

        p2 = machine.handle(session, "secret1")
        assert p2.state == LoginState.DONE
        assert p2.done is True
        assert p2.result is not None
        assert p2.result.account_id == "alice"
        assert p2.result.name == "爱丽丝"
        assert p2.result.is_new is False

    def test_wrong_password_aborts(self, tmp_path: Path) -> None:
        """密码错误 -> ABORTED。"""
        svc = AccountService(tmp_path)
        svc.register("alice", "爱丽丝", "secret1")
        machine = LoginMachine(svc)
        session = _new_session()

        machine.handle(session, "alice")
        p = machine.handle(session, "wrong")
        assert p.state == LoginState.ABORTED
        assert p.done is True
        assert "密码错误" in p.error

    def test_nonexistent_account_goes_to_confirm(self, machine: LoginMachine) -> None:
        """不存在的账号 -> CONFIRM_ID（新人物创建确认）。"""
        session = _new_session()
        p = machine.handle(session, "newbie")
        assert p.state == LoginState.CONFIRM_ID
        assert "新的人物" in p.prompt


# ---------------------------------------------------------------------------
# 新玩家注册流程
# ---------------------------------------------------------------------------


class TestNewPlayerRegistration:
    def test_full_flow(self, machine: LoginMachine) -> None:
        """新玩家完整注册：GET_ID -> CONFIRM_ID -> GET_NAME -> NEW_PASSWORD
        -> CONFIRM_PASSWORD -> GET_GENDER -> DONE。"""
        session = _new_session()

        p1 = machine.handle(session, "newbie")  # GET_ID -> CONFIRM_ID
        assert p1.state == LoginState.CONFIRM_ID

        p2 = machine.handle(session, "y")  # CONFIRM_ID -> GET_NAME
        assert p2.state == LoginState.GET_NAME

        p3 = machine.handle(session, "新玩家")  # GET_NAME -> NEW_PASSWORD
        assert p3.state == LoginState.NEW_PASSWORD

        p4 = machine.handle(session, "passwd1")  # NEW_PASSWORD -> CONFIRM_PASSWORD
        assert p4.state == LoginState.CONFIRM_PASSWORD

        p5 = machine.handle(session, "passwd1")  # CONFIRM_PASSWORD -> GET_GENDER
        assert p5.state == LoginState.GET_GENDER

        p6 = machine.handle(session, "m")  # GET_GENDER -> DONE
        assert p6.state == LoginState.DONE
        assert p6.done is True
        assert p6.result is not None
        assert p6.result.account_id == "newbie"
        assert p6.result.name == "新玩家"
        assert p6.result.is_new is True
        assert p6.result.gender == "男性"

    def test_confirm_id_n_goes_back_to_get_id(self, machine: LoginMachine) -> None:
        """CONFIRM_ID 输入 n -> 回到 GET_ID。"""
        session = _new_session()
        machine.handle(session, "newbie")  # -> CONFIRM_ID
        p = machine.handle(session, "n")
        assert p.state == LoginState.GET_ID

    def test_short_password_retries(self, machine: LoginMachine) -> None:
        """NEW_PASSWORD 输入短密码 -> 重试。"""
        session = _new_session()
        machine.handle(session, "newbie")
        machine.handle(session, "y")
        machine.handle(session, "新玩家")
        p = machine.handle(session, "1234")  # 短密码
        assert p.state == LoginState.NEW_PASSWORD
        assert "太短" in p.prompt

    def test_password_mismatch_retries(self, machine: LoginMachine) -> None:
        """CONFIRM_PASSWORD 不匹配 -> 回到 NEW_PASSWORD。"""
        session = _new_session()
        machine.handle(session, "newbie")
        machine.handle(session, "y")
        machine.handle(session, "新玩家")
        machine.handle(session, "passwd1")
        p = machine.handle(session, "different")  # 不匹配
        assert p.state == LoginState.NEW_PASSWORD
        assert "不一致" in p.prompt

    def test_invalid_gender_retries(self, machine: LoginMachine) -> None:
        """GET_GENDER 无效输入 -> 重试。"""
        session = _new_session()
        machine.handle(session, "newbie")
        machine.handle(session, "y")
        machine.handle(session, "新玩家")
        machine.handle(session, "passwd1")
        machine.handle(session, "passwd1")
        p = machine.handle(session, "x")  # 无效
        assert p.state == LoginState.GET_GENDER

    def test_female_gender(self, machine: LoginMachine) -> None:
        """GET_GENDER 输入 f -> 女性。"""
        session = _new_session()
        machine.handle(session, "newbie")
        machine.handle(session, "y")
        machine.handle(session, "新玩家")
        machine.handle(session, "passwd1")
        machine.handle(session, "passwd1")
        p = machine.handle(session, "f")
        assert p.state == LoginState.DONE
        assert p.result is not None
        assert p.result.gender == "女性"

    def test_register_failure_aborts(self, tmp_path: Path) -> None:
        """注册失败（如中文名禁用词）-> ABORTED。"""
        svc = AccountService(tmp_path)
        machine = LoginMachine(svc)
        session = _new_session()
        machine.handle(session, "newbie")
        machine.handle(session, "y")
        machine.handle(session, "韦小宝")  # 禁用名
        machine.handle(session, "passwd1")
        machine.handle(session, "passwd1")
        p = machine.handle(session, "m")  # 注册时失败
        assert p.state == LoginState.ABORTED
        assert p.done is True


# ---------------------------------------------------------------------------
# 状态机不变量
# ---------------------------------------------------------------------------


def test_handle_invalid_state_aborts(machine: LoginMachine) -> None:
    """未知/已完成状态 handle -> ABORTED。"""
    session = LoginSession(state=LoginState.DONE)
    p = machine.handle(session, "anything")
    assert p.state == LoginState.ABORTED
    assert p.done is True


def test_session_state_transitions_track(machine: LoginMachine) -> None:
    """session.state 随状态机转换更新。"""
    session = _new_session()
    assert session.state == LoginState.GET_ID
    machine.handle(session, "newbie")
    assert session.state == LoginState.CONFIRM_ID
    machine.handle(session, "y")
    assert session.state == LoginState.GET_NAME


def test_login_prompt_done_only_on_terminal(machine: LoginMachine) -> None:
    """done=True 仅在 DONE/ABORTED 终态。"""
    session = _new_session()
    p = machine.handle(session, "newbie")
    assert p.done is False  # CONFIRM_ID 非终态
    p2 = machine.handle(session, "y")
    assert p2.done is False  # GET_NAME 非终态
