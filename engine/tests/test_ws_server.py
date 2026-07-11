"""WSServer 测试（ADR-0024 决策 1/6/7）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from xkx.runtime.account import AccountService
from xkx.runtime.capability import PermissionService
from xkx.runtime.commands import Game
from xkx.runtime.connection import SessionState
from xkx.runtime.ecs import World
from xkx.runtime.ws_server import WSServer, decode_frame, encode_frame


@pytest.fixture
def server(tmp_path: Path) -> WSServer:
    world = World()
    game = Game(world, room_entities={}, rules=[], spawn_room="start")
    accounts = AccountService(tmp_path, time_cost=1)
    perms = PermissionService()
    return WSServer(game, accounts, perms)


def _login_flow(server: WSServer, session_id: str, inputs: list[str]) -> list[dict]:
    """驱动登录流程，返回所有响应帧。"""
    frames = server.handle_new_connection(session_id)
    for inp in inputs:
        frames.extend(server.handle_frame(session_id, {"type": "login", "input": inp}))
    return frames


# ---------------------------------------------------------------------------
# 帧编解码
# ---------------------------------------------------------------------------


def test_encode_decode_frame_roundtrip() -> None:
    """帧编解码往返。"""
    frame = {"type": "command", "verb": "go", "args": "north", "seq": 1}
    encoded = encode_frame(frame)
    assert isinstance(encoded, str)
    decoded = decode_frame(encoded)
    assert decoded == frame


def test_encode_frame_chinese_not_escaped() -> None:
    """中文不转义（ensure_ascii=False）。"""
    frame = {"type": "result", "messages": ["你好，侠客行"]}
    assert "你好" in encode_frame(frame)


# ---------------------------------------------------------------------------
# 新连接
# ---------------------------------------------------------------------------


def test_handle_new_connection_sends_get_id(server: WSServer) -> None:
    """新连接发 GET_ID prompt。"""
    frames = server.handle_new_connection("s1")
    assert len(frames) == 1
    assert frames[0]["type"] == "login_state"
    assert frames[0]["state"] == "get_id"
    assert "英文名" in frames[0]["prompt"]
    assert server.connections.get_session("s1") is not None


# ---------------------------------------------------------------------------
# 老玩家登录
# ---------------------------------------------------------------------------


def test_login_old_player(server: WSServer, tmp_path: Path) -> None:
    """老玩家登录：GET_ID -> GET_PASSWD -> DONE + result。"""
    # 预注册
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    frames = _login_flow(server, "s1", ["alice", "secret1"])
    # 最后两帧：login_state DONE + result
    assert frames[-2]["type"] == "login_state"
    assert frames[-2]["state"] == "done"
    assert frames[-2]["done"] is True
    assert frames[-1]["type"] == "result"
    s = server.connections.get_session("s1")
    assert s is not None
    assert s.state == SessionState.ACTIVE
    assert s.account_id == "alice"
    assert s.body_eid > 0


def test_login_wrong_password(server: WSServer, tmp_path: Path) -> None:
    """密码错误 -> ABORTED。"""
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    frames = _login_flow(server, "s1", ["alice", "wrong"])
    last = frames[-1]
    assert last["state"] == "aborted"
    assert last["done"] is True
    s = server.connections.get_session("s1")
    assert s is not None
    assert s.state == SessionState.LOGIN  # 未激活


# ---------------------------------------------------------------------------
# 新玩家注册
# ---------------------------------------------------------------------------


def test_login_new_player(server: WSServer) -> None:
    """新玩家完整注册流程。"""
    frames = _login_flow(
        server, "s1", ["newbie", "y", "新玩家", "passwd1", "passwd1", "m"]
    )
    last_state = frames[-2]
    assert last_state["state"] == "done"
    assert last_state["done"] is True
    s = server.connections.get_session("s1")
    assert s is not None
    assert s.state == SessionState.ACTIVE
    assert s.account_id == "newbie"


# ---------------------------------------------------------------------------
# 命令分发
# ---------------------------------------------------------------------------


def test_command_not_logged_in(server: WSServer) -> None:
    """未登录发 command -> error。"""
    server.handle_new_connection("s1")
    frames = server.handle_frame("s1", {"type": "command", "verb": "hp", "seq": 1})
    assert frames[0]["type"] == "error"
    assert "not logged in" in frames[0]["error"]


def test_command_hp_after_login(server: WSServer, tmp_path: Path) -> None:
    """登录后发 hp 命令 -> result。"""
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    _login_flow(server, "s1", ["alice", "secret1"])
    frames = server.handle_frame("s1", {"type": "command", "verb": "hp", "seq": 1})
    assert frames[0]["type"] == "result"
    assert frames[0]["seq"] == 1
    # hp 命令返回状态信息
    assert len(frames[0]["messages"]) > 0


def test_command_updates_last_active(server: WSServer, tmp_path: Path) -> None:
    """命令更新会话 last_active（touch）。"""
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    _login_flow(server, "s1", ["alice", "secret1"])
    s = server.connections.get_session("s1")
    assert s is not None
    old = s.last_active
    import time

    time.sleep(0.01)
    server.handle_frame("s1", {"type": "command", "verb": "hp", "seq": 1})
    assert s.last_active > old


# ---------------------------------------------------------------------------
# 重连（resume）
# ---------------------------------------------------------------------------


def test_resume_ring_replay(server: WSServer, tmp_path: Path) -> None:
    """登录 + 推送事件 + resume -> ring 重放。"""
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    _login_flow(server, "s1", ["alice", "secret1"])
    # 推送几个事件
    server.connections.push_event("s1", "room_msg", {"text": "hi"})
    server.connections.push_event("s1", "combat", {"text": "hit"})
    # resume from seq 0
    frames = server.handle_frame("s1", {"type": "resume", "last_seq": 0})
    assert frames[0]["type"] == "resumed"
    assert frames[0]["mode"] == "ring"
    assert len(frames[0]["events"]) == 2


def test_resume_snapshot_degradation(server: WSServer, tmp_path: Path) -> None:
    """ring 不足 -> snapshot 降级。"""
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    _login_flow(server, "s1", ["alice", "secret1"])
    # ring_size 默认 100，推 3 事件，last_seq=0 在范围内 -> ring
    # 用小 ring 制造不足
    from xkx.runtime.connection import ConnectionSystem

    server._connections = ConnectionSystem(ring_size=3)  # noqa: SLF001
    # 重新登录（新 connection_system）
    _login_flow(server, "s2", ["alice", "secret1"])
    for i in range(5):
        server.connections.push_event("s2", "evt", {"i": i})
    # ring 含 seq 3,4,5；last_seq=1 早于 ring_head-1=2 -> snapshot
    frames = server.handle_frame("s2", {"type": "resume", "last_seq": 1})
    assert frames[0]["mode"] == "snapshot"


def test_resume_rejected_nonexistent(server: WSServer) -> None:
    """不存在的会话 resume -> rejected error。"""
    frames = server.handle_frame("nope", {"type": "resume", "last_seq": 0})
    assert frames[0]["type"] == "error"
    assert "not found" in frames[0]["error"]


# ---------------------------------------------------------------------------
# 断线
# ---------------------------------------------------------------------------


def test_handle_disconnect_marks_net_dead(server: WSServer, tmp_path: Path) -> None:
    """断线 -> mark_net_dead。"""
    AccountService(tmp_path, time_cost=1).register("alice", "爱丽丝", "secret1")
    _login_flow(server, "s1", ["alice", "secret1"])
    server.handle_disconnect("s1")
    s = server.connections.get_session("s1")
    assert s is not None
    assert s.state == SessionState.NET_DEAD


def test_handle_disconnect_during_login(server: WSServer) -> None:
    """登录中断线 -> mark_net_dead + 清理 login session。"""
    server.handle_new_connection("s1")
    server.handle_disconnect("s1")
    s = server.connections.get_session("s1")
    assert s is not None
    assert s.state == SessionState.NET_DEAD
    assert "s1" not in server._login_sessions  # noqa: SLF001


# ---------------------------------------------------------------------------
# 未知帧类型
# ---------------------------------------------------------------------------


def test_unknown_frame_type(server: WSServer) -> None:
    """未知帧类型 -> error。"""
    server.handle_new_connection("s1")
    frames = server.handle_frame("s1", {"type": "bogus"})
    assert frames[0]["type"] == "error"
    assert "unknown" in frames[0]["error"]


def test_login_no_login_session(server: WSServer) -> None:
    """无 login session 时发 login -> error。"""
    # 不调 handle_new_connection，直接发 login
    frames = server.handle_frame("s1", {"type": "login", "input": "alice"})
    assert frames[0]["type"] == "error"
    assert "no login session" in frames[0]["error"]
