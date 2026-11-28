"""DeepSeek chat-completion provider."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from copy import deepcopy
from typing import Any

import httpx

from app.config.settings import Settings
from app.core.exceptions import LLMProviderError, LLMTruncationError
from app.core.retry import is_retryable_status, with_exponential_backoff
from app.memory.budget import enforce_request_budget
from app.observability.tracing import traced
from app.providers.base import LLMResponse
from app.schemas.common import TokenUsage

logger = logging.getLogger(__name__)


class DeepSeekProvider:
    """OpenAI-compatible DeepSeek chat completions client.

    Timeouts are split so a hung connect does not block a worker forever.
    400/401/403 are not retried.
    Non-streaming calls can explicitly select thinking mode and capture raw bodies.
    """

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient | None = None,
        *,
        thinking_enabled: bool | None = None,
        capture_raw: bool = False,
    ) -> None:
        self._settings = settings
        self._thinking_enabled = thinking_enabled
        self._capture_raw = capture_raw
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=settings.deepseek_base_url.rstrip("/"),
            timeout=httpx.Timeout(
                connect=3.0,
                read=settings.llm_timeout_seconds,
                write=10.0,
                pool=5.0,
            ),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ping(self) -> bool:
        """Do not call chat completions here — readiness must stay cheap."""
        return bool(self._settings.deepseek_api_key.get_secret_value())

    @traced("llm.deepseek", "llm")
    async def generate(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        response_format: dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Send one completion, optionally with native function definitions and tool messages."""
        api_key = self._settings.deepseek_api_key.get_secret_value()
        if not api_key:
            raise LLMProviderError("DeepSeek API key is not configured")

        payload: dict[str, object] = {
            "model": self._settings.deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if self._thinking_enabled is not None:
            payload["thinking"] = {"type": "enabled" if self._thinking_enabled else "disabled"}
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        enforce_request_budget(payload, self._settings.token_budget)

        @traced("llm.http_attempt", "chain")
        async def _call() -> LLMResponse:
            try:
                response = await self._client.post(
                    "/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise LLMProviderError("DeepSeek request timed out", timeout=True) from exc
            except httpx.HTTPError as exc:
                raise LLMProviderError("DeepSeek transport error") from exc

            if response.status_code in {400, 401, 403, 404, 422}:
                raise LLMProviderError(
                    f"DeepSeek HTTP {response.status_code}",
                    retryable=False,
                )
            if response.status_code == 429:
                raise LLMProviderError("DeepSeek rate limited", rate_limited=True)
            if is_retryable_status(response.status_code):
                raise LLMProviderError(f"DeepSeek HTTP {response.status_code}")
            if response.status_code >= 400:
                raise LLMProviderError(f"DeepSeek HTTP {response.status_code}")

            try:
                body = response.json()
            except ValueError as exc:
                raise LLMProviderError("DeepSeek response is not JSON", retryable=False) from exc
            try:
                choice = body["choices"][0]
                message = choice["message"]
                tool_calls = message.get("tool_calls") or []
                content = message.get("content") if tool_calls else message["content"]
                finish_reason = choice.get("finish_reason")
            except (AttributeError, KeyError, IndexError, TypeError) as exc:
                raise LLMProviderError("DeepSeek response missing choices") from exc
            if content is not None and not isinstance(content, str):
                raise LLMProviderError("DeepSeek response content is invalid", retryable=False)
            if response_format and finish_reason == "length":
                raise LLMTruncationError()
            usage_raw = body.get("usage") or {}
            usage = TokenUsage(
                prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
                completion_tokens=int(usage_raw.get("completion_tokens") or 0),
                total_tokens=int(usage_raw.get("total_tokens") or 0),
            )
            cache_hit = usage_raw.get("prompt_cache_hit_tokens")
            cache_miss = usage_raw.get("prompt_cache_miss_tokens")
            return LLMResponse(
                content=content or "",
                usage=usage,
                model=body.get("model") or self._settings.deepseek_model,
                finish_reason=finish_reason,
                tool_calls=tool_calls,
                prompt_cache_hit_tokens=int(cache_hit) if cache_hit is not None else None,
                prompt_cache_miss_tokens=int(cache_miss) if cache_miss is not None else None,
                raw_request=json.loads(response.request.content) if self._capture_raw else None,
                raw_response=deepcopy(body) if self._capture_raw else None,
            )

        return await with_exponential_backoff(
            _call,
            max_attempts=self._settings.llm_max_retries,
            operation_name="deepseek.generate",
        )

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 1024,
        response_format: dict[str, str] | None = None,
    ) -> AsyncIterator[str]:
        api_key = self._settings.deepseek_api_key.get_secret_value()
        if not api_key:
            raise LLMProviderError("DeepSeek API key is not configured")

        payload: dict[str, object] = {
            "model": self._settings.deepseek_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        enforce_request_budget(payload, self._settings.token_budget)

        try:
            async with self._client.stream(
                "POST",
                "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            ) as response:
                if response.status_code in {400, 401, 403, 404, 422}:
                    raise LLMProviderError(
                        f"DeepSeek HTTP {response.status_code}",
                        retryable=False,
                    )
                if response.status_code == 429:
                    raise LLMProviderError("DeepSeek rate limited", rate_limited=True)
                if is_retryable_status(response.status_code):
                    raise LLMProviderError(f"DeepSeek HTTP {response.status_code}")
                if response.status_code >= 400:
                    raise LLMProviderError(f"DeepSeek HTTP {response.status_code}")
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {}).get("content") or ""
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    if delta:
                        yield delta
        except httpx.TimeoutException as exc:
            raise LLMProviderError("DeepSeek stream timed out", timeout=True) from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("DeepSeek stream transport error") from exc
