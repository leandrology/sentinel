"""Provider contract. Business logic depends only on this, never on DeepSeek."""

from __future__ import annotations

from typing import Protocol

from app.domain.schemas import NormalizedEvent, TriageResult


class TriageError(Exception):
    """Provider failure. ``transient=True`` means retry may help."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class TriageProvider(Protocol):
    name: str

    async def triage(self, event: NormalizedEvent) -> TriageResult:
        """Classify one event. Raises TriageError on provider failure."""
        ...
