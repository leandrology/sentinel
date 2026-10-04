"""DeepSeek provider. Async HTTP, timeouts, bounded retries, strict validation."""

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


class DeepSeekProvider(TriageProvider):
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout_s: float = 8.0,
        max_retries: int = 3,
        max_concurrent: int = 8,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("DeepSeek API key is required")
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
        url = f"{self._base_url}/chat/completions"
        body = {
            "model": self._model,
            "messages": build_messages(event),
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "max_tokens": 300,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = await self._client.post(url, json=body, headers=headers)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TriageError(f"transient network: {type(exc).__name__}", transient=True) from exc
        if resp.status_code in _RETRYABLE_STATUS:
            raise TriageError(f"transient status {resp.status_code}", transient=True)
        if resp.status_code != 200:
            raise TriageError(f"permanent status {resp.status_code}", transient=False)
        try:
            data = resp.json()
        except ValueError as exc:
            raise TriageError("invalid JSON envelope", transient=False) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TriageError("missing choices content", transient=False) from exc
        if not isinstance(content, str) or not content.strip():
            raise TriageError("empty model content", transient=False)
        return content

    def _validate(self, content: str) -> TriageResult:
        try:
            payload = json.loads(content)
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
