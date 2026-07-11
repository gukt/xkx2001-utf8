"""ConnectionSystem + 会话管理 + ring buffer 重连（ADR-0024 决策 2/6）。

会话态进程内内存（非 ECS 组件，非权威态，崩溃丢失可接受，dissent 8 取舍）。
ring buffer 重放近期 event；``last_seq`` 早于 ring 起点时 snapshot 降级。

ConnectionSystem 是 ADR-0014 第 6 个 System，tick 驱动会话超时
（LOGIN/NET_DEAD/IDLE_TIMEOUT）。接口对齐 ``System.update(world, tick)``
（鸭子类型），但不继承 ``System``（会话表非 ECS 组件，独立管理）。

[ADR-0024](../../../docs/adr/ADR-0024-ws-protocol-reconnect-accountservice.md) 决策 2/6
[ADR-0014](../../../docs/adr/ADR-0014-daemon-responsibility-redesign.md) 第 6 个 System
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from xkx.runtime.capability import CapabilityToken


class SessionState(StrEnum):
    """会话状态。"""

    LOGIN = "login"
    ACTIVE = "active"
    NET_DEAD = "net_dead"
    CLOSED = "closed"


@dataclass
class EventEntry:
    """ring buffer 事件条目（event 帧）。"""

    seq: int
    event_type: str
    data: dict[str, Any] = field(default_factory=dict)


# 超时常量（秒，对齐 spec layer_i login.c time_out / user.c user_dump）
LOGIN_TIMEOUT = 60.0
NET_DEAD_TIMEOUT = 300.0
IDLE_TIMEOUT = 600.0

# 默认 ring buffer 容量（ADR-0024 决策 2：100 条或 30 秒，T10 实测后调）
DEFAULT_RING_SIZE = 100


@dataclass
class ConnectionSession:
    """单会话状态（进程内内存，非持久化）。"""

    session_id: str
    account_id: str = ""
    body_eid: int = 0
    state: SessionState = SessionState.LOGIN
    token: CapabilityToken | None = None
    ring: deque[EventEntry] = field(default_factory=lambda: deque(maxlen=DEFAULT_RING_SIZE))
    last_seq: int = 0
    last_active: float = 0.0
    net_dead_at: float = 0.0

    def push_event(self, event_type: str, data: dict[str, Any] | None = None) -> EventEntry:
        """追加事件到 ring buffer，seq 递增。"""
        self.last_seq += 1
        entry = EventEntry(seq=self.last_seq, event_type=event_type, data=data or {})
        self.ring.append(entry)
        return entry

    def replay_since(self, last_seq: int) -> tuple[list[EventEntry], bool]:
        """重放 last_seq 之后的事件。

        返回 (events, full)：
        - full=True：ring 重放成功（last_seq 在 ring 范围内）
        - full=False：ring 不足（last_seq 早于 ring 起点），需 snapshot 降级
        """
        if not self.ring:
            return [], True
        ring_head = self.ring[0].seq
        if last_seq < ring_head - 1:
            return [], False
        events = [e for e in self.ring if e.seq > last_seq]
        return events, True


class ConnectionSystem:
    """会话管理 System（ADR-0024 决策 6，ADR-0014 第 6 个 System）。

    tick 驱动会话超时检测。会话表进程内内存（非 ECS 组件）。
    """

    name: str = "ConnectionSystem"

    def __init__(self, *, ring_size: int = DEFAULT_RING_SIZE) -> None:
        self._sessions: dict[str, ConnectionSession] = {}
        self._ring_size = ring_size

    def create_session(self, session_id: str) -> ConnectionSession:
        session = ConnectionSession(
            session_id=session_id,
            ring=deque(maxlen=self._ring_size),
            last_active=time.time(),
        )
        self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ConnectionSession | None:
        return self._sessions.get(session_id)

    def close_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def activate(
        self,
        session_id: str,
        account_id: str,
        body_eid: int,
        token: CapabilityToken,
    ) -> None:
        """登录成功，激活会话（LOGIN -> ACTIVE）。"""
        s = self._sessions.get(session_id)
        if s is None:
            return
        s.account_id = account_id
        s.body_eid = body_eid
        s.token = token
        s.state = SessionState.ACTIVE
        s.last_active = time.time()

    def touch(self, session_id: str) -> None:
        """更新会话最后活跃时间（收到命令/心跳时调）。"""
        s = self._sessions.get(session_id)
        if s is not None:
            s.last_active = time.time()

    def mark_net_dead(self, session_id: str) -> None:
        """标记断线（ACTIVE -> NET_DEAD）。"""
        s = self._sessions.get(session_id)
        if s is None:
            return
        s.state = SessionState.NET_DEAD
        s.net_dead_at = time.time()

    def reconnect(self, session_id: str) -> ConnectionSession | None:
        """重连恢复（NET_DEAD -> ACTIVE）。"""
        s = self._sessions.get(session_id)
        if s is None or s.state != SessionState.NET_DEAD:
            return None
        s.state = SessionState.ACTIVE
        s.last_active = time.time()
        return s

    def push_event(
        self, session_id: str, event_type: str, data: dict[str, Any] | None = None
    ) -> EventEntry | None:
        """向会话 ring buffer 推送事件。"""
        s = self._sessions.get(session_id)
        if s is None:
            return None
        return s.push_event(event_type, data)

    def resume(
        self, session_id: str, last_seq: int
    ) -> tuple[list[EventEntry], str]:
        """重连重放（ADR-0024 决策 2）。

        返回 (events, mode)：
        - mode="ring"：ring 重放成功
        - mode="snapshot"：ring 不足，需 snapshot 降级
        - mode="rejected"：会话不存在
        """
        s = self._sessions.get(session_id)
        if s is None:
            return [], "rejected"
        events, full = s.replay_since(last_seq)
        mode = "ring" if full else "snapshot"
        return events, mode

    def update(self, world: Any = None, tick: int = 0) -> None:
        """tick 驱动：检测会话超时（LOGIN/NET_DEAD/IDLE）。"""
        now = time.time()
        for sid, s in list(self._sessions.items()):
            if self._is_timed_out(s, now):
                self.close_session(sid)

    def _is_timed_out(self, s: ConnectionSession, now: float) -> bool:
        """检查会话是否超时（LOGIN/NET_DEAD/IDLE 各自阈值）。"""
        if s.state == SessionState.LOGIN:
            return now - s.last_active > LOGIN_TIMEOUT
        if s.state == SessionState.NET_DEAD:
            return now - s.net_dead_at > NET_DEAD_TIMEOUT
        if s.state == SessionState.ACTIVE:
            return now - s.last_active > IDLE_TIMEOUT
        return False

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def active_sessions(self) -> list[ConnectionSession]:
        """当前活跃会话（ACTIVE 状态）。"""
        return [s for s in self._sessions.values() if s.state == SessionState.ACTIVE]
