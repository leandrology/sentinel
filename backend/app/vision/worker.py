"""Background video worker. Samples frames off the request/ingest hot path.

Runs as its own asyncio task: blocking capture I/O goes through
``asyncio.to_thread`` so the event loop (and WS reader) never stalls.
Detections are published via ``IngestQueue.submit_event`` — the exact same
interface sensor events use, so camera and sensor events share triage,
persistence, and broadcast downstream.

Extensions: runtime ``set_source`` (dashboard upload / webcam switch),
last-frame snapshot buffers for MJPEG preview, motion-gated vision-LLM
enrichment (Gemini / TwelveLabs via VisionProvider), and browser-webcam
frame ingest.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import cv2
import numpy as np

from app.ingestion.queue import IngestQueue
from app.vision.motion import MotionDetector, confidence_for_score

log = logging.getLogger(__name__)


@dataclass
class VideoStatus:
    running: bool = False
    source: str = ""
    frames_read: int = 0
    detections: int = 0
    last_error: str | None = None
    vision_provider: str = "mock"
    vision_analyzed: int = 0
    vision_failed: int = 0
    last_vision: dict[str, object] | None = None


@dataclass
class VisionInfo:
    provider: str = "mock"
    analyzed: int = 0
    failed: int = 0
    last: dict[str, object] | None = None


def parse_source(source: str) -> int | str:
    """Numeric strings address webcams (``"0"``); otherwise a file path."""
    return int(source) if source.strip().isdigit() else source


def _open_capture(target: int | str) -> cv2.VideoCapture:
    return cv2.VideoCapture(target)


def _encode_jpeg(frame: Any, max_width: int = 640) -> bytes | None:
    try:
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            frame = cv2.resize(frame, (max_width, int(h * scale)))
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return bytes(buf) if ok else None
    except Exception:
        return None


def _annotate(frame: Any, boxes: list[Any]) -> Any:
    try:
        out = frame.copy()
        for b in boxes:
            x, y, w, h = int(b.x), int(b.y), int(b.w), int(b.h)
            cv2.rectangle(out, (x, y), (x + w, y + h), (0, 255, 0), 2)
        return out
    except Exception:
        return frame


def _source_fps_or_fallback(cap: cv2.VideoCapture, is_file: bool, fallback: float) -> float:
    """Read CAP_PROP_FPS; files fall back to 30, live falls back to preview rate."""
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS))
    except Exception:
        fps = 0.0
    if 1.0 <= fps <= 120.0:
        return fps
    if fallback and 1.0 <= fallback <= 120.0:
        return fallback
    return 30.0 if is_file else 15.0


def _skip_frames(cap: cv2.VideoCapture, n: int) -> int:
    """Advance a file capture by n frames without decoding (grab only)."""
    skipped = 0
    for _ in range(max(0, n)):
        try:
            if not cap.grab():
                break
            skipped += 1
        except Exception:
            break
    return skipped


def _render_previews(frame: Any, boxes: list[Any]) -> tuple[bytes | None, bytes | None]:
    """Encode raw + annotated JPEGs. Runs in a worker thread (CPU-bound)."""
    raw = _encode_jpeg(frame)
    annotated = _encode_jpeg(_annotate(frame, boxes))
    return raw, annotated


_VISION_LABEL_TO_TYPE = {
    "person": "object_detected",
    "vehicle": "object_detected",
    "animal": "object_detected",
    "package": "object_detected",
    "other": "motion_detected",
    "motion": "motion_detected",
}


class VideoWorker:
    def __init__(
        self,
        queue: IngestQueue,
        source: str,
        sample_fps: float = 2.0,
        threshold: float = 25.0,
        min_area: float = 500.0,
        site_id: str = "site-100",
        zone: str = "north-perimeter",
        loop_files: bool = True,
        cooldown_s: float = 5.0,
        vision_provider: Any | None = None,
        vision_cooldown_s: float = 10.0,
        preview_fps: float = 15.0,
        file_realtime: bool = True,
    ) -> None:
        self.queue = queue
        self.source = source
        self.sample_fps = max(0.1, sample_fps)
        self.preview_fps = min(30.0, max(1.0, preview_fps))
        self.file_realtime = file_realtime
        self.site_id = site_id
        self.zone = zone
        self.loop_files = loop_files
        self.cooldown_s = max(0.0, cooldown_s)
        self.detector = MotionDetector(threshold=threshold, min_area=min_area)
        self.vision = vision_provider
        self.vision_cooldown_s = max(0.0, vision_cooldown_s)
        self.vision_info = VisionInfo(provider=getattr(vision_provider, "name", "mock"))
        self.status = VideoStatus(source=source, vision_provider=self.vision_info.provider)
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self._restart = False
        self._last_emit = 0.0
        self._last_vision = 0.0
        self._frame_index = 0
        self._last_jpeg: bytes | None = None
        self._last_annotated: bytes | None = None
        self._last_boxes: list[Any] = []
        self._preview_seq = 0
        self._source_fps = 0.0
        self._skipped_total = 0
        self._loops = 0

    @property
    def running(self) -> bool:
        return self._running

    def set_vision_provider(self, provider: Any | None) -> None:
        self.vision = provider
        name = getattr(provider, "name", "mock")
        self.vision_info.provider = name
        self.status.vision_provider = name

    async def set_source(self, source: str) -> None:
        """Switch input at runtime. Restarts the read loop without dropping queue."""
        self.source = source
        self.status.source = source
        self.status.last_error = None
        self.detector.reset()
        if self._running:
            self._restart = True
            # Break out of blocking read by stopping task; start() will relaunch.
            await self.stop()
            self.start()

    def start(self) -> asyncio.Task[None]:
        if self._task is None or self._task.done():
            self._running = True
            self._restart = False
            self._task = asyncio.create_task(self._run(), name="video-worker")
        return self._task

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.status.running = False

    async def _run(self) -> None:
        if not self.source:
            self.status.last_error = "no video source configured"
            self._running = False
            return
        self.status.running = True
        target = parse_source(self.source)
        is_file = isinstance(target, str)
        while self._running:
            cap = await asyncio.to_thread(_open_capture, target)
            try:
                if not await asyncio.to_thread(cap.isOpened):
                    self.status.last_error = f"cannot open video source: {self.source}"
                    log.warning("video source unavailable: %s", self.source)
                    await self._sleep_or_cancel(5.0)
                    continue
                # Reduce live-camera latency: drop buffered frames.
                if not is_file:
                    try:
                        await asyncio.to_thread(cap.set, cv2.CAP_PROP_BUFFERSIZE, 1)
                    except Exception:
                        pass
                source_fps = await asyncio.to_thread(
                    _source_fps_or_fallback, cap, is_file, self.preview_fps
                )
                self._source_fps = source_fps
                self.status.last_error = None
                log.info(
                    "video worker reading: %s (src_fps=%.1f sample=%.1f preview=%.1f)",
                    self.source,
                    source_fps,
                    self.sample_fps,
                    self.preview_fps,
                )
                # Display runs fast (preview_fps); detection stays sampled.
                # File sources are paced to wall-clock so the processed feed
                # cannot play in slow motion behind the raw <video> preview.
                loop_hz = max(self.sample_fps, self.preview_fps)
                base_interval = 1.0 / max(0.1, loop_hz)
                if is_file and self.file_realtime:
                    base_interval = max(base_interval, 1.0 / max(1.0, source_fps))
                loop_t0 = time.monotonic()
                consumed = 0
                next_detect = 0.0
                while self._running:
                    loop_started = time.perf_counter()
                    if is_file and self.file_realtime:
                        wall = time.monotonic() - loop_t0
                        expected = int(wall * source_fps)
                        lag = expected - consumed
                        if lag > 1:
                            to_skip = min(lag - 1, int(source_fps * 2))
                            if to_skip > 0:
                                skipped = await asyncio.to_thread(_skip_frames, cap, to_skip)
                                consumed += skipped
                                self._skipped_total += skipped
                    ok, frame = await asyncio.to_thread(cap.read)
                    if not ok or frame is None:
                        break  # EOF or disconnect; outer loop reopens/errors
                    self.status.frames_read += 1
                    self._frame_index += 1
                    consumed += 1
                    now_m = time.monotonic()
                    if now_m >= next_detect:
                        next_detect = now_m + 1.0 / self.sample_fps
                        result = await asyncio.to_thread(self.detector.detect, frame)
                        boxes = result.boxes
                        raw_jpeg, annotated_jpeg = await asyncio.to_thread(
                            _render_previews, frame, boxes
                        )
                        self._publish_preview(raw_jpeg, annotated_jpeg, boxes)
                        if result.motion:
                            await self._handle_motion(frame, result.score, boxes)
                    else:
                        # Preview-only frame: reuse last boxes, keep detector
                        # sampled so motion sensitivity is unchanged.
                        boxes = self._last_boxes
                        raw_jpeg, annotated_jpeg = await asyncio.to_thread(
                            _render_previews, frame, boxes
                        )
                        self._publish_preview(raw_jpeg, annotated_jpeg, boxes)
                    elapsed = time.perf_counter() - loop_started
                    await self._sleep_or_cancel(max(0.0, base_interval - elapsed))
                if not self._running:
                    break
                if self._restart:
                    self._restart = False
                    self._running = True
                    target = parse_source(self.source)
                    is_file = isinstance(target, str)
                    continue
                if is_file and self.loop_files:
                    self._loops += 1
                    continue  # replay file for continuous monitoring
                if not is_file:
                    self.status.last_error = "video stream disconnected"
                    await self._sleep_or_cancel(5.0)
                    continue
                break  # file EOF with loop disabled
            finally:
                await asyncio.to_thread(cap.release)
        self.status.running = False

    async def _sleep_or_cancel(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise

    def _store_preview(self, frame: Any, boxes: list[Any]) -> None:
        try:
            jpeg = _encode_jpeg(frame)
            if jpeg:
                self._last_jpeg = jpeg
            annotated = _encode_jpeg(_annotate(frame, boxes))
            if annotated:
                self._last_annotated = annotated
            self._last_boxes = boxes
            self._preview_seq += 1
        except Exception:
            pass

    def _publish_preview(
        self, raw: bytes | None, annotated: bytes | None, boxes: list[Any]
    ) -> None:
        try:
            if raw:
                self._last_jpeg = raw
            if annotated:
                self._last_annotated = annotated
            self._last_boxes = boxes
            self._preview_seq += 1
        except Exception:
            pass

    def last_snapshot(self, annotated: bool = True) -> bytes | None:
        return self._last_annotated if annotated else self._last_jpeg

    def snapshot_with_seq(self, annotated: bool = True) -> tuple[int, bytes | None]:
        """Sequence + JPEG for MJPEG dedup (no resend of identical frame)."""
        return self._preview_seq, self.last_snapshot(annotated=annotated)

    async def ingest_browser_frame(
        self, jpeg_bytes: bytes, site_id: str | None = None, zone: str | None = None
    ) -> dict[str, object]:
        """Accept one browser-webcam JPEG, run motion gate + vision, maybe emit."""
        try:
            arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
            frame = await asyncio.to_thread(cv2.imdecode, arr, cv2.IMREAD_COLOR)
        except Exception:
            return {"emitted": False, "reason": "decode failed"}
        if frame is None:
            return {"emitted": False, "reason": "decode failed"}
        self.status.frames_read += 1
        self._frame_index += 1
        result = self.detector.detect(frame)
        self._store_preview(frame, result.boxes)
        if not result.motion:
            return {"emitted": False, "reason": "no motion"}
        emitted = await self._handle_motion(
            frame,
            result.score,
            result.boxes,
            site_id=site_id or self.site_id,
            zone=zone or self.zone,
        )
        return {"emitted": emitted, "motion_score": round(result.score, 4)}

    async def _handle_motion(
        self,
        frame: Any,
        score: float,
        boxes: list[Any],
        site_id: str | None = None,
        zone: str | None = None,
    ) -> bool:
        now = time.monotonic()
        if now - self._last_emit < self.cooldown_s:
            return False
        self._last_emit = now
        vision_data: dict[str, object] | None = await self._maybe_vision(frame, score)
        event_type = "motion_detected"
        if vision_data:
            label = str(vision_data.get("label", "motion"))
            event_type = _VISION_LABEL_TO_TYPE.get(label, "motion_detected")
            # Suspicious vision hint upgrades motion to loitering for correlation.
            hint = vision_data.get("severity_hint")
            if hint in ("warning", "critical") and event_type == "motion_detected":
                event_type = "loitering"
        from app.domain.schemas import NormalizedEvent

        event = NormalizedEvent(
            event_id="cam_" + uuid.uuid4().hex[:10],
            site_id=site_id or self.site_id,
            zone=zone or self.zone,
            type=event_type,  # type: ignore[arg-type]
            source="camera",
            confidence=confidence_for_score(score),
            timestamp=datetime.now(UTC),
            snapshot_url=None,
            metadata={
                "detector": "frame-diff",
                "motion_score": round(score, 4),
                "boxes": [{"x": b.x, "y": b.y, "w": b.w, "h": b.h} for b in boxes],
                "frame_index": self._frame_index,
                **({"vision": vision_data} if vision_data else {}),
            },
        )
        outcome = self.queue.submit_event(event)
        if outcome in ("enqueued", "critical-evicted"):
            self.status.detections += 1
            return True
        return False

    async def _maybe_vision(self, frame: Any, score: float) -> dict[str, object] | None:
        provider = self.vision
        if provider is None or getattr(provider, "name", "") == "disabled":
            return None
        now = time.monotonic()
        if now - self._last_vision < self.vision_cooldown_s:
            return None
        self._last_vision = now
        try:
            jpeg = await asyncio.to_thread(_encode_jpeg, frame)
        except Exception:
            return None
        if not jpeg:
            return None
        try:
            result = await provider.analyze(
                jpeg, {"site_id": self.site_id, "zone": self.zone, "motion_score": score}
            )
        except Exception as exc:
            self.vision_info.failed += 1
            self.status.vision_failed = self.vision_info.failed
            log.warning("vision %s failed: %s", getattr(provider, "name", "?"), type(exc).__name__)
            return None
        self.vision_info.analyzed += 1
        self.status.vision_analyzed = self.vision_info.analyzed
        payload: dict[str, object] = {
            "label": result.label,
            "severity_hint": result.severity_hint,
            "description": result.description,
            "certainty": result.certainty,
            "provider": result.provider,
            "model": result.model,
        }
        self.vision_info.last = payload
        self.status.last_vision = payload
        return payload

    # Back-compat sync entry used by older tests/callers.
    def _maybe_emit(self, score: float, boxes: list[Any]) -> None:
        now = time.monotonic()
        if now - self._last_emit < self.cooldown_s:
            return
        self._last_emit = now
        from app.domain.schemas import NormalizedEvent

        event = NormalizedEvent(
            event_id="cam_" + uuid.uuid4().hex[:10],
            site_id=self.site_id,
            zone=self.zone,
            type="motion_detected",
            source="camera",
            confidence=confidence_for_score(score),
            timestamp=datetime.now(UTC),
            snapshot_url=None,
            metadata={
                "detector": "frame-diff",
                "motion_score": round(score, 4),
                "boxes": [{"x": b.x, "y": b.y, "w": b.w, "h": b.h} for b in boxes],
                "frame_index": self._frame_index,
            },
        )
        outcome = self.queue.submit_event(event)
        if outcome in ("enqueued", "critical-evicted"):
            self.status.detections += 1
