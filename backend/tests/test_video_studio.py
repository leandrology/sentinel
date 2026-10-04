"""Video studio tests: uploads, vision providers, source switching, ingestion toggle."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.ingestion.queue import IngestQueue
from app.vision import uploads as upload_store
from app.vision.vision_provider import (
    DisabledVision,
    GeminiVision,
    MockVision,
    TwelveLabsVision,
    VisionError,
    build_vision_provider,
)
from app.vision.worker import VideoWorker

W, H = 320, 240


def _black() -> np.ndarray:
    return np.zeros((H, W, 3), dtype=np.uint8)


def _with_rect() -> np.ndarray:
    frame = _black()
    cv2.rectangle(frame, (100, 90), (160, 150), (255, 255, 255), -1)
    return frame


def _jpeg(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    return bytes(buf)


def test_validate_upload_rejects_bad_type() -> None:
    with pytest.raises(ValueError):
        upload_store.validate_upload("evil.exe", "application/x-msdownload", 100, 100)
    with pytest.raises(ValueError):
        upload_store.validate_upload("big.mp4", "video/mp4", 200 * 1024 * 1024, 100)


def test_validate_upload_accepts_mp4_webm() -> None:
    assert upload_store.validate_upload("clip.mp4", "video/mp4", 10, 100) == ".mp4"
    assert upload_store.validate_upload("clip.webm", "video/webm", 10, 100) == ".webm"


def test_save_list_resolve_roundtrip(tmp_path: Path) -> None:
    saved = upload_store.save_upload(b"fake-video-bytes", "demo.mp4", str(tmp_path))
    items = upload_store.list_uploads(str(tmp_path))
    assert len(items) == 1
    assert items[0]["id"] == saved["id"]
    resolved = upload_store.resolve_upload(str(tmp_path), str(saved["id"]))
    assert resolved is not None and resolved.name == saved["filename"]
    # Traversal ids never resolve outside the dir.
    assert upload_store.resolve_upload(str(tmp_path), "../../etc/passwd") is None


async def test_mock_vision_returns_hint() -> None:
    provider = MockVision()
    jpeg = _jpeg(_with_rect())
    result = await provider.analyze(jpeg, {"motion_score": 0.01})
    assert result.provider == "mock"
    assert result.severity_hint in ("info", "warning", "critical")
    hot = await provider.analyze(jpeg, {"motion_score": 0.2})
    assert hot.severity_hint == "warning"


async def test_disabled_vision_raises() -> None:
    with pytest.raises(VisionError):
        await DisabledVision().analyze(b"bytes", {})


def test_gemini_validates_json_body() -> None:
    provider = GeminiVision(api_key="test-key")
    raw = 'prefix {"label": "person", "severity_hint": "warning", '
    raw += '"description": "Person near fence.", "certainty": 0.8} suffix'
    result = provider._validate(raw)
    assert result.label == "person"
    assert result.severity_hint == "warning"
    assert result.provider == "gemini"


def test_gemini_clamps_bad_hint() -> None:
    provider = GeminiVision(api_key="test-key")
    result = provider._validate('{"label": "x", "severity_hint": "nope"}')
    assert result.severity_hint == "info"


def test_build_vision_provider_defaults_to_mock() -> None:
    class S:
        vision_provider = "gemini"  # no key configured
        vision_enabled = True
        google_ai_api_key = ""
        twelvelabs_api_key = ""

    assert isinstance(build_vision_provider(S()), MockVision)


def test_build_vision_provider_disabled() -> None:
    class S:
        vision_provider = "gemini"
        vision_enabled = False
        google_ai_api_key = "k"
        twelvelabs_api_key = ""

    assert isinstance(build_vision_provider(S()), DisabledVision)


async def test_worker_enriches_event_with_mock_vision() -> None:
    q = IngestQueue(maxsize=50)
    worker = VideoWorker(
        q,
        source="",
        cooldown_s=0.0,
        vision_provider=MockVision(),
        vision_cooldown_s=0.0,
    )
    frame = _with_rect()
    ok = await worker._handle_motion(frame, 0.2, [])
    assert ok is True
    evt = q._queue.get_nowait()
    assert evt.source == "camera"
    assert "vision" in evt.metadata
    assert evt.metadata["vision"]["provider"] == "mock"


async def test_worker_vision_failure_still_emits_motion() -> None:
    q = IngestQueue(maxsize=50)

    class Boom:
        name = "boom"

        async def analyze(self, jpeg_bytes: bytes, context: dict) -> object:
            raise VisionError("down", transient=True)

    worker = VideoWorker(
        q, source="", cooldown_s=0.0, vision_provider=Boom(), vision_cooldown_s=0.0
    )
    ok = await worker._handle_motion(_with_rect(), 0.1, [])
    assert ok is True
    evt = q._queue.get_nowait()
    assert evt.type == "motion_detected"
    assert "vision" not in evt.metadata


async def test_worker_set_source_updates_status() -> None:
    q = IngestQueue(maxsize=10)
    worker = VideoWorker(q, source="", cooldown_s=0.0)
    await worker.set_source("0")
    assert worker.source == "0"
    assert worker.status.source == "0"


async def test_browser_frame_no_motion_reports_reason() -> None:
    q = IngestQueue(maxsize=10)
    worker = VideoWorker(q, source="", cooldown_s=0.0, vision_provider=DisabledVision())
    jpeg = _jpeg(_black())
    # First frame establishes reference; second identical frame has no motion.
    await worker.ingest_browser_frame(jpeg)
    result = await worker.ingest_browser_frame(jpeg)
    assert result["emitted"] is False


def test_twelvelabs_requires_key() -> None:
    with pytest.raises(ValueError):
        TwelveLabsVision(api_key="")


def test_api_upload_sources_ingestion_vision(tmp_path: Path) -> None:
    import io

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    os.environ["INGEST_ENABLED"] = "false"
    os.environ["VIDEO_ENABLED"] = "false"
    os.environ["VIDEO_UPLOAD_DIR"] = str(tmp_path)
    os.environ["VISION_PROVIDER"] = "mock"
    try:
        with TestClient(create_app()) as client:
            # Upload a tiny mp4 (bytes need not decode; storage only).
            files = {"file": ("demo.mp4", io.BytesIO(b"0" * 1024), "video/mp4")}
            up = client.post("/api/video/upload", files=files)
            assert up.status_code == 201, up.text
            vid = up.json()["id"]

            sources = client.get("/api/video/sources").json()
            assert any(s["id"] == vid for s in sources["items"])

            served = client.get(f"/api/video/file/{vid}")
            assert served.status_code == 200

            bad = client.post("/api/video/source", json={"source": "nope-missing"})
            assert bad.json().get("error")

            ok = client.post("/api/video/source", json={"source": vid})
            assert ok.status_code == 200

            vision = client.get("/api/vision/status").json()
            assert vision["provider"] == "mock"

            stopped = client.post("/api/ingestion/stop").json()
            assert stopped["enabled"] is False
            started = client.post("/api/ingestion/start").json()
            assert "queue_size" in started

            status = client.get("/api/video/status").json()
            assert "vision_provider" in status

            bad_upload = client.post(
                "/api/video/upload",
                files={"file": ("evil.exe", io.BytesIO(b"x"), "application/x-msdownload")},
            )
            assert bad_upload.status_code == 400

            empty_frame = client.post("/api/video/frames", json={"image_b64": ""}).json()
            assert empty_frame["emitted"] is False
    finally:
        for k in ("INGEST_ENABLED", "VIDEO_ENABLED", "VIDEO_UPLOAD_DIR", "VISION_PROVIDER"):
            os.environ.pop(k, None)
        get_settings.cache_clear()


def test_api_browser_frame_invalid_base64() -> None:
    import os

    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app

    get_settings.cache_clear()
    os.environ["INGEST_ENABLED"] = "false"
    os.environ["VIDEO_ENABLED"] = "false"
    try:
        with TestClient(create_app()) as client:
            res = client.post("/api/video/frames", json={"image_b64": "!!!not-base64"}).json()
            assert res["emitted"] is False
            # Raw bytes that are not a JPEG decode-fail gracefully.
            raw = base64.b64encode(b"not-an-image").decode()
            res2 = client.post("/api/video/frames", json={"image_b64": raw}).json()
            assert res2["emitted"] is False
    finally:
        os.environ.pop("INGEST_ENABLED", None)
        os.environ.pop("VIDEO_ENABLED", None)
        get_settings.cache_clear()
