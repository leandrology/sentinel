import asyncio
import base64
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.persistence import repo
from app.realtime.sse import incident_stream
from app.vision import uploads as upload_store

router = APIRouter()


class OperatorAction(BaseModel):
    actor: str = "operator"


class VideoSourceSelect(BaseModel):
    source: str = ""


class BrowserFrame(BaseModel):
    image_b64: str = ""
    site_id: str | None = None
    zone: str | None = None


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _snapshot(request: Request) -> dict[str, object]:
    settings = get_settings()
    queue = getattr(request.app.state, "ingest_queue", None)
    consumer = getattr(request.app.state, "consumer", None)
    pool = getattr(request.app.state, "worker_pool", None)
    if queue is None:
        return {
            "connected": False,
            "queue_size": 0,
            "queue_max": settings.ingest_queue_size,
            "dropped": 0,
        }
    m = queue.metrics
    return {
        "connected": bool(consumer and consumer.status.connected),
        "enabled": bool(consumer and getattr(consumer, "_running", False)),
        "reconnects": consumer.status.reconnects if consumer else 0,
        "last_error": consumer.status.last_error if consumer else None,
        "queue_size": queue.depth,
        "queue_max": settings.ingest_queue_size,
        "workers": pool.num_workers if pool else settings.ingest_workers,
        "enqueued": m.enqueued,
        "processed": m.processed,
        "failed": m.failed,
        "dropped": m.dropped_noncritical,
        "evicted": m.evicted,
        "duplicates": m.duplicates,
        "malformed": m.malformed,
        "high_water_mark": m.high_water_mark,
    }


@router.get("/ingestion/status")
def ingestion_status(request: Request) -> dict[str, object]:
    return _snapshot(request)


@router.post("/ingestion/start")
async def ingestion_start(request: Request) -> dict[str, object]:
    consumer = getattr(request.app.state, "consumer", None)
    if consumer is None:
        return {"enabled": False, "error": "no consumer"}
    consumer.start()
    return _snapshot(request)


@router.post("/ingestion/stop")
async def ingestion_stop(request: Request) -> dict[str, object]:
    consumer = getattr(request.app.state, "consumer", None)
    if consumer is None:
        return {"enabled": False, "error": "no consumer"}
    await consumer.stop()
    data = _snapshot(request)
    data["enabled"] = False
    data["connected"] = False
    return data


@router.get("/metrics")
def metrics(request: Request) -> dict[str, object]:
    data = _snapshot(request)
    store = getattr(request.app.state, "triage_store", None)
    provider = getattr(request.app.state, "triage_provider", None)
    if store is not None:
        data["triaged"] = store.triaged_total
        data["fallback"] = store.fallback_total
    if provider is not None:
        data["triage_provider"] = provider.name
    vision = getattr(request.app.state, "vision_provider", None)
    if vision is not None:
        data["vision_provider"] = vision.name
    hub = getattr(request.app.state, "hub", None)
    if hub is not None:
        data["sse_subscribers"] = hub.subscribers
        data["sse_dropped"] = hub.dropped
    return data


@router.get("/triage/recent")
def triage_recent(request: Request, limit: int = 20) -> dict[str, object]:
    store = getattr(request.app.state, "triage_store", None)
    if store is None:
        return {"items": []}
    items = [
        {
            "event_id": r.event.event_id,
            "site_id": r.event.site_id,
            "zone": r.event.zone,
            "type": r.event.type,
            "source": r.event.source,
            "timestamp": r.event.timestamp.isoformat(),
            "severity": r.triage.severity,
            "threat_assessment": r.triage.threat_assessment,
            "summary": r.triage.summary,
            "recommended_action": r.triage.recommended_action,
            "certainty": r.triage.certainty,
            "provider": r.triage.provider,
            "fallback": r.triage.fallback,
        }
        for r in store.recent(limit=min(max(1, limit), 100))
    ]
    return {"items": items}


