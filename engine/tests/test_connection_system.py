"""ConnectionSystem 测试（ADR-0024 决策 2/6）。"""

from __future__ import annotations

import time

from xkx.runtime.capability import PermissionService, WizLevel
from xkx.runtime.connection import (
    LOGIN_TIMEOUT,
    NET_DEAD_TIMEOUT,
    ConnectionSession,
    ConnectionSystem,
    EventEntry,
    SessionState,
)


def _make_token() -> object:
    perms = PermissionService()
    return perms.issue_token(1, WizLevel.PLAYER)


# ---------------------------------------------------------------------------
# 会话生命周期
# ---------------------------------------------------------------------------


def test_create_session() -> None:
    cs = ConnectionSystem()
    s = cs.create_session("sess1")
    assert s.session_id == "sess1"
    assert s.state == SessionState.LOGIN
    assert cs.session_count == 1


def test_get_session() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    assert cs.get_session("sess1") is not None
    assert cs.get_session("nope") is None


def test_close_session() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    cs.close_session("sess1")
    assert cs.session_count == 0
    assert cs.get_session("sess1") is None


def test_activate_session() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    token = _make_token()
    cs.activate("sess1", "alice", 42, token)  # type: ignore[arg-type]
    s = cs.get_session("sess1")
    assert s is not None
    assert s.state == SessionState.ACTIVE
    assert s.account_id == "alice"
    assert s.body_eid == 42


def test_touch_updates_last_active() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    s = cs.get_session("sess1")
    assert s is not None
    old = s.last_active
    time.sleep(0.01)
    cs.touch("sess1")
    assert s.last_active > old


# ---------------------------------------------------------------------------
# ring buffer
# ---------------------------------------------------------------------------


def test_push_event_increments_seq() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    e1 = cs.push_event("sess1", "room_msg", {"text": "hi"})
    e2 = cs.push_event("sess1", "combat", {"text": "hit"})
    assert e1.seq == 1
    assert e2.seq == 2
    s = cs.get_session("sess1")
    assert s is not None
    assert s.last_seq == 2


def test_ring_buffer_drops_old() -> None:
    """ring 满后丢弃旧事件（maxlen）。"""
    cs = ConnectionSystem(ring_size=3)
    cs.create_session("sess1")
    for i in range(5):
        cs.push_event("sess1", "evt", {"i": i})
    s = cs.get_session("sess1")
    assert s is not None
    assert len(s.ring) == 3  # maxlen=3
    assert s.ring[0].seq == 3  # 旧的 1/2 被丢弃
    assert s.last_seq == 5  # seq 持续递增


def test_replay_since_ring_success() -> None:
    """last_seq 在 ring 范围内 -> ring 重放。"""
    cs = ConnectionSystem()
    cs.create_session("sess1")
    for i in range(5):
        cs.push_event("sess1", "evt", {"i": i})
    events, mode = cs.resume("sess1", last_seq=2)
    assert mode == "ring"
    assert len(events) == 3  # seq 3, 4, 5
    assert [e.seq for e in events] == [3, 4, 5]


def test_replay_since_snapshot_degradation() -> None:
    """last_seq 早于 ring 起点 -> snapshot 降级。"""
    cs = ConnectionSystem(ring_size=3)
    cs.create_session("sess1")
    for i in range(5):
        cs.push_event("sess1", "evt", {"i": i})
    # ring 现在含 seq 3,4,5；last_seq=1 早于 ring_head-1=2
    events, mode = cs.resume("sess1", last_seq=1)
    assert mode == "snapshot"
    assert events == []


def test_resume_rejected_for_nonexistent_session() -> None:
    cs = ConnectionSystem()
    events, mode = cs.resume("nope", last_seq=0)
    assert mode == "rejected"
    assert events == []


def test_replay_empty_ring() -> None:
    """空 ring -> ring 成功（无事件）。"""
    cs = ConnectionSystem()
    cs.create_session("sess1")
    events, mode = cs.resume("sess1", last_seq=0)
    assert mode == "ring"
    assert events == []


