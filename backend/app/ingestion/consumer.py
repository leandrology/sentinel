"""Continuous WebSocket consumer. Never awaits AI work in the read path."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import websockets

from app.ingestion.queue import IngestQueue, SubmitOutcome

log = logging.getLogger(__name__)


@dataclass
class ConsumerStatus:
    connected: bool = False
    reconnects: int = 0
    last_error: str | None = None


class EventConsumer:
    """Reads WS messages, validates, enqueues. Reconnects with backoff+jitter."""

    def __init__(
        self,
        queue: IngestQueue,
        url: str,
        base_s: float = 1.0,
        max_s: float = 30.0,
        connect_fn: Callable[[str], Any] | None = None,
    ) -> None:
        self.queue = queue
        self.url = url
        self.base_s = base_s
        self.max_s = max_s
        self.status = ConsumerStatus()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._attempt = 0
        self._connect_fn = connect_fn or (lambda u: websockets.connect(u))

    def handle_message(self, raw_text: str) -> SubmitOutcome | Literal["malformed"]:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            self.queue.metrics.malformed += 1
            log.warning("reject non-JSON frame")
            return "malformed"
        if not isinstance(payload, dict):
            self.queue.metrics.malformed += 1
            return "malformed"
        return self.queue.submit_dict(payload)

    async def run(self) -> None:
        self._running = True
        while self._running:
            try:
                cm = self._connect_fn(self.url)
                if inspect.isawaitable(cm):
                    cm = await cm
                async with cm as ws:  # type: ignore[union-attr]
                    self.status.connected = True
                    self.status.last_error = None
                    self._attempt = 0
                    log.info("ingest connected: %s", self.url)
                    async for message in ws:
                        if not self._running:
                            break
                        if isinstance(message, str):
                            text = message
                        else:
                            text = message.decode("utf-8", "ignore")
                        self.handle_message(text)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # reconnect on any transport failure
                self.status.connected = False
                self.status.last_error = f"{type(exc).__name__}: {exc}"
                self.status.reconnects += 1
                delay = self._backoff()
                log.warning("ingest down (%s), retry in %.1fs", self.status.last_error, delay)
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    raise
        self.status.connected = False

    def _backoff(self) -> float:
        self._attempt += 1
        delay = min(self.max_s, self.base_s * (2 ** (self._attempt - 1)))
        return delay + random.uniform(0, min(1.0, delay * 0.25))

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.status.connected = False
