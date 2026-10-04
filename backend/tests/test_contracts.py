from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.domain.safety import clamp_severity
from app.domain.schemas import NormalizedEvent, RawEvent, normalize_raw
from app.main import create_app


def test_normalize_valid_sensor_event() -> None:
    raw = RawEvent(
        event_id="evt_abc",
        site_id="site-100",
        zone="lobby",
        type="motion_detected",
        source="sensor",
        confidence=0.8,
        timestamp="2026-10-01T12:00:00Z",
        metadata={},
    )
    evt = normalize_raw(raw)
    assert evt.event_id == "evt_abc"
    assert evt.timestamp.tzinfo is not None
    assert evt.timestamp == datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def test_missing_optional_fields_get_safe_defaults() -> None:
    raw = RawEvent(event_id="e1", site_id="s1", zone="z1")
    evt = normalize_raw(raw)
    assert evt.type == "motion_detected"
    assert evt.source == "sensor"
    assert evt.confidence == 0.5


def test_invalid_confidence_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedEvent(
            event_id="e",
            site_id="s",
            zone="z",
            type="motion_detected",
            source="sensor",
            confidence=9.9,
            timestamp=datetime.now(UTC),
        )


def test_timestamp_naive_normalized_to_utc() -> None:
    raw = RawEvent(event_id="e2", site_id="s1", zone="z1", timestamp="2026-10-01T12:00:00")
    evt = normalize_raw(raw)
    assert evt.timestamp.tzinfo == UTC


def test_deterministic_critical_cannot_downgrade() -> None:
    assert clamp_severity("fire_alarm", "info") == "critical"
    assert clamp_severity("panic_button", "warning") == "critical"
    assert clamp_severity("motion_detected", "info") == "info"


def test_health_endpoint() -> None:
    client = TestClient(create_app())
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
