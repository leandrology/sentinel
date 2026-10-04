"""SSE framing + stream: replay recent history, then live hub frames."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from sqlalchemy.orm import Session

from app.persistence import repo
from app.realtime.hub import Hub

SessionFactory = Callable[[], Session]


def format_frame(seq: int, event: str, data: dict[str, Any]) -> str:
    return f"id: {seq}\nevent: {event}\ndata: {json.dumps(data)}\n\n"


async def incident_stream(
    hub: Hub,
    session_factory: SessionFactory,
    limit: int = 100,
    heartbeat_s: float = 15.0,
) -> AsyncIterator[str]:
    """Yield replay frames (oldest first), then live frames + heartbeats.

    Reconnect recovery: clients load REST history and dedupe by ``event_id``,
    so replay is bounded recent history rather than precise gap-fill.
    """
    recent = await asyncio.to_thread(_recent_incidents, session_factory, limit)
    for item in recent:
        yield format_frame(item["id"], "incident", item)
    sub_id, queue = hub.subscribe()
    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=heartbeat_s)
            except TimeoutError:
                yield ":ping\n\n"
                continue
            yield format_frame(msg["seq"], msg["kind"], msg["payload"])
    finally:
        hub.unsubscribe(sub_id)


def _recent_incidents(session_factory: SessionFactory, limit: int) -> list[dict[str, Any]]:
    with session_factory() as session:
        rows = repo.list_incidents(session, limit=limit)
    rows.reverse()  # list_incidents is newest-first; replay oldest-first
    return rows
