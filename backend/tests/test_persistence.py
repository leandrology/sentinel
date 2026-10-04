"""M5 persistence tests. Tmp SQLite file per test; no app required."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.domain.schemas import NormalizedEvent, TriageResult
from app.persistence import repo
from app.persistence.db import get_session_factory, init_db
from app.persistence.models import Escalation, Event, Incident, StatusChange


def _evt(i: str, **over: Any) -> NormalizedEvent:
    base: dict[str, Any] = {
        "event_id": f"evt_{i}",
        "site_id": "site-100",
        "zone": "lobby",
        "type": "motion_detected",
        "source": "sensor",
        "confidence": 0.7,
        "timestamp": datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
        "metadata": {},
    }
    base.update(over)
    return NormalizedEvent(**base)


def _tri(**over: Any) -> TriageResult:
    base: dict[str, Any] = {
        "severity": "info",
        "threat_assessment": "uncertain",
        "summary": "Motion in lobby.",
        "recommended_action": "Review footage.",
        "certainty": 0.5,
        "provider": "mock",
        "model": "mock-v1",
    }
    base.update(over)
    return TriageResult(**base)


@pytest.fixture
def db(tmp_path):  # type: ignore[no-untyped-def]
    init_db(f"sqlite:///{tmp_path}/t.db")
    return get_session_factory()


def test_save_creates_open_incident(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        detail = repo.save_event_and_triage(s, _evt("a"), _tri(severity="warning"))
    assert detail["status"] == "open"
    assert detail["severity"] == "warning"
    assert detail["site_id"] == "site-100"
    assert detail["timestamp"] == "2026-10-01T12:00:00+00:00"


def test_duplicate_event_id_is_idempotent(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        first = repo.save_event_and_triage(s, _evt("dup"), _tri())
        second = repo.save_event_and_triage(s, _evt("dup"), _tri())
        assert first["id"] == second["id"]
        assert s.query(Event).count() == 1
        assert s.query(Incident).count() == 1


def test_acknowledge_flow_and_idempotency(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        detail = repo.save_event_and_triage(s, _evt("ack1"), _tri())
        item, changed = repo.acknowledge(s, detail["id"], actor="op-1")
        assert changed is True
        assert item["status"] == "acknowledged"
        assert item["acknowledged_by"] == "op-1"
        item2, changed2 = repo.acknowledge(s, detail["id"], actor="op-1")
        assert changed2 is False
        changes = s.query(StatusChange).filter_by(incident_id=detail["id"]).all()
        assert [(c.from_status, c.to_status) for c in changes] == [
            ("none", "open"),
            ("open", "acknowledged"),
        ]


def test_acknowledge_resolved_is_rejected(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        detail = repo.save_event_and_triage(s, _evt("ack2"), _tri())
        repo.resolve(s, detail["id"])
        with pytest.raises(repo.InvalidTransition):
            repo.acknowledge(s, detail["id"])


def test_resolve_flow_and_idempotency(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        detail = repo.save_event_and_triage(s, _evt("res1"), _tri())
        item, changed = repo.resolve(s, detail["id"], actor="op-2")
        assert changed is True
        assert item["status"] == "resolved"
        assert item["resolved_by"] == "op-2"
        _, changed2 = repo.resolve(s, detail["id"])
        assert changed2 is False


def test_missing_incident_raises_key_error(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        with pytest.raises(KeyError):
            repo.acknowledge(s, 999)
        assert repo.get_detail(s, 999) is None


def test_list_ordering_and_filters(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        repo.save_event_and_triage(s, _evt("o1"), _tri(severity="info"))
        repo.save_event_and_triage(s, _evt("o2"), _tri(severity="critical"))
        repo.save_event_and_triage(s, _evt("o3", site_id="site-101"), _tri(severity="warning"))
        items = repo.list_incidents(s)
        assert [i["severity"] for i in items] == ["critical", "warning", "info"]
        assert [i["site_id"] for i in repo.list_incidents(s, site_id="site-101")] == ["site-101"]
        assert len(repo.list_incidents(s, severity="critical")) == 1
        repo.acknowledge(s, items[0]["id"])
        assert len(repo.list_incidents(s, status="acknowledged")) == 1
        assert len(repo.list_incidents(s, status="open")) == 2


def test_escalation_upsert_is_idempotent(db) -> None:  # type: ignore[no-untyped-def]
    with db() as s:
        d1 = repo.save_event_and_triage(s, _evt("e1", type="perimeter_breach"), _tri())
        d2 = repo.save_event_and_triage(s, _evt("e2", type="perimeter_breach"), _tri())
        now = datetime.now(UTC)
        esc1, created1 = repo.record_escalation(
            s,
            "site-100|lobby|2026-10-01T12",
            "site-100",
            "lobby",
            "perimeter_breach",
            2,
            now - timedelta(minutes=5),
            now,
            [d1["event_id"], d2["event_id"]],
        )
        esc2, created2 = repo.record_escalation(
            s,
            "site-100|lobby|2026-10-01T12",
            "site-100",
            "lobby",
            "perimeter_breach",
            2,
            now - timedelta(minutes=5),
            now,
            [d1["event_id"], d2["event_id"]],
        )
        assert created1 is True and created2 is False
        assert esc1["id"] == esc2["id"]
        assert s.query(Escalation).count() == 1
        flagged = s.query(Incident).filter_by(escalated=True).count()
        assert flagged == 2
