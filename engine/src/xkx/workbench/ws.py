"""WebSocket 连接管理器（M2-2 评审工作台）。"""

from __future__ import annotations

import contextlib
import json
from typing import Any

try:
    from fastapi import WebSocket
except ImportError as exc:  # pragma: no cover - 无 workbench extra 时占位
    WebSocket = Any  # type: ignore[misc, assignment]
    _FASTAPI_AVAILABLE = False
    _IMPORT_ERROR = exc
else:
    _FASTAPI_AVAILABLE = True
    _IMPORT_ERROR = None


class ConnectionManager:
    """管理活动 WebSocket 连接，支持广播与按 job 过滤。"""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        if not _FASTAPI_AVAILABLE:
            raise _IMPORT_ERROR or ImportError("fastapi 未安装")
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        with contextlib.suppress(ValueError):
            self._connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有连接广播 JSON 消息。"""
        if not _FASTAPI_AVAILABLE:
            return
        text = json.dumps(message, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
