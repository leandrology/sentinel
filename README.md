# Sentinel

Real-time alarm monitoring with AI-assisted triage. Sensor events arrive over
WebSockets, camera detections come from a background video worker; both share
one async pipeline (validate → queue → triage → persist → correlate →
broadcast) feeding a live Next.js operations dashboard over SSE.

## Architecture

```
simulator (WS :8765) ──> consumer (validate/normalize/dedupe) ──> bounded asyncio.Queue(500)
                                                                               │
video worker (OpenCV, sampled) ──> queue.submit_event ──────────────────────────┤
                                                                               ▼
                                              workers(4) → safety clamp → triage (mock|gemini|fallback)
                                                                         │
                                                                         ▼
                                              SQLite (events, triages, incidents, status_changes, escalations)
                                                                         │
                                                                         ▼
                                              Hub fan-out ──> SSE /api/events/stream ──> dashboard
```

Overload policy: the WS reader never blocks. A full queue drops incoming
non-critical events (counted in metrics/logs); incoming `fire_alarm` /
`panic_button` evict the oldest queued event instead. No silent loss.

## Stack

Backend: Python 3.12+, FastAPI, Pydantic v2, asyncio, HTTPX, SQLAlchemy +
SQLite, OpenCV (headless), websockets, pytest/pytest-asyncio, Ruff, MyPy.
Frontend: Next.js 14 App Router, React 18, strict TypeScript, Tailwind,
TanStack Query, Vitest, Playwright. AI: Gemini via Google AI Studio
(`generateContent`, triage + vision; DeepSeek `chat/completions` kept for compat).

## Prerequisites

* Python 3.12+ (`python --version` on Windows, `python3 --version` on Mac)
* Node 20+ and npm (`node --version`, `npm --version`)
* Git
* No API key needed for tests or local demo (`AI_PROVIDER=mock` default)
* Optional (Docker path): Docker Desktop 4.x+ with `docker compose`

Install Node if missing:

* Windows: install from https://nodejs.org (LTS 20+) or `winget install OpenJS.NodeJS.LTS`
* Mac: `brew install node@20` or install from https://nodejs.org (LTS 20+)

## Install — Windows (Command Prompt / cmd)

Open **Command Prompt** (`cmd.exe`), not PowerShell. All commands below are
plain `cmd` syntax with plain `npm`.

```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd ..\frontend
npm install
npx playwright install chromium   :: E2E only, skip otherwise
```

## Install — Mac (Terminal / zsh)

Open **Terminal** (zsh). Use `python3` and `source`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../frontend
npm install
npx playwright install chromium   # E2E only, skip otherwise
```

## Configure

From the repo root, copy the template (`.env` is git-ignored):

```cmd
:: Windows (cmd, from repo root)
copy .env.example .env
```

```bash
# Mac (from repo root)
cp .env.example .env
```

Relevant vars (see `.env.example`): `SIMULATOR_URL`, `SIMULATOR_MIN_DELAY_S`
(30), `SIMULATOR_MAX_DELAY_S` (40), `INGEST_ENABLED` (`false`, sensor
simulator is opted out by default), `INGEST_QUEUE_SIZE`
(500), `INGEST_WORKERS` (4), `AI_PROVIDER` (`mock`|`gemini`),
`GOOGLE_AI_API_KEY`, `GOOGLE_AI_MODEL` (`gemini-3.5-flash-lite`), `AI_TIMEOUT_S` (8),
`AI_MAX_RETRIES` (3), `AI_MAX_CONCURRENT` (8), `VIDEO_SOURCE`,
`VIDEO_SAMPLE_FPS` (2), `VIDEO_PREVIEW_FPS` (15), `VIDEO_FILE_REALTIME`
(`true`, keeps uploaded-file loop near realtime), `VIDEO_MOTION_THRESHOLD` (25), `VIDEO_MIN_AREA`
(500), `VIDEO_COOLDOWN_S` (5), `CORR_WINDOW_S` (300), `CORR_THRESHOLD` (3),
`DATABASE_URL` (`sqlite:///./sentinel.db`), `CORS_ORIGINS`.

## Run locally — Windows (cmd, 3 windows)

Terminal 1 — event simulator (from `backend/`, venv activated):

```cmd
python scripts\run_simulator.py
:: Event stream live on ws://0.0.0.0:8765
```

Terminal 2 — backend (from `backend/`, venv activated):

```cmd
python -m uvicorn app.main:app --reload --port 8000
:: health: http://localhost:8000/api/health
```

Terminal 3 — frontend (from `frontend/`):

```cmd
npm run dev
:: app: http://localhost:3000
```