def _video_status(request: Request) -> dict[str, object]:
    worker = getattr(request.app.state, "video_worker", None)
    if worker is None:
        return {"running": False, "source": "", "error": "no worker"}
    s = worker.status
    return {
        "running": s.running,
        "source": s.source,
        "frames_read": s.frames_read,
        "detections": s.detections,
        "last_error": s.last_error,
        "vision_provider": s.vision_provider,
        "vision_analyzed": s.vision_analyzed,
        "vision_failed": s.vision_failed,
        "last_vision": s.last_vision,
        "preview_fps": getattr(worker, "preview_fps", None),
        "sample_fps": getattr(worker, "sample_fps", None),
        "source_fps": getattr(worker, "_source_fps", None),
        "preview_seq": getattr(worker, "_preview_seq", 0),
        "skipped": getattr(worker, "_skipped_total", 0),
        "loops": getattr(worker, "_loops", 0),
    }


@router.get("/video/status")
def video_status(request: Request) -> dict[str, object]:
    return _video_status(request)


@router.post("/video/start")
async def video_start(request: Request) -> dict[str, object]:
    worker = getattr(request.app.state, "video_worker", None)
    if worker is None:
        return {"running": False, "error": "no worker"}
    if not worker.source:
        return {"running": False, "error": "no video source configured"}
    worker.start()
    return _video_status(request)


@router.post("/video/stop")
async def video_stop(request: Request) -> dict[str, object]:
    worker = getattr(request.app.state, "video_worker", None)
    if worker is None:
        return {"running": False, "error": "no worker"}
    await worker.stop()
    return _video_status(request)


@router.get("/vision/status")
def vision_status(request: Request) -> dict[str, object]:
    provider = getattr(request.app.state, "vision_provider", None)
    worker = getattr(request.app.state, "video_worker", None)
    settings = get_settings()
    return {
        "provider": getattr(provider, "name", "mock"),
        "configured": settings.vision_provider,
        "enabled": settings.vision_enabled,
        "analyzed": worker.status.vision_analyzed if worker else 0,
        "failed": worker.status.vision_failed if worker else 0,
        "last": worker.status.last_vision if worker else None,
    }


@router.post("/video/upload")
async def video_upload(request: Request, file: UploadFile) -> JSONResponse:
    settings = get_settings()
    data = await file.read()
    try:
        upload_store.validate_upload(
            file.filename, file.content_type, len(data), settings.video_max_mb
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    saved = upload_store.save_upload(data, file.filename or "upload.mp4", settings.video_upload_dir)
    return JSONResponse(status_code=201, content=saved)


@router.get("/video/sources")
def video_sources() -> dict[str, object]:
    settings = get_settings()
    return {"items": upload_store.list_uploads(settings.video_upload_dir)}


@router.post("/video/source")
async def video_set_source(request: Request, body: VideoSourceSelect) -> dict[str, object]:
    worker = getattr(request.app.state, "video_worker", None)
    if worker is None:
        return {"running": False, "error": "no worker"}
    source = (body.source or "").strip()
    if not source:
        return {"running": False, "error": "empty source"}
    # Allow upload ids ("<hex>") as shorthand for stored files.
    settings = get_settings()
    resolved = upload_store.resolve_upload(settings.video_upload_dir, source)
    target = str(resolved) if resolved is not None else source
    # Confine arbitrary paths: only allow upload dir, existing files, or webcam index.
    if target != source and resolved is None:
        return {"running": False, "error": "unknown upload id"}
    if target.strip().isdigit():
        pass
    elif resolved is None:
        p = Path(target)
        if not p.exists() or not p.is_file():
            return {"running": False, "error": f"file not found: {source}"}
    await worker.set_source(target)
    worker.start()
    return _video_status(request)


@router.get("/video/file/{video_id}", response_model=None)
def video_file(video_id: str):
    settings = get_settings()
    resolved = upload_store.resolve_upload(settings.video_upload_dir, video_id)
    if resolved is None:
        return JSONResponse(status_code=404, content={"error": "video not found"})
    suffix = resolved.suffix.lower()
    media = "video/mp4" if suffix == ".mp4" else "video/webm" if suffix == ".webm" else "video/mp4"
    return FileResponse(str(resolved), media_type=media, filename=resolved.name)


@router.get("/video/snapshot.jpg", response_model=None)
def video_snapshot(request: Request, annotated: bool = True):
    worker = getattr(request.app.state, "video_worker", None)
    if worker is None:
        return JSONResponse(status_code=503, content={"error": "no worker"})
    jpeg = worker.last_snapshot(annotated=annotated)
    if jpeg is None:
        return JSONResponse(status_code=404, content={"error": "no frame yet"})
    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/video/stream.mjpeg")
async def video_stream(request: Request) -> StreamingResponse:
    worker = getattr(request.app.state, "video_worker", None)

    async def gen():  # type: ignore[no-untyped-def]
        boundary = "sentinelframe"
        # Preview-paced MJPEG: yields only new frames (~preview_fps),
        # so file sources stay near realtime instead of resending stale JPEGs.
        last_seq = -1
        idle = 0
        while True:
            if await request.is_disconnected():
                break
            seq_jpeg = worker.snapshot_with_seq(annotated=True) if worker else (-1, None)
            seq, jpeg = seq_jpeg[0], seq_jpeg[1]
            if jpeg is None:
                await asyncio.sleep(0.25)
                continue
            if seq == last_seq:
                # No new frame yet; poll fast to keep latency low.
                idle += 1
                await asyncio.sleep(0.03)
                # Send keep-alive duplicate at most every ~2s so browsers
                # don't stall if the source pauses (e.g. EOF reopen).
                if idle < 60:
                    continue
                idle = 0
            else:
                idle = 0
            last_seq = seq
            yield (
                f"--{boundary}\r\nContent-Type: image/jpeg\r\n"
                f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                + jpeg
                + b"\r\n"
            )

    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=sentinelframe",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/video/frames")
