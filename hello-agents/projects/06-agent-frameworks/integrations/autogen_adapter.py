"""Official Microsoft AutoGen AgentChat adapter.

All AutoGen imports are lazy so the offline lesson does not depend on the SDK.
"""

from __future__ import annotations

import inspect
from time import time
from types import SimpleNamespace
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


def load_autogen_sdk() -> SimpleNamespace:
    """Load the current official AgentChat/OpenAI extension entry points."""

    try:
        from autogen_agentchat.agents import AssistantAgent
        from autogen_core.models import ModelFamily
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError as exc:
        raise MissingOptionalDependency(
            "autogen-agentchat 和 autogen-ext[openai]",
            "pip install -r requirements-autogen.txt",
        ) from exc
    return SimpleNamespace(
        AssistantAgent=AssistantAgent,
        ModelFamily=ModelFamily,
        OpenAIChatCompletionClient=OpenAIChatCompletionClient,
    )


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _usage_tokens(value: Any) -> int:
    usage = _field(value, "models_usage", None) or _field(value, "usage", None)
    if usage is None:
        messages = _field(value, "messages", None)
        if messages:
            return _usage_tokens(messages[-1])
    if usage is None:
        return 0
    total = _field(usage, "total_tokens", None)
    if total is not None:
        return int(total)
    return int(_field(usage, "prompt_tokens", 0) or 0) + int(
        _field(usage, "completion_tokens", 0) or 0
    )


def _content(value: Any) -> str:
    messages = _field(value, "messages", None)
    if messages:
        return _content(messages[-1])
    content = _field(value, "content", "")
    if content is None:
        return ""
    return str(content)


class AutoGenAdapter(AsyncAgentAdapter):
    """Adapt AutoGen AssistantAgent to the course async message contract."""

    capabilities = AdapterCapabilities(
        supports_streaming=True,
        supports_interrupt=False,
        supports_checkpoint=False,
        supports_cancellation=True,
    )

    def __init__(
        self,
        *,
        model_client: Any,
        system: str = "你是一个严谨的 Agent。",
        stream: bool = False,
        agent_factory: Any | None = None,
        api_key_for_redaction: str = "",
    ):
        self.model_client = model_client
        self.system = system
        self.stream = stream
        self.agent_factory = agent_factory
        self._api_key_for_redaction = api_key_for_redaction

    @classmethod
    def from_environment(
        cls,
        *,
        system: str = "你是一个严谨的 Agent。",
        stream: bool = False,
    ) -> "AutoGenAdapter":
        sdk = load_autogen_sdk()
        from common.llm import load_config

        config = load_config()
        model_client = sdk.OpenAIChatCompletionClient(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            model_info={
                "vision": False,
                "function_calling": False,
                "json_output": False,
                "structured_output": False,
                "family": sdk.ModelFamily.UNKNOWN,
            },
        )
        return cls(
            model_client=model_client,
            system=system,
            stream=stream,
            agent_factory=sdk.AssistantAgent,
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
        if self.agent_factory is None:
            sdk = load_autogen_sdk()
            agent_factory = sdk.AssistantAgent
        else:
            agent_factory = self.agent_factory

        assistant = agent_factory(
            name=agent,
            model_client=self.model_client,
            system_message=self.system,
        )
        try:
            if self.stream:
                return await self._respond_stream(
                    assistant,
                    agent,
                    prompt,
                    on_event=on_event,
                    cancel_token=cancel_token,
                )
            result = await assistant.run(task=prompt)
            self._raise_if_cancelled(cancel_token)
            return AgentMessage(
                sender=agent,
                recipient="runtime",
                content=_content(result),
                usage_tokens=_usage_tokens(result),
                metadata={"framework": "autogen", "agent": agent},
            )
        except ProviderError:
            raise
        except Exception as exc:
            status_code = _field(exc, "status_code", None)
            raise ProviderError(
                self._safe_error_text(exc),
                status_code=int(status_code) if status_code is not None else None,
            ) from exc

    async def _respond_stream(
        self,
        assistant: Any,
        agent: str,
        prompt: str,
        *,
        on_event: EventSink | None,
        cancel_token: CancellationToken | None,
    ) -> AgentMessage:
        parts: list[str] = []
        usage_tokens = 0
        async for item in assistant.run_stream(task=prompt):
            self._raise_if_cancelled(cancel_token)
            content = _content(item)
            usage_tokens = max(usage_tokens, _usage_tokens(item))
            if not content:
                continue
            parts.append(content)
            await self._emit(
                on_event,
                AgentEvent(
                    run_id="",
                    node=agent,
                    phase="message_delta",
                    timestamp=time(),
                    usage_tokens=usage_tokens,
                    metadata={"delta": content, "framework": "autogen"},
                ),
            )

        self._raise_if_cancelled(cancel_token)
        return AgentMessage(
            sender=agent,
            recipient="runtime",
            content=parts[-1] if parts else "",
            usage_tokens=usage_tokens,
            metadata={"framework": "autogen", "agent": agent},
        )

    @staticmethod
    async def _emit(sink: EventSink | None, event: AgentEvent) -> None:
        if sink is None:
            return
        result = sink(event)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _raise_if_cancelled(cancel_token: CancellationToken | None) -> None:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()

    def _safe_error_text(self, error: Exception) -> str:
        text = str(error)
        if self._api_key_for_redaction:
            text = text.replace(self._api_key_for_redaction, "[REDACTED]")
        return text or error.__class__.__name__

    async def aclose(self) -> None:
        close = getattr(self.model_client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result
