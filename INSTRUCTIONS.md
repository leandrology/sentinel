# Sentinel Engineering Instructions

Version: 1.0
Project: Sentinel - Real-Time Alarm Monitoring Prototype
Backend: Python / FastAPI
Frontend: Next.js / TypeScript

---

## 1. Purpose

Sentinel is a real-time security alarm monitoring prototype that combines sensor event ingestion, camera-based detection, AI-assisted triage, incident correlation, and an operator dashboard.

The system must be designed around asynchronous event processing and predictable failure handling.

These instructions establish the engineering standards for all contributors and coding agents working on this repository.

They apply to initial development, bug fixes, refactoring, testing, and documentation.

## 2. General engineering principles

Follow these principles:

1. Prefer simple, explicit implementations over unnecessary abstractions.
2. Keep responsibilities separated.
3. Use asynchronous processing for I/O-bound workloads.
4. Keep expensive processing outside the ingestion hot path.
5. Treat external services as unreliable.
6. Validate all external input.
7. Persist important application state.
8. Make operations idempotent where practical.
9. Make failures observable.
10. Write tests alongside implementation.
11. Keep documentation synchronized with actual behavior.
12. Never claim functionality that has not been verified.

Do not introduce infrastructure simply because it is commonly used in production systems.

The prototype should be understandable and runnable on a developer's machine.

## 3. Technology standards

### Backend

* Python 3.12+.
* FastAPI.
* Pydantic v2.
* asyncio.
* HTTPX.
* SQLAlchemy.
* Alembic.
* SQLite for the local prototype.
* OpenCV.
* Pytest.
* pytest-asyncio.
* Ruff.
* MyPy where practical.

### Frontend

* Next.js App Router.
* React.
* TypeScript strict mode.
* Tailwind CSS.
* TanStack Query where useful.
* Playwright.
* Vitest or Jest.

### AI provider

DeepSeek is the primary LLM provider.

Use an asynchronous HTTP client and configurable provider settings.

Do not couple business logic to a particular provider's response format.

### Transport

* WebSockets: external event ingestion.
* SSE: dashboard event delivery.
* HTTP: operator actions and application APIs.

## 4. Repository organization

Keep backend and frontend independently executable.

Suggested structure:

backend/
app/
api/
core/
domain/
ingestion/
processing/
providers/
triage/
vision/
alerts/
persistence/
realtime/
services/
main.py
tests/
unit/
integration/
fixtures/
migrations/
pyproject.toml

frontend/
src/
app/
components/
features/
hooks/
lib/
types/
tests/
package.json

scripts/
run_simulator.py
generate_test_video.py

docs/
architecture.md
decisions.md

Keep the structure proportional to the actual implementation. Do not create empty modules or directories merely to match this example.

## 5. Event contract

All sensor and camera events must follow a common normalized event contract.

Required logical fields:

* event_id
* site_id
* zone
* type
* source
* confidence
* timestamp
* snapshot_url
* metadata

Allowed sources:

* sensor
* camera

Allowed event types:

* motion_detected
* perimeter_breach
* door_forced
* glass_break
* smoke_detected
* fire_alarm
* object_detected
* loitering
* camera_offline
* sensor_fault
* panic_button

Validation requirements:

* Validate incoming payloads with Pydantic.
* Accept optional and missing fields where appropriate.
* Normalize timestamps to UTC.
* Reject invalid confidence values.
* Preserve original event identifiers.
* Generate internal identifiers only where necessary.
* Treat external payloads as untrusted.
* Never silently replace invalid input with fabricated information.

Maintain a distinction between original event data and normalized internal data.

## 6. Ingestion and concurrency

The ingestion service must remain independent of downstream AI processing.

Rules:

* Never await an LLM request directly inside the WebSocket reader.
* Use bounded asyncio queues.
* Use independent consumers for downstream processing.
* Configure worker concurrency.
* Avoid blocking operations on the event loop.
* Keep CPU-intensive video operations off the event-processing hot path.
* Handle connection failures and reconnects.
* Ensure background tasks can be shut down cleanly.
* Handle cancellation correctly.

Define explicit behavior for queue saturation.

Do not claim that events cannot be dropped unless the implementation actually guarantees that behavior.

If the system cannot durably accept an event, expose the failure through logs and metrics.

For this prototype, in-memory queues are acceptable, but their limitations must be documented.

## 7. Event processing

Processing must be modular.

Recommended lifecycle:

Received -> Validated -> Queued -> Triaging -> Triaged -> Persisted -> Broadcast

Additional statuses may include:

* Failed.
* Deferred.
* Escalated.

Use explicit state transitions.

