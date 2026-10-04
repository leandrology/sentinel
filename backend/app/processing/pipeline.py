"""Independent background workers. Drain the bounded queue off the read path.

M2 default handler just acknowledges work (triage/persist plug in at M3/M5 via
``process_fn``). Workers never block the WebSocket reader.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

from app.domain.schemas import NormalizedEvent
from app.ingestion.queue import IngestQueue

log = logging.getLogger(__name__)

ProcessFn = Callable[[NormalizedEvent], Awaitable[None]]


async def noop_process(_: NormalizedEvent) -> None:
    return None


class WorkerPool:
    def __init__(
        self,
        queue: IngestQueue,
        num_workers: int = 4,
        process_fn: ProcessFn | None = None,
    ) -> None:
        self.queue = queue
        self.num_workers = max(1, num_workers)
        self.process_fn = process_fn or noop_process
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False
        self.latency_ms_last: int = 0

    async def _worker(self, wid: int) -> None:
        while self._running:
            try:
                event = await self.queue.get()
            except asyncio.CancelledError:
                raise
            started = time.perf_counter()
            try:
                await self.process_fn(event)
                self.queue.metrics.processed += 1
            except asyncio.CancelledError:
                self.queue.task_done()
                raise
            except Exception as exc:
                self.queue.metrics.failed += 1
                log.exception("worker %d failed on %s: %s", wid, event.event_id, exc)
            finally:
                self.latency_ms_last = int((time.perf_counter() - started) * 1000)
                self.queue.task_done()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [asyncio.create_task(self._worker(i)) for i in range(self.num_workers)]

    async def stop(self, drain_timeout_s: float = 5.0) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    drain_timeout_s,
                )
            except (TimeoutError, asyncio.CancelledError):
                pass
        self._tasks = []