With `AI_PROVIDER=mock` the sensor simulator is opted out by default —
click Resume in the dashboard (or `POST /api/ingestion/start`) to ingest;
then the first incident arrives in ~30-40s (simulator
pacing; override with `SIMULATOR_MIN_DELAY_S` / `SIMULATOR_MAX_DELAY_S`).
For live AI
(from `backend/`, venv activated):

```cmd
set AI_PROVIDER=gemini
set GOOGLE_AI_API_KEY=<key>
python -m uvicorn app.main:app --port 8000
```

## Run locally — Mac (Terminal, 3 tabs)

Terminal 1 — event simulator (from `backend/`, venv activated):

```bash
python scripts/run_simulator.py
# Event stream live on ws://0.0.0.0:8765
```

Terminal 2 — backend (from `backend/`, venv activated):

```bash
python -m uvicorn app.main:app --reload --port 8000
# health: http://localhost:8000/api/health
```

Terminal 3 — frontend (from `frontend/`):

```bash
npm run dev
# app: http://localhost:3000
```

With `AI_PROVIDER=mock` the sensor simulator is opted out by default —
click Resume in the dashboard to ingest. For live AI:

```bash
export AI_PROVIDER=gemini GOOGLE_AI_API_KEY=<key>
python -m uvicorn app.main:app --port 8000
```

## Run with Docker (Windows and Mac)

One command starts all three services (event simulator + backend + frontend).
No venv or local Node/Python setup needed — only Docker Desktop.

```bash
docker compose up --build
```

* app: http://localhost:3000
* api health: http://localhost:8000/api/health
* simulator (internal): `ws://simulator:8765`, also published at `ws://localhost:8765`

Useful commands:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f simulator
docker compose down
docker compose down -v   # also removes the sqlite volume
```

Notes:

* The compose stack sets `SIMULATOR_URL=ws://simulator:8765`,
  `DATABASE_URL=sqlite:////data/sentinel.db` (persisted in the
  `sentinel-data` volume), and `CORS_ORIGINS=http://localhost:3000`.
* The frontend image is a production build (`npm run build` + `npm run start`).
  `NEXT_PUBLIC_API_URL` is baked at build time (default `http://localhost:8000`);
  override with `NEXT_PUBLIC_API_URL=http://localhost:8000 docker compose up --build`.
* Live AI in Docker: `AI_PROVIDER=gemini GOOGLE_AI_API_KEY=<key> docker compose up --build`
  (or set them in a root `.env` file — compose reads `AI_PROVIDER`,
  `GOOGLE_AI_API_KEY`, `GOOGLE_AI_MODEL`, `LOG_LEVEL` from it).
* `backend/Dockerfile` (Python 3.12-slim + uvicorn) and
  `frontend/Dockerfile` (Node 20 multi-stage build) are used by `docker-compose.yml`.
  The simulator reuses the backend image with `python scripts/run_simulator.py`,
  which binds `0.0.0.0:8765` (overridable via `SIMULATOR_HOST` / `SIMULATOR_PORT`,
  `SIMULATOR_MIN_DELAY_S` / `SIMULATOR_MAX_DELAY_S` for 30~40s pacing).

## Video source

File (deterministic, default for tests/E2E). Run from `backend/` with venv activated:

```cmd
:: Windows (cmd)
python scripts\generate_test_video.py demo.mp4
set VIDEO_ENABLED=true
set VIDEO_SOURCE=demo.mp4
set VIDEO_COOLDOWN_S=2
python -m uvicorn app.main:app --reload --port 8000
```

```bash
# Mac
python scripts/generate_test_video.py demo.mp4
export VIDEO_ENABLED=true VIDEO_SOURCE=demo.mp4 VIDEO_COOLDOWN_S=2
python -m uvicorn app.main:app --reload --port 8000
```

Webcam: `VIDEO_SOURCE=0`. Status/control: `GET /api/video/status`,
`POST /api/video/start|stop` (also in the dashboard video studio).
Worker events (`cam_*`, `source=camera`) enter the same queue as sensors.

Dashboard video studio (no restart needed): upload an mp4/webm in the
dashboard (File tab → Use as live feed), which calls `POST /api/video/upload`
then `POST /api/video/source`; server webcam via `POST /api/video/source
{"source":"0"}`; browser webcam via `POST /api/video/frames`; simulator
opt-out via `POST /api/ingestion/stop|start`. Previews: raw `<video>` for
uploads, `GET /api/video/stream.mjpeg` / `GET /api/video/snapshot.jpg` for
annotated server frames.