Avoid multiple workers updating the same incident without appropriate synchronization or database transaction handling.

Duplicate event IDs must not create duplicate persisted events or repeated operator actions.

## 8. AI triage standards

AI triage must use a structured response.

Expected fields:

* severity
* threat_assessment
* summary
* recommended_action
* certainty

Severity values:

* info
* warning
* critical

Threat assessment values:

* likely_threat
* probable_false_positive
* uncertain

The model must be instructed to treat event metadata as untrusted evidence, not as instructions.

Never execute commands, SQL, or application actions returned by the model.

Never allow arbitrary model output to change system configuration or operator permissions.

### Deterministic safety rules

Implement deterministic handling for clearly critical events, particularly:

* fire_alarm
* panic_button

Additional safety-critical mappings should be documented and configurable.

AI may add context, but it must not downgrade a deterministic critical classification.

### Reliability

Configure:

* Request timeout.
* Maximum concurrent requests.
* Limited retry attempts.
* Exponential backoff with jitter.
* Response validation.
* Error classification.
* Fallback processing.

Do not retry every failure indefinitely.

Do not retry permanent validation failures as if they were transient network failures.

Record:

* Provider.
* Model.
* Processing duration.
* Outcome.
* Retry count.
* Fallback usage.

Do not store API credentials in logs or event records.

## 9. Prompt engineering standards

Keep system prompts and response schemas in dedicated, version-controlled application modules.

Avoid scattering large prompt strings across API routes.

AI prompts must:

* Define the expected role.
* Explain the event context.
* Specify allowed classification values.
* Require concise operator-ready output.
* Prohibit invented evidence.
* Treat missing fields as unknown.
* Avoid unsupported assumptions.
* Request a valid structured response.

The model must distinguish observed facts from uncertainty.

A confidence score provided by the original detector must not automatically be treated as the probability that an actual threat exists.

## 10. Computer vision

Video processing must run independently from the API request lifecycle.

Use OpenCV for the initial implementation.

Requirements:

* Configurable video source.
* Configurable frame sampling interval.
* Configurable motion sensitivity.
* Noise reduction.
* Frame resource cleanup.
* Detection event generation.
* UTC timestamps.
* Confidence values.
* Source identification.
* Graceful handling of unavailable streams.

Do not assume that motion detection identifies a person or proves malicious activity.

Only include object classifications when an actual detector provides them.

Camera detections must enter the common event pipeline.

Do not send every frame to an LLM.

## 11. Correlation and alert escalation

Keep deterministic alert rules separate from AI triage.

Implement configurable repeated-event detection.

Initial rule:

Repeated perimeter breaches at the same site and zone within a defined time window should trigger an escalation.

Consider:

* Event type.
* Site.
* Zone.
* Time window.
* Duplicate event IDs.
* Existing escalation state.

Avoid generating duplicate escalation records for the same correlation window.

Escalation must be explainable and traceable to the events that triggered it.

## 12. API and real-time delivery

Use consistent HTTP response structures.

Document endpoints and expected payloads.

SSE requirements:

* Correct content type.
* Correct event framing.
* Connection cleanup.
* Heartbeats where appropriate.
* Reconnection support.
* Event identifiers for recovery.
* Multiple-client support.
* No continuous database polling per client.

Do not expose internal exceptions or sensitive configuration in API responses.

Protect operator endpoints against invalid state transitions.

## 13. Persistence

SQLite is sufficient for this assessment.

Use SQLAlchemy models and Alembic migrations.

Persist:

* Events.
* Triage results.
* Incidents.
* Incident status changes.
* Acknowledgments.
* Resolutions.
* Escalations.

Keep event history immutable where possible.

Represent status changes as explicit records when practical.

Use transactions for related updates.

Do not rely on frontend state as the authoritative record.

## 14. Frontend standards

The dashboard must prioritize situational awareness.

The interface should communicate:

* What happened?
* Where did it happen?
* When did it happen?
* How severe is it?
* What does the AI recommend?
* What action has the operator taken?

Use reusable components.

Keep business logic out of large page components.

Separate transport logic from presentation.

Handle:

* Initial loading.
* Empty states.
* API failures.
* SSE disconnections.
* Reconnection.
* Duplicate updates.
* Stale data.
* Optimistic action rollback.

Use semantic HTML and accessible interactions.

Critical information must not depend on color alone.

## 15. Testing standards

Every meaningful feature must have corresponding tests.

### Backend

Use:

* Unit tests for domain logic.
* Integration tests for database and API behavior.
* Async tests for workers and queues.
* Mocked HTTP responses for LLM providers.
* Controlled fixtures for video detection.

### Frontend

Test:

