"""M5 realtime + API tests: hub fan-out, SSE framing, incident endpoints."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from app.domain.schemas import NormalizedEvent, TriageResult
from app.main import build_event_handler
from app.persistence import repo
from app.persistence.db import get_session_factory, init_db
from app.providers.mock import MockProvider
from app.realtime.hub import Hub
from app.realtime.sse import format_frame, incident_stream
from app.triage.service import TriageService
from app.triage.store import TriageStore


def _evt(i: str, **over: Any) -> NormalizedEvent:
    base: dict[str, Any] = {
        "event_id": f"sse_{i}",
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


def _tri(severity: str = "warning") -> TriageResult:
    return TriageResult(
        severity=severity,  # type: ignore[arg-type]
        threat_assessment="likely_threat",
        summary="Door forced.",
        recommended_action="Dispatch guard.",
        certainty=0.8,
        provider="mock",
        model="mock-v1",
    )


async def test_hub_fan_out_to_multiple_clients() -> None:
    hub = Hub()
    _, q1 = hub.subscribe()
    _, q2 = hub.subscribe()
    seq = hub.publish("incident", {"event_id": "e1"})
    assert seq == 1
    assert (await q1.get())["payload"] == {"event_id": "e1"}
    assert (await q2.get())["payload"] == {"event_id": "e1"}
    assert hub.subscribers == 2


async def test_hub_bounded_slow_client_drops_oldest() -> None:
    hub = Hub(maxsize=2)
    _, q = hub.subscribe()
    for i in range(5):
        hub.publish("incident", {"n": i})
    assert hub.dropped == 3
    got = [q.get_nowait()["payload"] for _ in range(2)]
    assert got == [{"n": 3}, {"n": 4}]


async def test_hub_unsubscribe_stops_delivery() -> None:
    hub = Hub()
    sub_id, q = hub.subscribe()
    hub.unsubscribe(sub_id)
    hub.publish("incident", {"n": 1})
    assert hub.subscribers == 0
    assert q.empty()


def test_sse_frame_format() -> None:
    frame = format_frame(7, "incident", {"a": 1})
    assert frame == 'id: 7\nevent: incident\ndata: {"a": 1}\n\n'


async def test_stream_replays_then_live(tmp_path) -> None:  # type: ignore[no-untyped-def]
    init_db(f"sqlite:///{tmp_path}/sse.db")
    factory = get_session_factory()
    with factory() as s:
        repo.save_event_and_triage(s, _evt("r1"), _tri())
        repo.save_event_and_triage(s, _evt("r2", type="fire_alarm"), _tri("critical"))
    hub = Hub()
    gen = incident_stream(hub, factory)
    try:
        replay = [json.loads((await gen.__anext__()).split("data: ")[1]) for _ in range(2)]
        assert [r["event_id"] for r in replay] == ["sse_r1", "sse_r2"]  # oldest first
        waiter = asyncio.create_task(gen.__anext__())
        await asyncio.sleep(0.2)  # let the generator reach its live subscription
        hub.publish("incident", {"event_id": "live-1"})
        live = await asyncio.wait_for(waiter, timeout=5.0)
        assert live.startswith("id: 1\nevent: incident\n")
        assert json.loads(live.split("data: ")[1])["event_id"] == "live-1"
    finally:
        await gen.aclose()
    assert hub.subscribers == 0  # connection cleanup


async def test_stream_heartbeat_on_idle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    init_db(f"sqlite:///{tmp_path}/hb.db")
    hub = Hub()
    gen = incident_stream(hub, get_session_factory(), heartbeat_s=0.05)
    try:
        assert await gen.__anext__() == ":ping\n\n"
    finally:
        await gen.aclose()


async def test_handler_persists_and_broadcasts(tmp_path) -> None:  # type: ignore[no-untyped-def]
    init_db(f"sqlite:///{tmp_path}/h.db")
    factory = get_session_factory()
    hub = Hub()
    _, q = hub.subscribe()
    handle = build_event_handler(TriageService(MockProvider()), TriageStore(), factory, hub)
    await handle(_evt("full", type="panic_button"))
    frame = await asyncio.wait_for(q.get(), timeout=2.0)
    assert frame["kind"] == "incident"
    assert frame["payload"]["status"] == "open"
    assert frame["payload"]["severity"] == "critical"
    assert frame["payload"]["event_id"] == "sse_full"
    with factory() as s:
        assert repo.get_detail(s, frame["payload"]["id"])["severity"] == "critical"


def _client(tmp_path):  # type: ignore[no-untyped-def]
    import os

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_path}/api.db"
    os.environ["INGEST_ENABLED"] = "false"
    os.environ["VIDEO_ENABLED"] = "false"
    client = TestClient(create_app())
    client.__enter__()
    return client


def test_incident_api_lifecycle(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import os

    from app.core.config import get_settings

    client = _client(tmp_path)
    try:
        app = client.app
        with app.state.db_session() as s:
            detail = repo.save_event_and_triage(s, _evt("api1"), _tri())
        iid = detail["id"]

        items = client.get("/api/incidents").json()["items"]
        assert len(items) == 1

        assert client.get(f"/api/incidents/{iid}").json()["event_id"] == "sse_api1"
        assert client.get("/api/incidents/999").status_code == 404

        ack = client.post(f"/api/incidents/{iid}/acknowledge", json={"actor": "op-1"}).json()
        assert ack == {"incident": ack["incident"], "changed": True}
        assert ack["incident"]["status"] == "acknowledged"
        again = client.post(f"/api/incidents/{iid}/acknowledge", json={"actor": "op-1"}).json()
        assert again["changed"] is False  # idempotent

        res = client.post(f"/api/incidents/{iid}/resolve", json={"actor": "op-2"}).json()
        assert res["incident"]["status"] == "resolved"

        conflict = client.post(f"/api/incidents/{iid}/acknowledge", json={"actor": "op-1"})
        assert conflict.status_code == 409  # resolved cannot be re-acknowledged

        assert client.get("/api/incidents", params={"status": "resolved"}).json()["items"]
        assert client.get("/api/incidents", params={"status": "open"}).json() == {"items": []}
    finally:
        client.__exit__(None, None, None)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("INGEST_ENABLED", None)
        os.environ.pop("VIDEO_ENABLED", None)
        get_settings.cache_clear()


async def test_sse_endpoint_streams_replay(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Endpoint wiring: correct content-type/headers + replay frames from the app.

    (Starlette's TestClient buffers StreamingResponse, so the route's
    body_iterator is driven directly instead of over HTTP.)
    """
    import os

    from fastapi import Request

    from app.api.routes import events_stream
    from app.core.config import get_settings

    client = _client(tmp_path)
    try:
        app = client.app
        with app.state.db_session() as s:
            repo.save_event_and_triage(s, _evt("stream1"), _tri())
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/events/stream",
            "query_string": b"",
            "headers": [],
            "app": app,
        }
        response = await events_stream(Request(scope))
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"

        frame = ""
        async for chunk in response.body_iterator:
            text = chunk if isinstance(chunk, str) else chunk.decode()
            if text.strip():
                frame = text
                break
        await response.body_iterator.aclose()  # releases the hub subscription
        assert frame.startswith("id: ")
        assert "\nevent: incident\n" in frame
        assert json.loads(frame.split("data: ")[1])["event_id"] == "sse_stream1"
    finally:
        client.__exit__(None, None, None)
        os.environ.pop("DATABASE_URL", None)
        os.environ.pop("INGEST_ENABLED", None)
        os.environ.pop("VIDEO_ENABLED", None)
        get_settings.cache_clear()
