"""In-process broadcast hub. One producer (pipeline), N dashboard clients.

No database polling per client: workers publish once, the hub fans out to
each subscriber's bounded queue. A slow client drops its oldest buffered
frame (counted in ``dropped``) instead of stalling the hub.

Limitation: sequence numbers reset on restart; clients reconcile by
``event_id`` dedupe plus REST history load.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hub:
    maxsize: int = 100
    dropped: int = 0
    _subs: dict[int, asyncio.Queue[dict[str, Any]]] = field(default_factory=dict)
    _seq: int = 0
    _next_id: int = 1

    def subscribe(self) -> tuple[int, asyncio.Queue[dict[str, Any]]]:
        sub_id = self._next_id
        self._next_id += 1
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self.maxsize)
        self._subs[sub_id] = queue
        return sub_id, queue

    def unsubscribe(self, sub_id: int) -> None:
        self._subs.pop(sub_id, None)

    @property
    def subscribers(self) -> int:
        return len(self._subs)

    def publish(self, kind: str, payload: dict[str, Any]) -> int:
        """Fan out one frame. Returns its sequence number."""
        self._seq += 1
        frame = {"seq": self._seq, "kind": kind, "payload": payload}
        for queue in self._subs.values():
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(frame)
                except asyncio.QueueFull:  # pragma: no cover - defensive
                    pass
                self.dropped += 1
        return self._seq