Vision LLM (motion-gated): `VISION_PROVIDER=mock|gemini|twelvelabs|disabled`
with `GOOGLE_AI_API_KEY` (AI Studio) or `TWELVELABS_API_KEY`. One JPEG
keyframe per motion (cooldown `VISION_COOLDOWN_S`) enriches
`metadata.vision`; final severity still uses triage + safety clamp.
See `GET /api/vision/status`.

Note: webcam devices (`VIDEO_SOURCE=0`) are host-only and are not passed
through in the default `docker-compose.yml`. Use a file source or run video
locally if you need camera input.

## How AI triage works

Each event gets one provider call with a minimal context block (type, site,
zone, source, confidence, UTC timestamp, ≤500 chars of metadata — never
frames). The versioned prompt (`app/triage/prompts.py`) requires a strict
JSON object validated against `TriageResult` (`extra=forbid`); metadata is
declared untrusted evidence. Before/after the call,
`clamp_severity` floors `fire_alarm`/`panic_button` to `critical` — the LLM
can add context but never downgrade. Concurrency is semaphore-capped;
retries (backoff+jitter) apply to transient failures only (timeout, network,
429/5xx). Latency, retries, provider/model, and outcome are recorded.

Fallback: any provider failure yields a labeled rule-based result
(`provider=fallback`, `fallback=true`, `triage_status=fallback`) that still
honors the critical floor. The pipeline never stalls on AI errors.

## API endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/ingestion/status` | connected, queue depth/max, dropped, workers |
| GET | `/api/metrics` | + triaged/fallback counts, provider, SSE subs |
| GET | `/api/incidents` | `?status=&site_id=&zone=&severity=&limit=&offset=`, severity-ordered |
| GET | `/api/incidents/{id}` | full detail (404) |
| POST | `/api/incidents/{id}/acknowledge` | `{"actor"}`; idempotent; 409 if resolved |
| POST | `/api/incidents/{id}/resolve` | `{"actor"}`; idempotent |
| GET | `/api/triage/recent` | in-memory recent (diagnostic) |
| GET | `/api/events/stream` | SSE `incident` + `escalation` frames, replay + heartbeat |
| GET | `/api/video/status` | worker state + vision counters |
| POST | `/api/video/start`, `/api/video/stop` | independent worker control |
| POST | `/api/video/upload` | multipart mp4/webm (100 MB default) |
| GET | `/api/video/sources` | uploaded files |
| POST | `/api/video/source` | `{"source":"<id|path|0>"}` switch + restart |
| GET | `/api/video/file/{id}` | raw file for preview |
| GET | `/api/video/snapshot.jpg` | last annotated frame |
| GET | `/api/video/stream.mjpeg` | MJPEG annotated preview |
| POST | `/api/video/frames` | browser webcam `{image_b64}` |
| GET | `/api/vision/status` | vision provider + counters |
| POST | `/api/ingestion/start`, `/api/ingestion/stop` | simulator opt-out toggle |

## Testing

Backend (from `backend/` with venv activated, no key required):

Windows (cmd):

```cmd
python -m pytest -q
ruff check app tests
ruff format --check app tests
python -m mypy app
```

Mac:

```bash
python -m pytest -q
ruff check app tests
ruff format --check app tests
python -m mypy app
```

Frontend (from `frontend/`, same on Windows cmd and Mac):

```bash
npm run test
npx tsc --noEmit
npm run build
npx playwright test   # needs ports 8765/8100/3100 free
```

Current results: backend 85 passed + 1 hardware-gated skip; frontend 21
Vitest passed; Playwright 2 passed (sensor E2E incl. ack persistence,
camera E2E via `cam_` worker fingerprint); Ruff/MyPy/`tsc` clean.

## Known limitations

* In-memory queue + SSE hub: backlog and sequence numbers reset on restart;
  clients reconcile via REST history + `event_id` dedupe.
* SQLite via `create_all` (no Alembic revisions yet); single-writer prototype scale.
* No authentication; local prototype. CORS defaults to `http://localhost:3000`.
* Motion detection is frame-differencing, not person/object recognition.
* Live Gemini calls were verified by design review + mocked fault matrix,
  not against the paid API in this run (no key in environment).

## Design decisions and trade-offs

See `docs/architecture.md` and `docs/decisions.md`. Highlights: bounded
queues with an explicit critical-preserving drop policy instead of claiming
lossless delivery; sync SQLite accessed via `to_thread` instead of an async
driver; fixed wall-clock correlation buckets (one escalation per bucket);
SSE broadcast-on-write instead of per-client polling; mock-first provider
with a substitutable interface.
