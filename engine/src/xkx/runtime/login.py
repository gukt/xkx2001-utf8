"""LOGIN_D 登录状态机（ADR-0024 决策 5，spec layer_h LoginState）。

WS 登录子协议驱动：``login_state`` 帧（prompt）<-> ``login`` 帧（input）。
每次输入驱动状态转换，输出下一 prompt 或 ``done``。

阶段 1 简化路径（ADR-0024 决策 5）：
- 老玩家：``GET_ID`` -> ``GET_PASSWD`` -> ``DONE``
- 新玩家：``GET_ID`` -> ``CONFIRM_ID`` -> ``GET_NAME`` -> ``NEW_PASSWORD``
  -> ``CONFIRM_PASSWORD`` -> ``GET_GENDER`` -> ``DONE``

跳过 ``CONFIRM_BIG5``（UTF-8 统一）/ ``wiz_lock`` / ``valid_wiz_login`` /
``GET_GIFT``（自动 ``random_gift``）/ ``GET_EMAIL``（后置）。

login.py 只管状态机 + 调 ``AccountService``（注册/验证）；创建实体 + 签发
``CapabilityToken`` 由 ``ws_server`` 在 ``DONE`` 后负责。

[ADR-0024](../../../docs/adr/ADR-0024-ws-protocol-reconnect-accountservice.md) 决策 5
[spec/layer_h_daemons.py](../spec/layer_h_daemons.py) LoginState + logon/get_id/get_passwd
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from xkx.runtime.account import AccountError, AccountService


class LoginState(StrEnum):
    """登录状态机各阶段（spec layer_h，阶段 1 简化）。"""

    LOGON = "logon"
    GET_ID = "get_id"
    GET_PASSWD = "get_passwd"
    CONFIRM_ID = "confirm_id"
    GET_NAME = "get_name"
    NEW_PASSWORD = "new_password"
    CONFIRM_PASSWORD = "confirm_password"
    GET_GENDER = "get_gender"
    DONE = "done"
    ABORTED = "aborted"


@dataclass
class LoginResult:
    """登录完成结果（DONE 时携带，ws_server 据此创建实体 + 签发 token）。"""

    account_id: str
    name: str
    is_new: bool
    gender: str = "男性"


@dataclass
class LoginPrompt:
    """状态机输出（login_state 帧）。"""

    state: LoginState
    prompt: str
    done: bool = False
    error: str = ""
    result: LoginResult | None = None


@dataclass
class LoginSession:
    """登录会话状态（状态机在多次 handle 间保持）。

    阶段 1 跳过 LOGON/CONFIRM_BIG5（UTF-8 统一），创建后直接 GET_ID。
    """

    state: LoginState = LoginState.GET_ID
    account_id: str = ""
    pending_name: str = ""
    pending_password: str = ""


_GENDER_MAP: dict[str, str] = {
    "m": "男性",
    "f": "女性",
    "男": "男性",
    "女": "女性",
}


class LoginMachine:
    """LOGIN_D 状态机驱动器（ADR-0024 决策 5）。"""

    def __init__(self, account_service: AccountService) -> None:
        self._accounts = account_service

    def start(self) -> LoginPrompt:
        """开始登录（LOGON -> GET_ID）。"""
        return LoginPrompt(
            state=LoginState.GET_ID,
            prompt="请输入你的英文名（3-8 个小写字母）：",
        )

    def handle(self, session: LoginSession, text: str) -> LoginPrompt:
        """处理一次输入，驱动状态转换。"""
        text = text.strip()
        handler = {
            LoginState.GET_ID: self._handle_get_id,
            LoginState.GET_PASSWD: self._handle_get_passwd,
            LoginState.CONFIRM_ID: self._handle_confirm_id,
            LoginState.GET_NAME: self._handle_get_name,
            LoginState.NEW_PASSWORD: self._handle_new_password,
            LoginState.CONFIRM_PASSWORD: self._handle_confirm_password,
            LoginState.GET_GENDER: self._handle_get_gender,
        }.get(session.state)
        if handler is None:
            return LoginPrompt(
                state=LoginState.ABORTED,
                prompt="状态错误",
                done=True,
                error="invalid state",
            )
        return handler(session, text)

    def _handle_get_id(self, session: LoginSession, text: str) -> LoginPrompt:
        session.account_id = text
        if self._accounts.exists(text):
            session.state = LoginState.GET_PASSWD
            return LoginPrompt(state=LoginState.GET_PASSWD, prompt="请输入密码：")
        session.state = LoginState.CONFIRM_ID
        return LoginPrompt(
            state=LoginState.CONFIRM_ID,
            prompt=f"使用 {text} 这个名字将会创造一个新的人物，您确定吗(y/n)？",
        )

    def _handle_get_passwd(self, session: LoginSession, text: str) -> LoginPrompt:
        account = self._accounts.verify(session.account_id, text)
        if account is None:
            session.state = LoginState.ABORTED
            return LoginPrompt(
                state=LoginState.ABORTED,
                prompt="密码错误。",
                done=True,
                error="密码错误",
            )
        session.state = LoginState.DONE
        return LoginPrompt(
            state=LoginState.DONE,
            prompt=f"欢迎回来，{account.name}！",
            done=True,
            result=LoginResult(
                account_id=account.account_id,
                name=account.name,
                is_new=False,
                gender=account.gender,
            ),
        )

    def _handle_confirm_id(self, session: LoginSession, text: str) -> LoginPrompt:
        if text.lower() in ("y", "yes"):
            session.state = LoginState.GET_NAME
            return LoginPrompt(
                state=LoginState.GET_NAME,
                prompt="请输入你的中文名（1-4 个中文字）：",
            )
        session.state = LoginState.GET_ID
        return LoginPrompt(state=LoginState.GET_ID, prompt="请输入你的英文名：")

    def _handle_get_name(self, session: LoginSession, text: str) -> LoginPrompt:
        session.pending_name = text
        session.state = LoginState.NEW_PASSWORD
        return LoginPrompt(
            state=LoginState.NEW_PASSWORD,
            prompt="请设定密码（至少 5 位）：",
        )

    def _handle_new_password(self, session: LoginSession, text: str) -> LoginPrompt:
        if len(text) < 5:
            return LoginPrompt(
                state=LoginState.NEW_PASSWORD,
                prompt="密码太短，至少 5 位，请重新设定：",
            )
        session.pending_password = text
        session.state = LoginState.CONFIRM_PASSWORD
        return LoginPrompt(
            state=LoginState.CONFIRM_PASSWORD,
            prompt="请再次输入密码确认：",
        )

    def _handle_confirm_password(self, session: LoginSession, text: str) -> LoginPrompt:
        if text != session.pending_password:
            session.state = LoginState.NEW_PASSWORD
            return LoginPrompt(
                state=LoginState.NEW_PASSWORD,
                prompt="两次密码不一致，请重新设定：",
            )
        session.state = LoginState.GET_GENDER
        return LoginPrompt(
            state=LoginState.GET_GENDER,
            prompt="请选择性别(m=男/f=女)：",
        )

    def _handle_get_gender(self, session: LoginSession, text: str) -> LoginPrompt:
        gender = _GENDER_MAP.get(text.lower())
        if gender is None:
            return LoginPrompt(
                state=LoginState.GET_GENDER,
                prompt="请输入 m(男) 或 f(女)：",
            )
        try:
            account = self._accounts.register(
                session.account_id,
                session.pending_name,
                session.pending_password,
                gender,
            )
        except AccountError as e:
            session.state = LoginState.ABORTED
            return LoginPrompt(
                state=LoginState.ABORTED,
                prompt=str(e),
                done=True,
                error=str(e),
            )
        session.state = LoginState.DONE
        return LoginPrompt(
            state=LoginState.DONE,
            prompt=f"欢迎来到侠客行，{account.name}！",
            done=True,
            result=LoginResult(
                account_id=account.account_id,
                name=account.name,
                is_new=True,
                gender=account.gender,
            ),
        )
