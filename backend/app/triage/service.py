"""Orchestrates provider triage: clamp safety-critical, fall back on any failure."""

from __future__ import annotations

import logging
import time

from app.domain.safety import clamp_severity
from app.domain.schemas import NormalizedEvent, TriageResult
from app.providers.base import TriageProvider
from app.providers.fallback import fallback_triage

log = logging.getLogger(__name__)


class TriageService:
    def __init__(self, provider: TriageProvider) -> None:
        self.provider = provider

    @property
    def provider_name(self) -> str:
        return self.provider.name

    async def triage_event(self, event: NormalizedEvent) -> TriageResult:
        """Never raises: provider failures become labeled fallback results."""
        started = time.perf_counter()
        try:
            result = await self.provider.triage(event)
        except Exception as exc:
            latency = int((time.perf_counter() - started) * 1000)
            reason = f"{type(exc).__name__}"
            log.warning("triage provider %s failed: %s", self.provider.name, reason)
            return fallback_triage(event, reason, latency_ms=latency)
        # LLM must not downgrade deterministic criticals.
        clamped = clamp_severity(event.type, result.severity)
        if clamped != result.severity:
            log.info("safety clamp %s -> %s for %s", result.severity, clamped, event.event_id)
            result.severity = clamped
        return result
