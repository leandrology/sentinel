"""Deterministic mock provider. Default for dev/tests. No network."""

from __future__ import annotations

import time

from app.domain.schemas import NormalizedEvent, TriageResult
from app.providers.base import TriageProvider

_LIKELY_THREAT = {"perimeter_breach", "door_forced", "glass_break", "fire_alarm", "panic_button"}


class MockProvider(TriageProvider):
    name = "mock"

    async def triage(self, event: NormalizedEvent) -> TriageResult:
        started = time.perf_counter()
        if event.type in ("fire_alarm", "panic_button"):
            severity, threat, certainty = "critical", "likely_threat", 0.95
        elif event.type in _LIKELY_THREAT:
            severity, threat = "warning", "likely_threat"
            certainty = 0.6 + 0.3 * event.confidence
        elif event.confidence < 0.5:
            severity, threat, certainty = "info", "probable_false_positive", 0.6
        else:
            severity, threat, certainty = "info", "uncertain", 0.5
        return TriageResult(
            severity=severity,  # type: ignore[arg-type]
            threat_assessment=threat,  # type: ignore[arg-type]
            summary=f"{event.type} at {event.site_id}/{event.zone} (mock).",
            recommended_action="Review event and acknowledge if benign.",
            certainty=round(certainty, 2),
            provider=self.name,
            model="mock-v1",
            latency_ms=int((time.perf_counter() - started) * 1000),
            retries=0,
            fallback=False,
            triage_status="triaged",
        )
