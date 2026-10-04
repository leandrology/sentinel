"""Gemini triage provider (Google AI Studio). Async HTTP, timeouts, bounded retries.

Uses the native ``generateContent`` endpoint with ``responseMimeType``
``application/json`` plus a response schema, so the model returns the strict
triage object directly. Shares the ``GOOGLE_AI_*`` settings with vision.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time

import httpx

from app.domain.schemas import NormalizedEvent, TriageResult
from app.providers.base import TriageError, TriageProvider
from app.triage.prompts import PROMPT_VERSION, build_messages

log = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": ["info", "warning", "critical"]},
        "threat_assessment": {
            "type": "string",
            "enum": ["likely_threat", "probable_false_positive", "uncertain"],
        },
        "summary": {"type": "string"},
        "recommended_action": {"type": "string"},
        "certainty": {"type": "number"},
    },
    "required": ["severity", "threat_assessment", "summary", "recommended_action", "certainty"],
}


class GeminiProvider(TriageProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash-lite",
        base_url: str = "https://generativelanguage.googleapis.com",
        timeout_s: float = 8.0,
        max_retries: int = 3,
        max_concurrent: int = 8,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Google AI API key is required")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s)
        self._max_retries = max(0, max_retries)
        self._sem = asyncio.Semaphore(max(1, max_concurrent))
        self._owned_client = client is None
        self._client = client or httpx.AsyncClient(timeout=self._timeout)

    async def aclose(self) -> None:
        if self._owned_client:
            await self._client.aclose()

    async def triage(self, event: NormalizedEvent) -> TriageResult:
        started = time.perf_counter()
        retries = 0
        async with self._sem:
            while True:
                try:
                    raw = await self._request(event)
                    result = self._validate(raw)
                    result.provider = self.name
                    result.model = self._model
                    result.latency_ms = int((time.perf_counter() - started) * 1000)
                    result.retries = retries
                    return result
                except TriageError as exc:
                    if not exc.transient or retries >= self._max_retries:
                        raise
                    retries += 1
                    await asyncio.sleep(self._backoff(retries))

    async def _request(self, event: NormalizedEvent) -> str:
        url = f"{self._base_url}/v1beta/models/{self._model}:generateContent?key={self._api_key}"
        messages = build_messages(event)
        system_text = messages[0]["content"] if len(messages) > 0 else ""
        user_text = messages[1]["content"] if len(messages) > 1 else ""
        body = {
            "system_instruction": {"parts": [{"text": system_text}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 300,
                "responseMimeType": "application/json",
                "responseSchema": _RESPONSE_SCHEMA,
            },
        }
        try:
            resp = await self._client.post(url, json=body)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TriageError(f"transient network: {type(exc).__name__}", transient=True) from exc
        if resp.status_code in _RETRYABLE_STATUS:
            raise TriageError(f"transient status {resp.status_code}", transient=True)
        if resp.status_code != 200:
            raise TriageError(f"permanent status {resp.status_code}", transient=False)
        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TriageError("malformed gemini envelope", transient=False) from exc
        if not isinstance(text, str) or not text.strip():
            raise TriageError("empty model content", transient=False)
        return text

    def _validate(self, content: str) -> TriageResult:
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise TriageError("invalid JSON body", transient=False)
        try:
            payload = json.loads(content[start : end + 1])
        except json.JSONDecodeError as exc:
            raise TriageError("invalid JSON body", transient=False) from exc
        if not isinstance(payload, dict):
            raise TriageError("response not an object", transient=False)
        try:
            return TriageResult(**payload)
        except Exception as exc:
            raise TriageError(f"schema validation: {exc}", transient=False) from exc

    def _backoff(self, attempt: int) -> float:
        delay = min(8.0, 0.5 * (2 ** (attempt - 1)))
        return delay + random.uniform(0, delay * 0.25)

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION
