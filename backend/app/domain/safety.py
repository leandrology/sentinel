"""Deterministic safety rules. LLM output must never downgrade these."""

from app.domain.schemas import EventType, Severity

DETERMINISTIC_CRITICAL: frozenset[EventType] = frozenset({"fire_alarm", "panic_button"})

_SEVERITY_RANK: dict[Severity, int] = {"info": 0, "warning": 1, "critical": 2}


def clamp_severity(event_type: EventType, proposed: Severity) -> Severity:
    """Floor severity at critical for safety-critical event types."""
    if event_type in DETERMINISTIC_CRITICAL:
        if _SEVERITY_RANK[proposed] < _SEVERITY_RANK["critical"]:
            return "critical"
    return proposed


def is_deterministic_critical(event_type: EventType) -> bool:
    return event_type in DETERMINISTIC_CRITICAL
