"""Clearly-labeled rule-based fallback. Never masquerades as LLM output."""

from __future__ import annotations

from app.domain.safety import is_deterministic_critical
from app.domain.schemas import NormalizedEvent, TriageResult


def fallback_triage(event: NormalizedEvent, reason: str, latency_ms: int = 0) -> TriageResult:
    if is_deterministic_critical(event.type):
        severity: str = "critical"
        action = (
            f"Treat as critical {event.type} at {event.site_id}/{event.zone}. "
            "Dispatch per protocol."
        )
        certainty = 0.9
    elif event.type in {"perimeter_breach", "door_forced", "glass_break", "smoke_detected"}:
        severity = "warning"
        action = (
            f"Investigate {event.type} at {event.site_id}/{event.zone}; "
            "verify with adjacent sensors."
        )
        certainty = 0.5
    else:
        severity = "info"
        action = f"Log {event.type} at {event.site_id}/{event.zone} and monitor for repeats."
        certainty = 0.4
    where = f"{event.type} at {event.site_id}/{event.zone}"
    return TriageResult(
        severity=severity,  # type: ignore[arg-type]
        threat_assessment="uncertain",
        summary=f"Fallback triage (AI unavailable: {reason}): {where}.",
        recommended_action=action,
        certainty=certainty,
        provider="fallback",
        model="rules-v1",
        latency_ms=latency_ms,
        retries=0,
        fallback=True,
        triage_status="fallback",
    )
