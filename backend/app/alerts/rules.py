"""Deterministic correlation rules. Independent of the LLM by design.

Rule: repeated ``perimeter_breach`` events at the same site and zone within
a fixed time window trigger one escalation. Windows are bucketed
(``floor(timestamp / window)``), so each bucket yields at most one
escalation record — repeats in the same bucket are ignored, and the next
bucket may escalate again. Every escalation traces to its event IDs.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.schemas import NormalizedEvent
from app.persistence import repo
from app.persistence.models import Event

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def window_bounds(ts: datetime, window_s: int) -> tuple[datetime, datetime]:
    start_secs = math.floor((ts - _EPOCH).total_seconds() / window_s) * window_s
    start = _EPOCH + timedelta(seconds=start_secs)
    return start, start + timedelta(seconds=window_s)


def check_repeated_breach(
    session: Session,
    event: NormalizedEvent,
    window_s: int = 300,
    threshold: int = 3,
) -> dict | None:
    """Return the new escalation dict, or None when no new escalation."""
    if event.type != "perimeter_breach":
        return None
    start, end = window_bounds(event.timestamp, window_s)
    rows = (
        session.query(Event)
        .filter(
            Event.type == "perimeter_breach",
            Event.site_id == event.site_id,
            Event.zone == event.zone,
            Event.timestamp >= start,
            Event.timestamp < end,
        )
        .order_by(Event.id)
        .all()
    )
    if len(rows) < threshold:
        return None
    key = f"{event.site_id}|{event.zone}|perimeter_breach|{int(start.timestamp())}"
    escalation, created = repo.record_escalation(
        session,
        key=key,
        site_id=event.site_id,
        zone=event.zone,
        event_type="perimeter_breach",
        count=len(rows),
        window_start=start,
        window_end=end,
        event_ids=[r.event_id for r in rows],
    )
    return escalation if created else None
