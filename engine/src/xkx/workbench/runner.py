"""异步包装同步 Orchestrator，向 WebSocket 广播阶段事件（M2-2）。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xkx.orchestrator.loop import Orchestrator
    from xkx.orchestrator.state_machine import Job
    from xkx.workbench.ws import ConnectionManager


async def run_orchestrator_streaming(
    orchestrator: Orchestrator,
    job: Job,
    manager: ConnectionManager,
    job_id: str,
) -> Job:
    """在后台线程跑 ``Orchestrator.run``，同时通过 WebSocket 广播阶段事件。

    线程安全桥：callback 在 worker 线程被调用，通过 ``loop.call_soon_threadsafe``
    把事件 put 进 asyncio.Queue；主事件循环 drain queue 后广播。
    """
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    def _event_callback(event: dict[str, Any]) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, {"job_id": job_id, **event})

    orchestrator._event_callback = _event_callback

    async def _drain() -> None:
        while True:
            event = await queue.get()
            if event is None:
                break
            await manager.broadcast(event)

    drain_task = asyncio.create_task(_drain())

    def _run() -> Job:
        return orchestrator.run(job)

    try:
        result = await asyncio.to_thread(_run)
    finally:
        loop.call_soon_threadsafe(queue.put_nowait, None)
        await drain_task

    return result
