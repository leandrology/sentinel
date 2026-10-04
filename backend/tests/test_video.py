"""M4 video tests. Synthetic frames/video only; no webcam required."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ingestion.queue import IngestQueue
from app.processing.pipeline import WorkerPool
from app.providers.mock import MockProvider
from app.triage.service import TriageService
from app.triage.store import TriageStore
from app.vision.motion import MotionDetector, confidence_for_score
from app.vision.worker import VideoWorker, parse_source

W, H = 320, 240


def _black() -> np.ndarray:
    return np.zeros((H, W, 3), dtype=np.uint8)


def _with_rect(x: int = 100) -> np.ndarray:
    frame = _black()
    cv2.rectangle(frame, (x, 90), (x + 60, 150), (255, 255, 255), -1)
    return frame


def _video_file(path: Path, frames: int = 30) -> str:
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (W, H))
    for i in range(frames):
        if 10 <= i < 20:
            out.write(_with_rect(x=40 + i * 6))
        else:
            out.write(_black())
    out.release()
    return str(path)


def test_parse_source() -> None:
    assert parse_source("0") == 0
    assert parse_source(" 2 ") == 2
    assert parse_source("/videos/cam.mp4") == "/videos/cam.mp4"


def test_detector_ignores_first_frame_and_static() -> None:
    d = MotionDetector()
    assert d.detect(_black()).motion is False  # reference frame
    assert d.detect(_black()).motion is False  # identical


def test_detector_finds_motion_with_boxes() -> None:
    d = MotionDetector(min_area=500.0)
    d.detect(_black())
    result = d.detect(_with_rect())
    assert result.motion is True
    assert result.boxes, "expected bounding boxes"
    assert 0.0 < result.score <= 1.0


def test_detector_filters_small_noise() -> None:
    d = MotionDetector(min_area=500.0)
    d.detect(_black())
    noisy = _black()
    noisy[10, 10] = [255, 255, 255]  # single-pixel flicker
    assert d.detect(noisy).motion is False


def test_detector_high_min_area_rejects_rect() -> None:
    d = MotionDetector(min_area=1_000_000.0)
    d.detect(_black())
    assert d.detect(_with_rect()).motion is False


def test_confidence_bounds() -> None:
    assert confidence_for_score(0.0) == 0.35
    assert 0.35 <= confidence_for_score(0.05) <= 0.95
    assert confidence_for_score(10.0) == 0.95


async def test_worker_emits_camera_event_from_file(tmp_path: Path) -> None:
    src = _video_file(tmp_path / "motion.mp4")
    q = IngestQueue(maxsize=50)
    worker = VideoWorker(q, source=src, sample_fps=20.0, cooldown_s=0.0)
    worker.start()
    try:
        deadline = time.monotonic() + 15.0
        while q.metrics.enqueued == 0 and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        assert q.metrics.enqueued >= 1, "no camera event generated"
    finally:
        await worker.stop()
    assert worker.running is False
    assert worker.status.frames_read > 0
    assert worker.status.detections >= 1
    evt = q._queue.get_nowait()
    assert evt.source == "camera"
    assert evt.type == "motion_detected"
    assert 0.0 <= evt.confidence <= 1.0
    assert evt.timestamp.tzinfo is not None
    assert evt.metadata["detector"] == "frame-diff"
    assert evt.metadata["boxes"], "expected detection boxes"


async def test_worker_missing_source_is_graceful() -> None:
    q = IngestQueue(maxsize=10)
    worker = VideoWorker(q, source="/nonexistent/nope.mp4", sample_fps=10.0)
    worker.start()
    await asyncio.sleep(1.0)
    try:
        assert q.metrics.enqueued == 0
        assert worker.status.last_error is not None
    finally:
        await worker.stop()
    assert worker.running is False


async def test_worker_empty_source_stays_stopped() -> None:
    q = IngestQueue(maxsize=10)
    worker = VideoWorker(q, source="")
    worker.start()
    await asyncio.sleep(0.2)
    assert worker.running is False
    assert worker.status.last_error is not None
    await worker.stop()


async def test_camera_event_uses_same_pipeline(tmp_path: Path) -> None:
    """Camera detection -> queue -> triage workers -> store, like sensors."""
    src = _video_file(tmp_path / "pipe.mp4")
    q = IngestQueue(maxsize=50)
    service = TriageService(MockProvider())
    store = TriageStore(maxlen=50)
    pool = WorkerPool(q, num_workers=2, process_fn=lambda e: _record(store, service, e))
    video = VideoWorker(q, source=src, sample_fps=20.0, cooldown_s=0.0)
    pool.start()
    video.start()
    try:
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            await asyncio.sleep(0.2)
            if any(r.event.source == "camera" for r in store.recent(10)):
                break
        cams = [r for r in store.recent(10) if r.event.source == "camera"]
        assert cams, "no camera event reached the triage store"
        assert cams[0].triage.provider == "mock"
        assert cams[0].triage.severity in ("info", "warning", "critical")
    finally:
        await video.stop()
        await pool.stop()


async def _record(store: TriageStore, service: TriageService, event) -> None:  # type: ignore[no-untyped-def]
    store.add(event, await service.triage_event(event))


async def test_video_start_stop_api() -> None:
    import os

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    os.environ["INGEST_ENABLED"] = "false"
    os.environ["VIDEO_ENABLED"] = "false"
    try:
        with TestClient(create_app()) as client:
            status = client.get("/api/video/status").json()
            assert status["running"] is False
            denied = client.post("/api/video/start").json()
            assert denied["running"] is False  # no source configured
    finally:
        os.environ.pop("INGEST_ENABLED", None)
        os.environ.pop("VIDEO_ENABLED", None)
        get_settings.cache_clear()


@pytest.mark.skipif(True, reason="needs webcam hardware; run manually with VIDEO_SOURCE=0")
async def test_webcam_manual() -> None:  # pragma: no cover
    q = IngestQueue(maxsize=10)
    worker = VideoWorker(q, source="0", sample_fps=2.0)
    worker.start()
    await asyncio.sleep(5)
    await worker.stop()
