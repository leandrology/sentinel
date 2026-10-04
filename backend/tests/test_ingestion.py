"""M2 ingestion tests: validation, dedupe, bounded queue, workers, reconnect."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.domain.schemas import NormalizedEvent
from app.ingestion.consumer import EventConsumer
from app.ingestion.queue import IngestQueue
from app.processing.pipeline import WorkerPool


def _payload(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_id": "evt_test",
        "site_id": "site-100",
        "zone": "lobby",
        "type": "motion_detected",
        "source": "sensor",
        "confidence": 0.7,
        "timestamp": "2026-10-01T12:00:00Z",
        "metadata": {},
    }
    base.update(over)
    return base


def test_submit_valid_and_defaults() -> None:
    q = IngestQueue(maxsize=10)
    assert q.submit_dict(_payload(event_id="e1")) == "enqueued"
    assert q.submit_dict({"event_id": "e2", "site_id": "s", "zone": "z"}) == "enqueued"
    assert q.depth == 2


def test_malformed_rejected() -> None:
    q = IngestQueue(maxsize=10)
    c = EventConsumer(q, url="ws://test")
    assert c.handle_message("not-json{{{") == "malformed"
    assert c.handle_message(json.dumps(["list-not-dict"])) == "malformed"
    assert c.handle_message(json.dumps(_payload(event_id="m1", confidence=5.0))) == "malformed"
    assert c.handle_message(json.dumps({"site_id": "s"})) == "malformed"  # missing event_id
    assert q.depth == 0
    assert q.metrics.malformed == 4
    # consumer survives: next valid frame accepted
    assert c.handle_message(json.dumps(_payload(event_id="m2"))) == "enqueued"


def test_duplicate_idempotent() -> None:
    q = IngestQueue(maxsize=10)
    assert q.submit_dict(_payload(event_id="dup")) == "enqueued"
    assert q.submit_dict(_payload(event_id="dup")) == "duplicate"
    assert q.depth == 1
    assert q.metrics.duplicates == 1


def test_queue_full_drops_noncritical_with_metric() -> None:
    q = IngestQueue(maxsize=2)
    assert q.submit_dict(_payload(event_id="a")) == "enqueued"
    assert q.submit_dict(_payload(event_id="b")) == "enqueued"
    assert q.submit_dict(_payload(event_id="c")) == "dropped"
    assert q.metrics.dropped_noncritical == 1
    assert q.depth == 2


def test_queue_full_preserves_critical_by_eviction() -> None:
    q = IngestQueue(maxsize=2)
    q.submit_dict(_payload(event_id="a", type="motion_detected"))
    q.submit_dict(_payload(event_id="b", type="door_forced"))
    outcome = q.submit_dict(_payload(event_id="fire1", type="fire_alarm"))
    assert outcome == "critical-evicted"
    assert q.metrics.evicted == 1
    assert q.depth == 2
    # incoming critical present, one non-critical victim gone
    ids = set()
    while q.depth:
        evt = q._queue.get_nowait()
        ids.add(evt.event_id)
    assert "fire1" in ids
    assert len(ids) == 2


def test_timestamp_normalized_to_utc() -> None:
    q = IngestQueue(maxsize=10)
    q.submit_dict(_payload(event_id="t1", timestamp="2026-10-01T12:00:00"))
    evt = q._queue.get_nowait()
    assert evt.timestamp.tzinfo is not None
    assert str(evt.timestamp.tzinfo) == "UTC"


async def test_burst_does_not_block_reader_on_slow_downstream() -> None:
    """Reader submit stays fast (<50ms for 200) even when workers are slow."""
    import time

    q = IngestQueue(maxsize=500)

    async def slow(_: NormalizedEvent) -> None:
        await asyncio.sleep(0.05)

    pool = WorkerPool(q, num_workers=2, process_fn=slow)
    pool.start()
    try:
        start = time.perf_counter()
        for i in range(200):
            assert q.submit_dict(_payload(event_id=f"burst-{i}")) == "enqueued"
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0  # reader never awaited the 50ms downstream work
        await asyncio.wait_for(q._queue.join(), timeout=15.0)
        assert q.metrics.processed == 200
    finally:
        await pool.stop()


async def test_concurrent_workers_drain() -> None:
    q = IngestQueue(maxsize=100)
    seen: set[str] = set()

    async def record(evt: NormalizedEvent) -> None:
        seen.add(evt.event_id)

    pool = WorkerPool(q, num_workers=4, process_fn=record)
    pool.start()
    try:
        for i in range(50):
            q.submit_dict(_payload(event_id=f"cc-{i}"))
        await asyncio.wait_for(q._queue.join(), timeout=10.0)
        assert len(seen) == 50
    finally:
        await pool.stop()


class _FakeWS:
    def __init__(self, messages: list[str], fail: bool = False):
        self._messages = messages
        self._fail = fail

    async def __aenter__(self) -> _FakeWS:
        if self._fail:
            raise ConnectionRefusedError("refused")
        return self

    async def __aexit__(self, *args: Any) -> bool:
        return False

    def __aiter__(self) -> Any:
        async def gen() -> Any:
            for m in self._messages:
                yield m
            await asyncio.sleep(0.05)
            raise ConnectionResetError("server dropped")

        return gen()


async def test_consumer_reconnects_after_failure() -> None:
    q = IngestQueue(maxsize=50)
    frames = [json.dumps(_payload(event_id=f"r-{i}")) for i in range(3)]
    calls = {"n": 0}

    async def flaky(url: str) -> _FakeWS:
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeWS([], fail=True)
        return _FakeWS(frames)

    c = EventConsumer(q, url="ws://flaky", base_s=0.01, max_s=0.05, connect_fn=flaky)  # type: ignore[arg-type]
    task = asyncio.create_task(c.run())
    try:
        deadline = asyncio.get_event_loop().time() + 5.0
        while q.metrics.enqueued < 3 and asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(0.05)
        assert q.metrics.enqueued == 3
        assert c.status.reconnects >= 1
    finally:
        await c.stop()
        try:
            await asyncio.wait_for(task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            task.cancel()


async def test_multi_site_events_coexist() -> None:
    q = IngestQueue(maxsize=50)
    for site in ("site-100", "site-101", "site-102"):
        assert q.submit_dict(_payload(event_id=f"s-{site}", site_id=site)) == "enqueued"
    assert q.depth == 3
