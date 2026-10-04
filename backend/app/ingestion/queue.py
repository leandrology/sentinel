"""Bounded ingestion queue with explicit overload policy.

Policy: never block the WebSocket reader. ``submit`` is synchronous and uses
``put_nowait``. When full, incoming non-critical events are dropped + counted;
incoming critical events (fire_alarm / panic_button) evict the oldest queued
event to make room, preserving the new critical. All drops/evictions are
exposed via metrics and logs — nothing is silently lost.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from app.domain.safety import is_deterministic_critical
from app.domain.schemas import NormalizedEvent, RawEvent, normalize_raw

log = logging.getLogger(__name__)

SubmitOutcome = Literal["enqueued", "duplicate", "malformed", "dropped", "critical-evicted"]

SEEN_CAP = 20_000


@dataclass
class IngestMetrics:
    enqueued: int = 0
    processed: int = 0
    failed: int = 0
    dropped_noncritical: int = 0
    evicted: int = 0
    duplicates: int = 0
    malformed: int = 0
    high_water_mark: int = 0


@dataclass
class IngestQueue:
    maxsize: int = 500
    metrics: IngestMetrics = field(default_factory=IngestMetrics)
    _queue: asyncio.Queue[NormalizedEvent] = field(init=False)
    _seen: set[str] = field(default_factory=set, init=False)
    _seen_order: deque[str] = field(default_factory=deque, init=False)

    def __post_init__(self) -> None:
        self._queue = asyncio.Queue(maxsize=self.maxsize)

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    def _remember(self, event_id: str) -> bool:
        """Return True if already seen (duplicate), else record and return False."""
        if event_id in self._seen:
            return True
        self._seen.add(event_id)
        self._seen_order.append(event_id)
        if len(self._seen) > SEEN_CAP:  # bounded dedupe memory
            oldest = self._seen_order.popleft()
            self._seen.discard(oldest)
        return False

    def submit_dict(self, payload: dict[str, Any]) -> SubmitOutcome:
        try:
            raw = RawEvent(**payload)
            event = normalize_raw(raw)
        except ValidationError as exc:
            self.metrics.malformed += 1
            log.warning("reject malformed event: %s", exc.errors()[0].get("msg"))
            return "malformed"
        return self.submit_event(event)

    def submit_event(self, event: NormalizedEvent) -> SubmitOutcome:
        if self._remember(event.event_id):
            self.metrics.duplicates += 1
            return "duplicate"
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            if is_deterministic_critical(event.type):
                self._evict_oldest()
                try:
                    self._queue.put_nowait(event)
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    self.metrics.dropped_noncritical += 1
                    return "dropped"
                self.metrics.evicted += 1
                self.metrics.enqueued += 1
                self._touch_high_water()
                log.warning("queue full: evicted oldest to preserve critical %s", event.event_id)
                return "critical-evicted"
            self.metrics.dropped_noncritical += 1
            log.warning("queue full: dropped non-critical %s", event.event_id)
            return "dropped"
        self.metrics.enqueued += 1
        self._touch_high_water()
        return "enqueued"

    def _evict_oldest(self) -> None:
        """Drop oldest queued event to free one slot. Prefers non-critical victims."""
        drained: list[NormalizedEvent] = []
        try:
            while True:
                drained.append(self._queue.get_nowait())
        except asyncio.QueueEmpty:
            pass
        victim_idx = 0
        for i, evt in enumerate(drained):
            if not is_deterministic_critical(evt.type):
                victim_idx = i
                break
        for i, evt in enumerate(drained):
            if i != victim_idx:
                try:
                    self._queue.put_nowait(evt)
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    self.metrics.dropped_noncritical += 1

    def _touch_high_water(self) -> None:
        depth = self._queue.qsize()
        if depth > self.metrics.high_water_mark:
            self.metrics.high_water_mark = depth

    async def get(self) -> NormalizedEvent:
        return await self._queue.get()

    def task_done(self) -> None:
        self._queue.task_done()
