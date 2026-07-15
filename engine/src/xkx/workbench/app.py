"""FastAPI app 工厂（M2-2 评审工作台）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
except ImportError as exc:  # pragma: no cover - 无 workbench extra 时占位
    FastAPI = object  # type: ignore[misc, assignment]
    WebSocket = Any  # type: ignore[misc, assignment]
    WebSocketDisconnect = Exception  # type: ignore[misc, assignment]
    _FASTAPI_AVAILABLE = False
    _IMPORT_ERROR = exc
else:
    _FASTAPI_AVAILABLE = True
    _IMPORT_ERROR = None

from xkx.workbench.router import WorkbenchState, make_router
from xkx.workbench.ws import ConnectionManager


def create_app(
    output_dir: Path | str,
    *,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """创建评审工作台 FastAPI app。"""
    if not _FASTAPI_AVAILABLE:
        raise _IMPORT_ERROR or ImportError("fastapi 未安装")

    state = WorkbenchState(output_dir)
    manager = ConnectionManager()
    router = make_router(state, manager)

    app = FastAPI(title="xkx workbench", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await manager.connect(websocket)
        try:
            while True:
                # 客户端可发订阅消息，目前只保持连接即可
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    # 静态前端
    if static_dir is None:
        static_dir = Path(__file__).with_suffix("").parent / "static"
    if Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    # 把 manager/state 挂到 app 上，供 runner 使用
    app.state.workbench_manager = manager  # type: ignore[attr-defined]
    app.state.workbench_state = state  # type: ignore[attr-defined]

    return app