async def video_browser_frame(request: Request, body: BrowserFrame) -> dict[str, object]:
    worker = getattr(request.app.state, "video_worker", None)
    if worker is None:
        return {"emitted": False, "error": "no worker"}
    if not body.image_b64:
        return {"emitted": False, "error": "empty frame"}
    try:
        raw = base64.b64decode(body.image_b64.split(",", 1)[-1])
    except Exception:
        return {"emitted": False, "error": "invalid base64"}
    if len(raw) > 2 * 1024 * 1024:
        return {"emitted": False, "error": "frame too large (2 MB limit)"}
    return await worker.ingest_browser_frame(raw, site_id=body.site_id, zone=body.zone)


def _db(request: Request):  # type: ignore[no-untyped-def]
    factory = getattr(request.app.state, "db_session", None)
    if factory is None:
        from app.persistence.db import get_session_factory

        factory = get_session_factory()
    return factory


@router.get("/incidents")
def list_incidents(
    request: Request,
    status: str | None = None,
    site_id: str | None = None,
    zone: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    with _db(request)() as session:
        items = repo.list_incidents(
            session,
            status=status,
            site_id=site_id,
            zone=zone,
            severity=severity,
            limit=min(max(1, limit), 200),
            offset=max(0, offset),
        )
    return {"items": items}


@router.get("/incidents/{incident_id}")
def get_incident(request: Request, incident_id: int):  # type: ignore[no-untyped-def]
    with _db(request)() as session:
        item = repo.get_detail(session, incident_id)
    if item is None:
        return JSONResponse(status_code=404, content={"error": "incident not found"})
    return item


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge_incident(request: Request, incident_id: int, action: OperatorAction):  # type: ignore[no-untyped-def]
    try:
        with _db(request)() as session:
            item, changed = repo.acknowledge(session, incident_id, actor=action.actor)
    except KeyError:
        return JSONResponse(status_code=404, content={"error": "incident not found"})
    except repo.InvalidTransition as exc:
        return JSONResponse(status_code=409, content={"error": str(exc)})
    return {"incident": item, "changed": changed}


@router.post("/incidents/{incident_id}/resolve")
def resolve_incident(request: Request, incident_id: int, action: OperatorAction):  # type: ignore[no-untyped-def]
    try:
        with _db(request)() as session:
            item, changed = repo.resolve(session, incident_id, actor=action.actor)
    except KeyError:
        return JSONResponse(status_code=404, content={"error": "incident not found"})
    except repo.InvalidTransition as exc:
        return JSONResponse(status_code=409, content={"error": str(exc)})
    return {"incident": item, "changed": changed}


@router.get("/events/stream")
async def events_stream(request: Request) -> StreamingResponse:
    hub = request.app.state.hub
    heartbeat = getattr(request.app.state, "sse_heartbeat_s", 15.0)
    gen = incident_stream(hub, _db(request), heartbeat_s=heartbeat)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
