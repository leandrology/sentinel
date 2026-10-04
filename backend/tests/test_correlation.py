"""M7 correlation + reliability: escalation rule, bursts, AI-down, shutdown."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.schemas import NormalizedEvent
from app.ingestion.consumer import EventConsumer
from app.ingestion.queue import IngestQueue
from app.main import build_event_handler
from app.persistence import repo
from app.persistence.db import get_session_factory, init_db
from app.processing.pipeline import WorkerPool
from app.providers.base import TriageProvider
from app.providers.mock import MockProvider
from app.realtime.hub import Hub
from app.triage.service import TriageService
from app.triage.store import TriageStore
from app.vision.worker import VideoWorker

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def _breach(i: int, at: datetime | None = None, **over: Any) -> NormalizedEvent:
    base: dict[str, Any] = {
        "event_id": f"br_{i}",
        "site_id": "site-100",
        "zone": "north-perimeter",
        "type": "perimeter_breach",
        "source": "sensor",
        "confidence": 0.8,
        "timestamp": at or (T0 + timedelta(seconds=i * 10)),
        "metadata": {},
    }
    base.update(over)
    return NormalizedEvent(**base)


def _ctx(tmp_path, provider=None, window_s=300, threshold=3):  # type: ignore[no-untyped-def]
    init_db(f"sqlite:///{tmp_path}/corr.db")
    factory = get_session_factory()
    hub = Hub()
    _, q = hub.subscribe()
    handle = build_event_handler(
        TriageService(provider or MockProvider()),
        TriageStore(),
        factory,
        hub,
        corr_window_s=window_s,
        corr_threshold=threshold,
    )
    return factory, hub, q, handle


async def _drain(queue: IngestQueue, timeout_s: float = 15.0) -> None:
    await asyncio.wait_for(queue._queue.join(), timeout=timeout_s)


def _frames(queue) -> list[dict]:  # type: ignore[no-untyped-def]
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


async def test_escalation_fires_on_threshold(tmp_path) -> None:  # type: ignore[no-untyped-def]
    factory, hub, sub, handle = _ctx(tmp_path)
    for i in range(3):
        await handle(_breach(i))
    frames = _frames(sub)
    incidents = [f for f in frames if f["kind"] == "incident"]
    escalations = [f for f in frames if f["kind"] == "escalation"]
    assert len(incidents) == 3
    assert len(escalations) == 1
    esc = escalations[0]["payload"]
    assert esc["site_id"] == "site-100" and esc["zone"] == "north-perimeter"
    assert esc["count"] == 3 and len(esc["event_ids"]) == 3
    with factory() as s:
        assert s.query(repo.Incident).filter_by(escalated=True).count() == 3
        assert incidents[-1]["payload"]["escalated"] is True  # frame carries the flag


async def test_no_duplicate_escalation_in_same_window(tmp_path) -> None:  # type: ignore[no-untyped-def]
    factory, hub, sub, handle = _ctx(tmp_path)
    for i in range(5):
        await handle(_breach(i))
    frames = _frames(sub)
    assert len([f for f in frames if f["kind"] == "escalation"]) == 1


async def test_new_window_may_escalate_again(tmp_path) -> None:  # type: ignore[no-untyped-def]
    factory, hub, sub, handle = _ctx(tmp_path)
    for i in range(3):
        await handle(_breach(i))
    later = T0 + timedelta(seconds=400)  # next 300s bucket
    for i in range(3, 6):
        await handle(_breach(i, at=later + timedelta(seconds=(i - 3) * 10)))
    frames = _frames(sub)
    assert len([f for f in frames if f["kind"] == "escalation"]) == 2


async def test_other_zones_types_do_not_correlate(tmp_path) -> None:  # type: ignore[no-untyped-def]
    factory, hub, sub, handle = _ctx(tmp_path)
    await handle(_breach(0, zone="lobby"))
    await handle(_breach(1, zone="lobby"))
    await handle(_breach(2, zone="roof"))
    motions = [
        NormalizedEvent(
            event_id=f"m_{i}",
            site_id="site-100",
            zone="north-perimeter",
            type="motion_detected",
            source="sensor",
            confidence=0.6,
            timestamp=T0 + timedelta(seconds=i),
            metadata={},
        )
        for i in range(5)
    ]
    for m in motions:
        await handle(m)
    frames = _frames(sub)
    assert [f for f in frames if f["kind"] == "escalation"] == []


async def test_threshold_is_configurable(tmp_path) -> None:  # type: ignore[no-untyped-def]
    factory, hub, sub, handle = _ctx(tmp_path, threshold=2)
    await handle(_breach(0))
    assert [f for f in _frames(sub) if f["kind"] == "escalation"] == []
    await handle(_breach(1))
    assert len([f for f in _frames(sub) if f["kind"] == "escalation"]) == 1


async def test_correlation_survives_ai_failure(tmp_path) -> None:  # type: ignore[no-untyped-def]
    class Boom(TriageProvider):
        name = "boom"

        async def triage(self, event: NormalizedEvent) -> Any:
            raise RuntimeError("llm down")

    factory, hub, sub, handle = _ctx(tmp_path, provider=Boom())
    for i in range(3):
        await handle(_breach(i))
    frames = _frames(sub)
    assert len([f for f in frames if f["kind"] == "incident"]) == 3
    assert all(f["payload"]["fallback"] for f in frames if f["kind"] == "incident")
    assert len([f for f in frames if f["kind"] == "escalation"]) == 1


async def test_burst_through_full_pipeline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """60 bursty events: all persisted once, escalation bounded, nothing lost."""
    init_db(f"sqlite:///{tmp_path}/burst.db")
    factory = get_session_factory()
    hub = Hub()
    queue = IngestQueue(maxsize=500)
    pool = WorkerPool(
        queue,
        num_workers=4,
        process_fn=build_event_handler(
            TriageService(MockProvider()),
            TriageStore(),
            factory,
            hub,
            corr_window_s=3600,
            corr_threshold=3,
        ),
    )
    pool.start()
    try:
        for i in range(60):
            typ = "perimeter_breach" if i % 10 < 6 else "motion_detected"
            ok = queue.submit_dict(
                {
                    "event_id": f"burst_{i}",
                    "site_id": "site-100",
                    "zone": "north-perimeter",
                    "type": typ,
                    "source": "sensor",
                    "confidence": 0.8,
                    "timestamp": (T0 + timedelta(seconds=i)).isoformat(),
                    "metadata": {},
                }
            )
            assert ok == "enqueued"
        await _drain(queue)
        with factory() as s:
            assert s.query(repo.Event).count() == 60
            assert s.query(repo.Incident).count() == 60
            assert s.query(repo.Escalation).count() == 1  # 6 breaches, one window
    finally:
        await pool.stop()


async def test_graceful_shutdown_of_all_workers(tmp_path) -> None:  # type: ignore[no-untyped-def]
    init_db(f"sqlite:///{tmp_path}/down.db")
    queue = IngestQueue(maxsize=10)
    pool = WorkerPool(queue, num_workers=2)
    consumer = EventConsumer(queue, url="ws://localhost:9", base_s=0.01, max_s=0.05)
    video = VideoWorker(queue, source="/nonexistent/down.mp4", sample_fps=10.0)
    pool.start()
    consumer.start()
    video.start()
    await asyncio.sleep(0.5)
    await asyncio.wait_for(video.stop(), timeout=5.0)
    await asyncio.wait_for(consumer.stop(), timeout=5.0)
    await asyncio.wait_for(pool.stop(), timeout=5.0)
    assert video.running is False
    assert consumer.status.connected is False
    assert time.monotonic()  # reached: nothing hung
