"""Repository: transactions, idempotency, guarded state transitions.

Idempotency: duplicate ``event_id`` returns the existing incident (handles
DB races via IntegrityError retry). Ack/resolve repeat safely.
Transitions: open -> acknowledged -> resolved, plus open -> resolved.
Acknowledging a resolved incident is a 409, not a reopen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.schemas import NormalizedEvent, TriageResult
from app.persistence.models import Escalation, Event, Incident, StatusChange, Triage


class InvalidTransition(Exception):
    pass


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def _iso(dt: datetime | None, default: datetime | None = None) -> str | None:
    value = _utc(dt)
    if value is None and default is not None:
        value = default if default.tzinfo else default.replace(tzinfo=UTC)
    return value.isoformat() if value is not None else None


def serialize_detail(incident: Incident, event: Event, triage: Triage) -> dict[str, Any]:
    ts = _utc(event.timestamp)
    return {
        "id": incident.id,
        "event_id": event.event_id,
        "site_id": event.site_id,
        "zone": event.zone,
        "type": event.type,
        "source": event.source,
        "confidence": event.confidence,
        "timestamp": ts.isoformat() if ts else None,
        "snapshot_url": event.snapshot_url,
        "metadata": event.event_metadata or {},
        "severity": triage.severity,
        "threat_assessment": triage.threat_assessment,
        "summary": triage.summary,
        "recommended_action": triage.recommended_action,
        "certainty": triage.certainty,
        "provider": triage.provider,
        "model": triage.model_name,
        "fallback": triage.fallback,
        "triage_status": triage.triage_status,
        "status": incident.status,
        "acknowledged_by": incident.acknowledged_by,
        "acknowledged_at": _iso(incident.acknowledged_at),
        "resolved_by": incident.resolved_by,
        "resolved_at": _iso(incident.resolved_at),
        "escalated": incident.escalated,
        "created_at": _iso(incident.created_at, datetime.now(UTC)),
        "updated_at": _iso(incident.updated_at, datetime.now(UTC)),
    }


def save_event_and_triage(
    session: Session, event: NormalizedEvent, triage: TriageResult
) -> dict[str, Any]:
    """Persist event + triage + incident. Duplicate event_id returns existing."""
    existing = session.query(Incident).filter_by(event_id=event.event_id).first()
    if existing is not None:
        return get_detail(session, existing.id)  # type: ignore[return-value]
    now = datetime.now(UTC)
    try:
        session.add(
            Event(
                event_id=event.event_id,
                site_id=event.site_id,
                zone=event.zone,
                type=event.type,
                source=event.source,
                confidence=event.confidence,
                timestamp=event.timestamp,
                snapshot_url=event.snapshot_url,
                event_metadata=event.metadata,
            )
        )
        session.add(
            Triage(
                event_id=event.event_id,
                severity=triage.severity,
                threat_assessment=triage.threat_assessment,
                summary=triage.summary,
                recommended_action=triage.recommended_action,
                certainty=triage.certainty,
                provider=triage.provider,
                model_name=triage.model,
                latency_ms=triage.latency_ms,
                retries=triage.retries,
                fallback=triage.fallback,
                triage_status=triage.triage_status,
            )
        )
        incident = Incident(
            event_id=event.event_id,
            status="open",
            severity=triage.severity,
            site_id=event.site_id,
            zone=event.zone,
            event_type=event.type,
            created_at=now,
            updated_at=now,
        )
        session.add(incident)
        session.flush()
        session.add(
            StatusChange(
                incident_id=incident.id, from_status="none", to_status="open", actor="system"
            )
        )
        session.commit()
    except IntegrityError:  # lost a race with another worker on same event_id
        session.rollback()
        existing = session.query(Incident).filter_by(event_id=event.event_id).first()
        return get_detail(session, existing.id)  # type: ignore[union-attr, return-value]
    return get_detail(session, incident.id)  # type: ignore[return-value]


def get_detail(session: Session, incident_id: int) -> dict[str, Any] | None:
    incident = session.query(Incident).filter_by(id=incident_id).first()
    if incident is None:
        return None
    event = session.query(Event).filter_by(event_id=incident.event_id).first()
    triage = session.query(Triage).filter_by(event_id=incident.event_id).first()
    if event is None or triage is None:
        return None
    return serialize_detail(incident, event, triage)


def list_incidents(
    session: Session,
    status: str | None = None,
    site_id: str | None = None,
    zone: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rank = case({"critical": 0, "warning": 1, "info": 2}, value=Incident.severity, else_=3)
    q = (
        session.query(Incident, Event, Triage)
        .join(Event, Event.event_id == Incident.event_id)
        .join(Triage, Triage.event_id == Incident.event_id)
    )
    if status:
        q = q.filter(Incident.status == status)
    if site_id:
        q = q.filter(Incident.site_id == site_id)
    if zone:
        q = q.filter(Incident.zone == zone)
    if severity:
        q = q.filter(Incident.severity == severity)
    rows = q.order_by(rank, Incident.id.desc()).limit(limit).offset(offset).all()
    return [serialize_detail(i, e, t) for i, e, t in rows]


def acknowledge(
    session: Session, incident_id: int, actor: str = "operator"
) -> tuple[dict[str, Any], bool]:
    incident = session.query(Incident).filter_by(id=incident_id).first()
    if incident is None:
        raise KeyError(incident_id)
    if incident.status == "resolved":
        raise InvalidTransition("cannot acknowledge a resolved incident")
    if incident.status == "acknowledged":
        return get_detail(session, incident_id), False  # type: ignore[return-value]
    incident.status = "acknowledged"
    incident.acknowledged_by = actor
    incident.acknowledged_at = datetime.now(UTC)
    incident.updated_at = datetime.now(UTC)
    session.add(
        StatusChange(
            incident_id=incident.id, from_status="open", to_status="acknowledged", actor=actor
        )
    )
    session.commit()
    return get_detail(session, incident_id), True  # type: ignore[return-value]


def resolve(
    session: Session, incident_id: int, actor: str = "operator"
) -> tuple[dict[str, Any], bool]:
    incident = session.query(Incident).filter_by(id=incident_id).first()
    if incident is None:
        raise KeyError(incident_id)
    if incident.status == "resolved":
        return get_detail(session, incident_id), False  # type: ignore[return-value]
    from_status = incident.status
    incident.status = "resolved"
    incident.resolved_by = actor
    incident.resolved_at = datetime.now(UTC)
    incident.updated_at = datetime.now(UTC)
    session.add(
        StatusChange(
            incident_id=incident.id, from_status=from_status, to_status="resolved", actor=actor
        )
    )
    session.commit()
    return get_detail(session, incident_id), True  # type: ignore[return-value]


def record_escalation(
    session: Session,
    key: str,
    site_id: str,
    zone: str,
    event_type: str,
    count: int,
    window_start: datetime,
    window_end: datetime,
    event_ids: list[str],
) -> tuple[dict[str, Any], bool]:
    """Upsert by correlation key: same window never creates a second record."""
    existing = session.query(Escalation).filter_by(key=key).first()
    if existing is not None:
        return _escalation_dict(existing), False
    esc = Escalation(
        key=key,
        site_id=site_id,
        zone=zone,
        event_type=event_type,
        count=count,
        window_start=window_start,
        window_end=window_end,
        event_ids=event_ids,
    )
    session.add(esc)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.query(Escalation).filter_by(key=key).first()
        return _escalation_dict(existing), False  # type: ignore[arg-type]
    session.query(Incident).filter(Incident.event_id.in_(event_ids)).update(
        {"escalated": True}, synchronize_session=False
    )
    session.commit()
    return _escalation_dict(esc), True


def _escalation_dict(esc: Escalation) -> dict[str, Any]:
    return {
        "id": esc.id,
        "key": esc.key,
        "site_id": esc.site_id,
        "zone": esc.zone,
        "event_type": esc.event_type,
        "count": esc.count,
        "window_start": _iso(esc.window_start, datetime.now(UTC)),
        "window_end": _iso(esc.window_end, datetime.now(UTC)),
        "event_ids": esc.event_ids or [],
    }