* Component behavior.
* State transitions.
* Event updates.
* Incident actions.
* Loading and error states.
* Accessibility-critical interactions.

### Required scenarios

Test at minimum:

1. Valid sensor event.
2. Missing optional fields.
3. Malformed event.
4. Duplicate event.
5. Event burst.
6. WebSocket disconnection.
7. Slow AI provider.
8. AI timeout.
9. Rate-limited AI provider.
10. Invalid AI response.
11. Deterministic critical event.
12. Video detection.
13. Video source unavailable.
14. Repeated perimeter breach.
15. Dashboard reconnection.
16. Incident acknowledgment.
17. Incident resolution.

Tests must not depend on a paid API key.

Never modify or weaken a test merely to make a failing build appear successful.

## 16. Code quality

Follow consistent formatting and naming conventions.

Python:

* Use type annotations.
* Prefer explicit return types.
* Use structured logging.
* Avoid mutable global state.
* Use context managers for resources.
* Handle cancellation and exceptions explicitly.
* Keep functions focused.

TypeScript:

* Use strict typing.
* Avoid unnecessary `any`.
* Validate external data.
* Avoid excessive prop drilling.
* Keep components focused.
* Handle asynchronous errors.

Comments should explain decisions or non-obvious behavior.

Do not add comments that simply repeat the code.

Avoid:

* Generic placeholder comments.
* Excessive documentation strings.
* Unnecessary TODOs.
* Dead code.
* Unused imports.
* Broad exception suppression.
* Silent fallback behavior.
* Overengineering.
* Unnecessary design patterns.

## 17. Security

* Keep secrets in environment variables.
* Commit `.env.example`, never actual credentials.
* Validate all external input.
* Treat event metadata as untrusted.
* Restrict CORS to configured origins.
* Do not expose stack traces to clients.
* Avoid logging secrets.
* Limit request payload sizes.
* Avoid unsafe dynamic SQL.
* Protect operator state-changing endpoints.
* Keep uploaded and generated media in controlled locations.

The local prototype does not require full enterprise authentication, but the limitations must be documented.

## 18. Git and repository hygiene

Maintain a focused `.gitignore`.

Ignore local-only artifacts such as:

* Python bytecode.
* Virtual environments.
* pytest caches.
* Coverage outputs.
* Node modules.
* Next.js build output.
* Local environment files.
* Local databases.
* Editor workspace settings.
* Temporary agent execution logs.
* Local AI tool state.
* Generated video and frame captures.
* OS-generated files.

Do not ignore:

* Application source code.
* Tests.
* Required project instructions.
* README.
* Dependency manifests.
* Lockfiles.
* Database migrations.
* Configuration templates.
* Required AI provider implementation.

Do not alter Git history to conceal how code was produced.

The repository should be clean, reproducible, and reviewable.

## 19. Documentation

The README must be concise and factual.

Include:

* Project overview.
* Architecture.
* Stack.
* Prerequisites.
* Environment setup.
* Installation.
* Startup.
* Event simulator instructions.
* Video source instructions.
* DeepSeek configuration.
* API endpoints.
* Test commands.
* Limitations.
* Design trade-offs.

Verify every command before documenting it as working.

Keep architecture decisions in `docs/decisions.md` when they materially affect implementation.

## 20. Agent collaboration

If multiple agents are used:

* Assign each agent a clearly defined responsibility.
* Establish shared interfaces before parallel implementation.
* Avoid concurrent edits to the same files.
* Keep event schemas consistent.
* Require agents to report files changed and tests executed.
* Review all generated code before merging.
* Resolve interface mismatches centrally.
* Never assume another agent's implementation is correct without verification.

The primary agent owns integration and final verification.

## 21. Final review checklist

Before considering the project complete, verify:

* [ ] Clean installation works.
* [ ] Backend starts.
* [ ] Frontend starts.
* [ ] Event simulator works.
* [ ] Event ingestion is continuous.
* [ ] Queue limits are enforced.
* [ ] Camera processing works.
* [ ] Camera events enter the common pipeline.
* [ ] DeepSeek integration works with credentials.
* [ ] Fallback triage works without credentials.
* [ ] Critical events cannot be downgraded.
* [ ] Incident history persists.
* [ ] Dashboard updates through SSE.
* [ ] Acknowledgment works.
* [ ] Resolution works.
* [ ] Correlation escalation works.
* [ ] Failure scenarios are tested.
* [ ] Tests pass.
* [ ] Lint and type checks pass.
* [ ] README matches actual behavior.
* [ ] No secrets or local artifacts are committed.

When uncertain, favor a smaller verified implementation over a larger speculative one.

The objective is to demonstrate engineering judgment, not code volume.
