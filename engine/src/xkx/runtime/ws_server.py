"""WS 服务器 + 帧编解码 + 会话生命周期（ADR-0024 决策 1/6/7）。

帧格式（JSON 文本帧，UTF-8）：
- ``command`` C->S：玩家命令 -> 8 段管线（ADR-0020）
- ``result`` S->C：命令结果
- ``event`` S->C：异步事件（房间/战斗/频道）
- ``login`` / ``login_state``：登录子协议（LoginMachine 驱动）
- ``resume`` / ``resumed``：断线重连（ring/snapshot，ADR-0024 决策 2）

核心逻辑（``handle_frame`` 等）不依赖网络库，可单元测试。网络层（``serve``）
用 ``websockets`` 库，阶段 1 集成测试用。

session token 复用 T4 的 ``CapabilityToken`` + ``PermissionService``（HS256 +
内存吊销，ADR-0020 决策 3 + ADR-0024 决策 4）。

[ADR-0024](../../../docs/adr/ADR-0024-ws-protocol-reconnect-accountservice.md)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from xkx.runtime.account import AccountService
from xkx.runtime.capability import PermissionService, WizLevel
from xkx.runtime.commands import Game, dispatch
from xkx.runtime.components import (
    Attributes,
    Identity,
    Inventory,
    Marks,
    Position,
    Progression,
    Vitals,
)
from xkx.runtime.connection import ConnectionSystem, SessionState
from xkx.runtime.login import LoginMachine, LoginSession


def encode_frame(frame: dict[str, Any]) -> str:
    """帧编码为 JSON 字符串（WS 文本帧）。"""
    return json.dumps(frame, ensure_ascii=False)


def decode_frame(data: str) -> dict[str, Any]:
    """从 JSON 字符串解码帧。"""
    return json.loads(data)


class WSServer:
    """WS 服务器核心逻辑（不依赖网络库，可单元测试）。

    网络层（``serve`` 方法，``websockets`` 库）阶段 1 集成测试用；核心逻辑通过
    ``handle_frame`` / ``handle_new_connection`` / ``handle_disconnect`` 直接测试。
    """

    def __init__(
        self,
        game: Game,
        account_service: AccountService,
        permission_service: PermissionService,
        connection_system: ConnectionSystem | None = None,
    ) -> None:
        self._game = game
        self._accounts = account_service
        self._perms = permission_service
        self._connections = connection_system or ConnectionSystem()
        self._login_machine = LoginMachine(account_service)
        self._login_sessions: dict[str, LoginSession] = {}

    @property
    def connections(self) -> ConnectionSystem:
        return self._connections

    def handle_new_connection(self, session_id: str) -> list[dict[str, Any]]:
        """新连接：创建会话 + 发 GET_ID prompt。"""
        self._connections.create_session(session_id)
        self._login_sessions[session_id] = LoginSession()
        prompt = self._login_machine.start()
        return [self._login_state_frame(prompt)]

    def handle_disconnect(self, session_id: str) -> None:
        """断线：mark_net_dead（等待重连或超时关闭）。"""
        self._connections.mark_net_dead(session_id)
        self._login_sessions.pop(session_id, None)

    def handle_frame(
        self, session_id: str, frame: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """处理一帧，返回响应帧列表（核心逻辑，不依赖网络）。"""
        ftype = frame.get("type")
        if ftype == "login":
            return self._handle_login(session_id, frame)
        if ftype == "command":
            return self._handle_command(session_id, frame)
        if ftype == "resume":
            return self._handle_resume(session_id, frame)
        return [{"type": "error", "error": f"unknown frame type: {ftype}"}]

    def _handle_login(
        self, session_id: str, frame: dict[str, Any]
    ) -> list[dict[str, Any]]:
        ls = self._login_sessions.get(session_id)
        if ls is None:
            return [{"type": "error", "error": "no login session, please reconnect"}]
        prompt = self._login_machine.handle(ls, frame.get("input", ""))
        if prompt.done and prompt.result is not None:
            return self._finish_login(session_id, prompt)
        return [self._login_state_frame(prompt)]

    def _finish_login(
        self, session_id: str, prompt: Any
    ) -> list[dict[str, Any]]:
        """登录成功：创建 body + 签发 token + activate 会话。"""
        result = prompt.result
        body_eid = self._enter_world(result)
        token = self._perms.issue_token(body_eid, WizLevel.PLAYER)
        self._connections.activate(session_id, result.account_id, body_eid, token)
        self._login_sessions.pop(session_id, None)
        return [
            self._login_state_frame(prompt),
            {"type": "result", "seq": 0, "messages": [prompt.prompt], "effects": []},
        ]

    def _enter_world(self, result: Any) -> int:
        """创建 body 实体 + 挂组件（阶段 1 最小，天赋用默认值）。"""
        world = self._game.world
        eid = world.new_entity()
        ident = Identity(
            name=result.name,
            aliases=[result.account_id],
            is_player=True,
            prototype_id="player",
        )
        world.add(eid, ident)
        world.add(eid, Position(room_id=self._game.spawn_room or "start"))
        world.add(eid, Vitals())
        world.add(eid, Attributes(gender=result.gender))
        world.add(eid, Progression())
        world.add(eid, Inventory())
        world.add(eid, Marks())
        return eid

    def _handle_command(
        self, session_id: str, frame: dict[str, Any]
    ) -> list[dict[str, Any]]:
        s = self._connections.get_session(session_id)
        if s is None or s.state != SessionState.ACTIVE:
            return [{"type": "error", "error": "not logged in"}]
        verb = frame.get("verb", "")
        args = frame.get("args", "")
        line = f"{verb} {args}".strip() if args else verb
        self._connections.touch(session_id)
        seq = frame.get("seq", 0)
        messages = dispatch(
            self._game,
            s.body_eid,
            line,
            permission_service=self._perms,
            capability_token=s.token,
            seq=seq,
        )
        return [{"type": "result", "seq": seq, "messages": messages, "effects": []}]

    def _handle_resume(
        self, session_id: str, frame: dict[str, Any]
    ) -> list[dict[str, Any]]:
        last_seq = frame.get("last_seq", 0)
        events, mode = self._connections.resume(session_id, last_seq)
        if mode == "rejected":
            return [{"type": "error", "error": "session not found, please login"}]
        event_frames = [
            {"type": "event", "event_type": e.event_type, "data": e.data, "seq": e.seq}
            for e in events
        ]
        return [{"type": "resumed", "mode": mode, "events": event_frames}]

    def _login_state_frame(self, prompt: Any) -> dict[str, Any]:
        return {
            "type": "login_state",
            "state": prompt.state.value,
            "prompt": prompt.prompt,
            "done": prompt.done,
            "error": prompt.error,
        }

    async def serve(self, host: str = "127.0.0.1", port: int = 8888) -> None:
        """启动 WS 服务器（``websockets`` 库，阶段 1 集成测试用）。"""
        import websockets.asyncio.server  # noqa: PLC0415

        async def handler(websocket: Any) -> None:
            session_id = f"ws-{id(websocket)}"
            for frame_dict in self.handle_new_connection(session_id):
                await websocket.send(encode_frame(frame_dict))
            try:
                async for message in websocket:
                    frame = decode_frame(message)
                    for resp in self.handle_frame(session_id, frame):
                        await websocket.send(encode_frame(resp))
            except Exception:
                pass
            finally:
                self.handle_disconnect(session_id)

        async with websockets.asyncio.server.serve(handler, host, port):
            await asyncio.Future()  # run forever
