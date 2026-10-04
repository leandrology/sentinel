# Sentinel — architecture

Minimal async pipeline, single deployable backend + Next.js dashboard.

```
simulator (WS) ──> consumer (validate/normalize/dedupe) ──> bounded asyncio.Queue
                                                                      │
video worker (cv2, sampled) ──> same queue.put ─────────────────────────┤
                                                                      ▼
                                              workers(N) → safety clamp → AI triage
                                                (mock | gemini | fallback)
                                                        │
                                                        ▼
                                              SQLite (events, triage, incidents,
                                                      status changes, escalations)
                                                        │
                                                        ▼
                                              hub fan-out ──> SSE /events/stream
                                                        │
                                                        ▼
                                              Next.js dashboard (useSSE + REST)
```

Key decisions:

* In-memory `asyncio.Queue(maxsize)` + explicit overload policy (preserve
  `fire_alarm`/`panic_button`, count drops in metrics). Documented limit:
  unacked in-memory backlog is lost on restart.
* LLM never in WS reader hot path; workers only.
* Deterministic safety clamp before/after LLM: critical floor cannot be
  downgraded.
* SSE hub is in-process `set[asyncio.Queue]` broadcast-on-write; no per-client
  DB polling. Reconnects replay bounded recent history; dashboard reconciles
  via REST reload plus `event_id` dedupe (sequence resets on restart).
* Correlation is a deterministic DB query, separate from LLM.
