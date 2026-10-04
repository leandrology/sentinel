from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.schemas import NormalizedEvent, TriageResult
from app.ingestion.consumer import EventConsumer
from app.ingestion.queue import IngestQueue
from app.persistence import repo
from app.persistence.db import init_db
from app.processing.pipeline import WorkerPool
from app.providers.deepseek import DeepSeekProvider
from app.providers.gemini import GeminiProvider
from app.providers.mock import MockProvider
from app.realtime.hub import Hub
from app.triage.service import TriageService
from app.triage.store import TriageStore
from app.vision.vision_provider import build_vision_provider
from app.vision.worker import VideoWorker


def build_provider(settings) -> MockProvider | GeminiProvider | DeepSeekProvider:  # type: ignore[no-untyped-def]
    if settings.ai_provider == "gemini" and settings.google_ai_api_key:
        return GeminiProvider(
            api_key=settings.google_ai_api_key,
            model=settings.google_ai_model,
            base_url=settings.google_ai_base_url,
            timeout_s=settings.ai_timeout_s,
            max_retries=settings.ai_max_retries,
            max_concurrent=settings.ai_max_concurrent,
        )
    if settings.ai_provider == "deepseek" and settings.deepseek_api_key:
        return DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            timeout_s=settings.ai_timeout_s,
            max_retries=settings.ai_max_retries,
            max_concurrent=settings.ai_max_concurrent,
        )
    return MockProvider()


def build_event_handler(service, store, session_factory, hub, corr_window_s=300, corr_threshold=3):  # type: ignore[no-untyped-def]
    """Worker path: triage -> persist -> correlate -> broadcast. Importable."""

    async def handle(event: NormalizedEvent) -> None:
        import asyncio as _asyncio
        import logging as _logging

        result: TriageResult = await service.triage_event(event)
        store.add(event, result)
        try:
            record, escalation = await _asyncio.to_thread(
                _persist_and_correlate,
                session_factory,
                event,
                result,
                corr_window_s,
                corr_threshold,
            )
        except Exception:
            _logging.getLogger(__name__).exception("persist failed for %s", event.event_id)
            return
        hub.publish("incident", record)
        if escalation is not None:
            hub.publish("escalation", escalation)

    return handle


def _persist_and_correlate(session_factory, event, result, window_s, threshold):  # type: ignore[no-untyped-def]
    from app.alerts import rules

    with session_factory() as session:
        record = repo.save_event_and_triage(session, event, result)
        escalation = rules.check_repeated_breach(session, event, window_s, threshold)
        if escalation is not None:  # re-read so the frame carries escalated=true
            record = repo.get_detail(session, record["id"])
        return record, escalation


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    session_factory = init_db(settings.database_url)
    queue = IngestQueue(maxsize=settings.ingest_queue_size)
    provider = build_provider(settings)
    service = TriageService(provider)
    store = TriageStore(maxlen=100)
    hub = Hub()

    pool = WorkerPool(
        queue,
        num_workers=settings.ingest_workers,
        process_fn=build_event_handler(
            service,
            store,
            session_factory,
            hub,
            corr_window_s=settings.corr_window_s,
            corr_threshold=settings.corr_threshold,
        ),
    )
    consumer = EventConsumer(
        queue,
        url=settings.simulator_url,
        base_s=settings.reconnect_base_s,
        max_s=settings.reconnect_max_s,
    )
    app.state.ingest_queue = queue
    app.state.worker_pool = pool
    app.state.consumer = consumer
    app.state.triage_service = service
    app.state.triage_store = store
    app.state.triage_provider = provider
    app.state.hub = hub
    app.state.db_session = session_factory
    app.state.sse_heartbeat_s = 15.0
    vision_provider = build_vision_provider(settings)
    app.state.vision_provider = vision_provider
    video = VideoWorker(
        queue,
        source=settings.video_source,
        sample_fps=settings.video_sample_fps,
        threshold=settings.video_motion_threshold,
        min_area=settings.video_min_area,
        site_id=settings.video_site_id,
        zone=settings.video_zone,
        cooldown_s=settings.video_cooldown_s,
        vision_provider=vision_provider,
        vision_cooldown_s=settings.vision_cooldown_s,
        preview_fps=settings.video_preview_fps,
        file_realtime=settings.video_file_realtime,
    )
    app.state.video_worker = video
    pool.start()
    if settings.ingest_enabled:
        consumer.start()
    if settings.video_enabled and settings.video_source:
        video.start()
    try:
        yield
    finally:
        await video.stop()
        await consumer.stop()
        await pool.stop()
        aclose = getattr(provider, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                pass
        aclose = getattr(vision_provider, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Sentinel", version="0.1.0", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    return app


app = create_app()
