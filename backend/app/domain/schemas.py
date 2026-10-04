"""Shared event contracts. Single source of truth for sensor + camera events."""

from datetime import UTC, datetime
from typing import Any, Literal

from dateutil import parser as date_parser
from pydantic import BaseModel, Field, field_validator

EventType = Literal[
    "motion_detected",
    "perimeter_breach",
    "door_forced",
    "glass_break",
    "smoke_detected",
    "fire_alarm",
    "object_detected",
    "loitering",
    "camera_offline",
    "sensor_fault",
    "panic_button",
]

EventSource = Literal["sensor", "camera"]

Severity = Literal["info", "warning", "critical"]
ThreatAssessment = Literal["likely_threat", "probable_false_positive", "uncertain"]


class RawEvent(BaseModel):
    """Untrusted external payload. All fields optional except identity triple."""

    model_config = {"extra": "ignore"}

    event_id: str = Field(min_length=1)
    site_id: str = Field(min_length=1)
    zone: str = Field(min_length=1)
    type: EventType | None = None
    source: EventSource | None = None
    confidence: float | None = None
    timestamp: str | datetime | None = None
    snapshot_url: str | None = None
    metadata: dict[str, Any] | None = None


class NormalizedEvent(BaseModel):
    """Validated internal event. Timestamps always UTC."""

    event_id: str
    site_id: str
    zone: str
    type: EventType
    source: EventSource
    confidence: float = 0.5
    timestamp: datetime
    snapshot_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be in [0, 1]")
        return v

    @field_validator("timestamp", mode="before")
    @classmethod
    def _normalize_ts(cls, v: Any) -> datetime:
        if v is None:
            return datetime.now(UTC)
        if isinstance(v, datetime):
            dt = v
        else:
            dt = date_parser.isoparse(str(v).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)


def parse_timestamp(v: str | datetime | None) -> datetime:
    """Coerce untrusted timestamp input to UTC. Naive values assumed UTC."""
    if v is None:
        return datetime.now(UTC)
    dt = v if isinstance(v, datetime) else date_parser.isoparse(str(v).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def normalize_raw(raw: RawEvent) -> NormalizedEvent:
    """Apply safe defaults for missing optional fields. Raises ValidationError on bad ranges."""
    return NormalizedEvent(
        event_id=raw.event_id,
        site_id=raw.site_id,
        zone=raw.zone,
        type=raw.type or "motion_detected",
        source=raw.source or "sensor",
        confidence=0.5 if raw.confidence is None else raw.confidence,
        timestamp=parse_timestamp(raw.timestamp),
        snapshot_url=raw.snapshot_url,
        metadata=raw.metadata or {},
    )


class TriageResult(BaseModel):
    """Strict AI triage output. Extra fields forbidden."""

    model_config = {"extra": "forbid"}

    severity: Severity
    threat_assessment: ThreatAssessment
    summary: str = Field(min_length=1, max_length=500)
    recommended_action: str = Field(min_length=1, max_length=500)
    certainty: float = Field(ge=0.0, le=1.0)
    provider: str = "unknown"
    model: str = "unknown"
    latency_ms: int = 0
    retries: int = 0
    fallback: bool = False
    triage_status: Literal["triaged", "fallback", "failed"] = "triaged"
