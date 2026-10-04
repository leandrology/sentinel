"""SQLite models. Event history is immutable; status lives on Incident + changes."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    zone: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    snapshot_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Triage(Base):
    __tablename__ = "triages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("events.event_id"), unique=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    threat_assessment: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    certainty: Mapped[float] = mapped_column(Float)
    provider: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column("model", String(64))
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    triage_status: Mapped[str] = mapped_column(String(16), default="triaged")


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("events.event_id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    site_id: Mapped[str] = mapped_column(String(64), index=True)
    zone: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column("type", String(32))
    acknowledged_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class StatusChange(Base):
    __tablename__ = "status_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(16))
    to_status: Mapped[str] = mapped_column(String(16))
    actor: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)
    site_id: Mapped[str] = mapped_column(String(64))
    zone: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(32))
    count: Mapped[int] = mapped_column(Integer)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    event_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
