"""Bounded in-memory store for recent triage outcomes (M5 persists to SQLite)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from app.domain.schemas import NormalizedEvent, TriageResult


@dataclass
class TriageRecord:
    event: NormalizedEvent
    triage: TriageResult


@dataclass
class TriageStore:
    maxlen: int = 100
    triaged_total: int = 0
    fallback_total: int = 0
    _recent: deque[TriageRecord] = field(init=False)

    def __post_init__(self) -> None:
        self._recent = deque(maxlen=self.maxlen)

    def add(self, event: NormalizedEvent, triage: TriageResult) -> None:
        self._recent.append(TriageRecord(event=event, triage=triage))
        if triage.fallback or triage.triage_status == "fallback":
            self.fallback_total += 1
        else:
            self.triaged_total += 1

    def recent(self, limit: int = 20) -> list[TriageRecord]:
        items = list(self._recent)
        return items[-max(1, limit) :][::-1]
