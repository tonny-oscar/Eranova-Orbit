"""Provider-neutral AI gateway.

NOVA's business logic talks only to ``Provider``. Adding a vendor means adding
an adapter here; nothing else changes. API keys stay server-side.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings, get_settings


class ProviderError(Exception):
    """Safe-to-show provider failure."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]
    raw_arguments: str = ""


@dataclass
class Completion:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    latency_ms: int = 0


@dataclass(frozen=True)
class Capabilities:
    tool_calling: bool
    streaming: bool
    json_output: bool
    context_tokens: int | None


class Provider:
    name = "none"
    capabilities = Capabilities(
        tool_calling=False, streaming=False, json_output=False, context_tokens=None
    )

    @property
    def model(self) -> str:
        return ""

    async def complete(
        self, messages: list[dict], tools: list[dict], *, max_tokens: int, temperature: float
    ) -> Completion:
        raise NotImplementedError


_transport: httpx.AsyncBaseTransport | None = None


def set_transport(transport: httpx.AsyncBaseTransport | None) -> None:
    """Tests inject a mock transport here."""
    global _transport
    _transport = transport


class OpenAICompatibleProvider(Provider):
    """Any ``/chat/completions`` API with OpenAI-style tool calling
    (OpenAI, Azure OpenAI-compatible gateways, OpenRouter, Groq, Together, Ollama, vLLM...)."""

    name = "openai_compatible"
    capabilities = Capabilities(
        tool_calling=True, streaming=False, json_output=True, context_tokens=None
    )
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, settings: Settings):
        self._settings = settings

    @property
    def model(self) -> str:
        return self._settings.nova_model

    async def complete(self, messages, tools, *, max_tokens, temperature) -> Completion:
        s = self._settings
        payload: dict[str, Any] = {
            "model": s.nova_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Content-Type": "application/json"}
        if s.nova_api_key:
            headers["Authorization"] = f"Bearer {s.nova_api_key.get_secret_value()}"
        url = s.nova_base_url.rstrip("/") + "/chat/completions"
        started = time.monotonic()
        last_error = "The AI provider did not respond."
        async with httpx.AsyncClient(
            timeout=s.nova_timeout_seconds, transport=_transport
        ) as client:
            for attempt in range(3):
                try:
                    response = await client.post(url, json=payload, headers=headers)
                except httpx.TimeoutException:
                    last_error = "The AI provider timed out."
                except httpx.HTTPError:
                    last_error = "Could not reach the AI provider."
                else:
                    if response.status_code < 400:
                        return self._parse(
                            response.json(), int((time.monotonic() - started) * 1000)
                        )
                    if response.status_code in (401, 403):
                        raise ProviderError(
                            "The AI provider rejected the API key. Check NOVA_API_KEY."
                        )
                    if response.status_code not in self.RETRY_STATUSES:
                        raise ProviderError(
                            f"The AI provider returned an error (HTTP {response.status_code})."
                        )
                    last_error = (
                        "The AI provider is rate limiting requests."
                        if response.status_code == 429
                        else f"The AI provider is unavailable (HTTP {response.status_code})."
                    )
                if attempt < 2:
                    await asyncio.sleep(0.5 * 2**attempt)
        raise ProviderError(last_error)

    def _parse(self, body: dict, latency_ms: int) -> Completion:
        try:
            choice = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("The AI provider returned an unexpected response.") from exc
        calls = []
        for raw in choice.get("tool_calls") or []:
            fn = raw.get("function") or {}
            text = fn.get("arguments") or "{}"
            try:
                args = json.loads(text) if isinstance(text, str) else dict(text)
            except (ValueError, TypeError):
                args = {"__invalid__": text[:500] if isinstance(text, str) else ""}
            if not isinstance(args, dict):
                args = {"__invalid__": str(args)[:500]}
            calls.append(
                ToolCall(
                    id=str(raw.get("id") or f"call_{len(calls)}"),
                    name=str(fn.get("name", "")),
                    arguments=args,
                    raw_arguments=text if isinstance(text, str) else json.dumps(text),
                )
            )
        usage = body.get("usage") or {}
        return Completion(
            content=choice.get("content") or "",
            tool_calls=calls,
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            model=str(body.get("model") or self.model),
            latency_ms=latency_ms,
        )


def get_provider(settings: Settings | None = None) -> Provider | None:
    """The configured provider, or None for basic (no model) mode."""
    settings = settings or get_settings()
    if settings.nova_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings)
    return None


def estimate_cost(settings: Settings, prompt_tokens: int, completion_tokens: int) -> float | None:
    if settings.nova_cost_input_per_1k is None or settings.nova_cost_output_per_1k is None:
        return None
    return round(
        prompt_tokens / 1000 * settings.nova_cost_input_per_1k
        + completion_tokens / 1000 * settings.nova_cost_output_per_1k,
        6,
    )
