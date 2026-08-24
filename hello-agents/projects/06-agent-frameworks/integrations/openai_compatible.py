"""Async OpenAI-compatible chat adapter with optional streaming."""

from __future__ import annotations

import inspect
from time import time
from typing import Any

from integrations.common import (
    AdapterCapabilities,
    AgentEvent,
    AgentMessage,
    AsyncAgentAdapter,
    CancellationToken,
    EventSink,
    MissingOptionalDependency,
    ProviderError,
)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _content_from_response(response: Any) -> str:
    choices = _field(response, "choices", []) or []
    if not choices:
        return ""
    message = _field(choices[0], "message", None)
    content = _field(message, "content", "") or ""
    if isinstance(content, list):
        return "".join(
            str(_field(part, "text", "") or "")
            for part in content
        )
    return str(content)


def _usage_tokens(response: Any) -> int:
    usage = _field(response, "usage", None)
    if usage is None:
        return 0
    total = _field(usage, "total_tokens", None)
    if total is not None:
        return int(total)
    prompt = _field(usage, "prompt_tokens", 0) or 0
    completion = _field(usage, "completion_tokens", 0) or 0
    return int(prompt) + int(completion)


def _delta_from_chunk(chunk: Any) -> str:
    choices = _field(chunk, "choices", []) or []
    if not choices:
        return ""
    delta = _field(choices[0], "delta", None)
    content = _field(delta, "content", "") or ""
    return str(content)


class OpenAICompatibleAdapter(AsyncAgentAdapter):
    """Normalize AsyncOpenAI chat completions to lesson contracts."""

    capabilities = AdapterCapabilities(
        supports_streaming=True,
        supports_interrupt=False,
        supports_checkpoint=False,
        supports_cancellation=True,
    )

    def __init__(
        self,
        *,
        client: Any,
        model: str,
        system: str = "你是一个严谨的 Agent。",
        stream: bool = False,
        temperature: float = 0,
        api_key_for_redaction: str = "",
    ):
        if not model.strip():
            raise ValueError("model 不能为空")
        self.client = client
        self.model = model
        self.system = system
        self.stream = stream
        self.temperature = temperature
        self._api_key_for_redaction = api_key_for_redaction

    @classmethod
    def from_environment(
        cls,
        *,
        system: str = "你是一个严谨的 Agent。",
        stream: bool = False,
    ) -> "OpenAICompatibleAdapter":
        from common.llm import build_async_openai_client

        client, config = build_async_openai_client()
        return cls(
            client=client,
            model=config.model,
            system=system,
            stream=stream,
            api_key_for_redaction=config.api_key,
        )

    async def respond(
        self,
        agent: str,
        prompt: str,
        *,
        on_event: EventSink | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> AgentMessage:
        self._raise_if_cancelled(cancel_token)
        request = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "stream": self.stream,
        }

        try:
            response = await self.client.chat.completions.create(**request)
            if self.stream:
                return await self._consume_stream(
                    agent,
                    response,
                    on_event=on_event,
                    cancel_token=cancel_token,
                )

            self._raise_if_cancelled(cancel_token)
            return AgentMessage(
                sender=agent,
                recipient="runtime",
                content=_content_from_response(response),
                usage_tokens=_usage_tokens(response),
                metadata={"model": self.model},
            )
        except ProviderError:
            raise
        except Exception as exc:
            status_code = _field(exc, "status_code", None)
            raise ProviderError(
                self._safe_error_text(exc),
                status_code=int(status_code) if status_code is not None else None,
            ) from exc

    async def _consume_stream(
        self,
        agent: str,
        response: Any,
        *,
        on_event: EventSink | None,
        cancel_token: CancellationToken | None,
    ) -> AgentMessage:
        parts: list[str] = []
        usage_tokens = 0
        async for chunk in response:
            self._raise_if_cancelled(cancel_token)
            delta = _delta_from_chunk(chunk)
            usage_tokens = max(usage_tokens, _usage_tokens(chunk))
            if not delta:
                continue
            parts.append(delta)
            await self._emit(
                on_event,
                AgentEvent(
                    run_id="",
                    node=agent,
                    phase="message_delta",
                    timestamp=time(),
                    usage_tokens=usage_tokens,
                    metadata={"delta": delta, "model": self.model},
                ),
            )

        self._raise_if_cancelled(cancel_token)
        return AgentMessage(
            sender=agent,
            recipient="runtime",
            content="".join(parts),
            usage_tokens=usage_tokens,
            metadata={"model": self.model},
        )

    @staticmethod
    async def _emit(sink: EventSink | None, event: AgentEvent) -> None:
        if sink is None:
            return
        result = sink(event)
        if inspect.isawaitable(result):
            await result

    def _raise_if_cancelled(self, cancel_token: CancellationToken | None) -> None:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()

    def _safe_error_text(self, error: Exception) -> str:
        text = str(error)
        if self._api_key_for_redaction:
            text = text.replace(self._api_key_for_redaction, "[REDACTED]")
        return text or error.__class__.__name__

    async def aclose(self) -> None:
        close = getattr(self.client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result
