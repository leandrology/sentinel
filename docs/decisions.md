# Decisions

* 2026-10-01 — Start with `Base.metadata.create_all()` instead of Alembic.
  Reason: single SQLite file prototype; models kept migration-ready.
  Revisit if schema churn requires history.
* 2026-10-01 — `opencv-python-headless` on server to avoid GUI deps.
* 2026-10-01 — Synthetic MP4 as default video source (deterministic, CI-safe).
  Webcam via `VIDEO_SOURCE=0`.
* 2026-10-01 — `AI_PROVIDER=mock` default; `deepseek` only when
  `DEEPSEEK_API_KEY` is set. Tests always use mock, never live key.
* 2026-10-01 — Correlation uses fixed wall-clock buckets
  (`floor(ts / window)`), one escalation per bucket. Bounded, explainable,
  no duplicate storms; next bucket may escalate again.
* 2026-10-01 — Escalation frames broadcast as SSE `escalation` events;
  dashboard refetches incidents to pick up `escalated` flags.
* 2026-10-01 — Playwright E2E runs backend :8100 + frontend :3100 with
  `CORS_ORIGINS` widened for the harness only; prod default stays :3000.
  Worker video fixtures carry `cam_` event IDs to distinguish them from
  simulator camera rows.
* 2026-10-01 — Manual Next.js scaffold (no `create-next-app` network weight),
  pinned Next 14 + React 18 for local reproducibility.
* 2026-10-03 — Video studio: dashboard upload (`POST /api/video/upload`,
  mp4/webm ≤100 MB) + runtime `POST /api/video/source` switch instead of
  `VIDEO_SOURCE` restart. Raw `<video>` preview client-side; annotated MJPEG
  (`/api/video/stream.mjpeg`) server-side. Browser webcam via
  `getUserMedia` + throttled `POST /api/video/frames`; server webcam stays
  host-only (no Docker passthrough).
* 2026-10-03 — Simulator opt-out is a dashboard toggle
  (`POST /api/ingestion/stop|start`), not removal. Video-only mode keeps
  camera events on the same queue/pipeline.
* 2026-10-04 — Sensor simulator ingestion defaults to opted out
  (`INGEST_ENABLED=false` in config, `.env.example`, and compose).
  Opt in via dashboard Resume (`POST /api/ingestion/start`) or
  `INGEST_ENABLED=true`. E2E keeps `INGEST_ENABLED=true` explicitly.
* 2026-10-04 — Gemini via Google AI Studio is the primary LLM provider:
  `AI_PROVIDER=gemini` uses `GOOGLE_AI_API_KEY`/`GOOGLE_AI_MODEL`
  (default `gemini-3.5-flash-lite`) for triage; vision already used the same
  key. `deepseek` branch kept for compat. `gemini-2.0-flash` retired
  (shut down 2026-06-01).
* 2026-10-03 — Vision LLM is motion-gated enrichment, not replacement:
  `VisionProvider` (`mock|gemini|twelvelabs|disabled`) analyzes one JPEG
  keyframe per motion (`VISION_COOLDOWN_S`), writes `metadata.vision`
  (label/severity_hint/description); final severity still from
  `TriageService` + `clamp_severity`. Missing keys fall back to mock;
  any vision failure yields a motion-only event.