def test_replay_last_seq_at_ring_head_boundary() -> None:
    """last_seq == ring_head - 1 -> ring 重放全部。"""
    cs = ConnectionSystem(ring_size=3)
    cs.create_session("sess1")
    for i in range(5):
        cs.push_event("sess1", "evt", {"i": i})
    # ring 含 seq 3,4,5；last_seq=2 == ring_head-1=2 -> ring 重放
    events, mode = cs.resume("sess1", last_seq=2)
    assert mode == "ring"
    assert len(events) == 3


# ---------------------------------------------------------------------------
# net_dead + reconnect
# ---------------------------------------------------------------------------


def test_mark_net_dead() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    cs.mark_net_dead("sess1")
    s = cs.get_session("sess1")
    assert s is not None
    assert s.state == SessionState.NET_DEAD
    assert s.net_dead_at > 0


def test_reconnect_restores_active() -> None:
    cs = ConnectionSystem()
    cs.create_session("sess1")
    cs.mark_net_dead("sess1")
    s = cs.reconnect("sess1")
    assert s is not None
    assert s.state == SessionState.ACTIVE


def test_reconnect_non_net_dead_returns_none() -> None:
    """非 NET_DEAD 状态重连返回 None。"""
    cs = ConnectionSystem()
    cs.create_session("sess1")
    assert cs.reconnect("sess1") is None  # LOGIN 状态


def test_reconnect_nonexistent_returns_none() -> None:
    cs = ConnectionSystem()
    assert cs.reconnect("nope") is None


# ---------------------------------------------------------------------------
# tick 驱动超时
# ---------------------------------------------------------------------------


def test_update_closes_login_timeout() -> None:
    """LOGIN 超时关闭。"""
    cs = ConnectionSystem()
    cs.create_session("sess1")
    s = cs.get_session("sess1")
    assert s is not None
    s.last_active = time.time() - LOGIN_TIMEOUT - 1
    cs.update()
    assert cs.get_session("sess1") is None


def test_update_closes_net_dead_timeout() -> None:
    """NET_DEAD 超时关闭。"""
    cs = ConnectionSystem()
    cs.create_session("sess1")
    cs.mark_net_dead("sess1")
    s = cs.get_session("sess1")
    assert s is not None
    s.net_dead_at = time.time() - NET_DEAD_TIMEOUT - 1
    cs.update()
    assert cs.get_session("sess1") is None


def test_update_keeps_active_session() -> None:
    """活跃会话不超时关闭。"""
    cs = ConnectionSystem()
    cs.create_session("sess1")
    cs.activate("sess1", "alice", 1, _make_token())  # type: ignore[arg-type]
    cs.update()
    assert cs.get_session("sess1") is not None


def test_active_sessions_filter() -> None:
    cs = ConnectionSystem()
    cs.create_session("s1")
    cs.create_session("s2")
    cs.activate("s2", "alice", 1, _make_token())  # type: ignore[arg-type]
    active = cs.active_sessions()
    assert len(active) == 1
    assert active[0].session_id == "s2"


# ---------------------------------------------------------------------------
# EventEntry / ConnectionSession 数据模型
# ---------------------------------------------------------------------------


def test_event_entry_defaults() -> None:
    e = EventEntry(seq=1, event_type="test")
    assert e.seq == 1
    assert e.event_type == "test"
    assert e.data == {}


def test_connection_session_default_ring_size() -> None:
    s = ConnectionSession(session_id="x")
    assert s.ring.maxlen == 100  # DEFAULT_RING_SIZE


def test_connection_session_push_event_returns_entry() -> None:
    s = ConnectionSession(session_id="x")
    e = s.push_event("test", {"k": "v"})
    assert isinstance(e, EventEntry)
    assert e.seq == 1
    assert e.data == {"k": "v"}
