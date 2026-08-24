"""Official AgentScope 1.x adapter with message-queue streaming."""

from __future__ import annotations

import asyncio
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
    RunCancelled,
)


def load_agentscope_sdk() -> SimpleNamespace:
    """Load AgentScope 1.x entry points lazily."""

    try:
        from agentscope.agent import ReActAgent
        from agentscope.formatter import OpenAIChatFormatter
        from agentscope.message import Msg
        from agentscope.model import OpenAIChatModel
    except ImportError as exc:
        raise MissingOptionalDependency(
            "agentscope==1.0.21 和 mcp==1.29.0",
            "pip install -r requirements-agentscope.txt",
        ) from exc
    return SimpleNamespace(
        ReActAgent=ReActAgent,
        OpenAIChatFormatter=OpenAIChatFormatter,
        Msg=Msg,
        OpenAIChatModel=OpenAIChatModel,
    )


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _text_content(value: Any) -> str:
    getter = getattr(value, "get_text_content", None)
    if callable(getter):
        text = getter()
        return str(text or "")

    content = _field(value, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
            else:
                parts.append(str(_field(block, "text", "") or ""))
        return "".join(parts)
    return str(content or "")


def _usage_tokens(value: Any) -> int:
    usage = _field(value, "usage", None)
    if usage is not None:
        input_tokens = _field(usage, "input_tokens", None)
        output_tokens = _field(usage, "output_tokens", None)
        if input_tokens is not None or output_tokens is not None:
            return int(input_tokens or 0) + int(output_tokens or 0)
        total = _field(usage, "total_tokens", None)
        if total is not None:
            return int(total)

    messages = _field(value, "messages", None)
    if messages:
        return _usage_tokens(messages[-1])
    return 0


class AgentScopeAdapter(AsyncAgentAdapter):
    """Adapt AgentScope ReActAgent to the course async message contract."""

    capabilities = AdapterCapabilities(
        supports_streaming=True,
        supports_interrupt=False,
        supports_checkpoint=False,
        supports_cancellation=True,
    )

    def __init__(
        self,
        *,
        model: Any,
        formatter: Any,
        system: str = "你是一个严谨的 Agent。",
        stream: bool = False,
        agent_factory: Any | None = None,
        message_factory: Any | None = None,
        api_key_for_redaction: str = "",
    ):
        self.model = model
        self.formatter = formatter
        self.system = system
        self.stream = stream
        self.agent_factory = agent_factory
        self.message_factory = message_factory
        self._api_key_for_redaction = api_key_for_redaction

    @classmethod
    def from_environment(
        cls,
        *,
        system: str = "你是一个严谨的 Agent。",
        stream: bool = False,
    ) -> "AgentScopeAdapter":
        sdk = load_agentscope_sdk()
        from common.llm import load_config

        config = load_config()
        model = sdk.OpenAIChatModel(
            model_name=config.model,
            api_key=config.api_key,
            stream=stream,
            client_kwargs={"base_url": config.base_url},
            generate_kwargs={"temperature": 0},
        )
        return cls(
            model=model,
            formatter=sdk.OpenAIChatFormatter(),
            system=system,
            stream=stream,
            agent_factory=sdk.ReActAgent,
            message_factory=sdk.Msg,
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
        sdk = None
        if self.agent_factory is None or self.message_factory is None:
            sdk = load_agentscope_sdk()
        agent_factory = self.agent_factory or sdk.ReActAgent
        message_factory = self.message_factory or sdk.Msg
        agent_instance = agent_factory(
            name=agent,
            sys_prompt=self.system,
            model=self.model,
            formatter=self.formatter,
        )
        user_message = message_factory(
            name="user",
            content=prompt,
            role="user",
        )

        try:
            if self.stream and hasattr(agent_instance, "set_msg_queue_enabled"):
                result = await self._respond_stream(
                    agent_instance,
                    user_message,
                    agent,
                    on_event=on_event,
                    cancel_token=cancel_token,
                )
            else:
                result = await agent_instance(user_message)
                self._raise_if_cancelled(cancel_token)
                if self.stream:
                    await self._emit_text(
                        on_event,
                        agent,
                        _text_content(result),
                    )

            self._raise_if_cancelled(cancel_token)
            return AgentMessage(
                sender=agent,
                recipient="runtime",
                content=_text_content(result),
                usage_tokens=_usage_tokens(result),
                metadata={"framework": "agentscope", "agent": agent},
            )
        except RunCancelled:
            raise
        except Exception as exc:
            status_code = _field(exc, "status_code", None)
            raise ProviderError(
                self._safe_error_text(exc),
                status_code=int(status_code) if status_code is not None else None,
            ) from exc

    async def _respond_stream(
        self,
        agent_instance: Any,
        user_message: Any,
        agent: str,
        *,
        on_event: EventSink | None,
        cancel_token: CancellationToken | None,
    ) -> Any:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        agent_instance.set_msg_queue_enabled(True, queue)
        task = asyncio.create_task(agent_instance(user_message))
        previous = ""
        try:
            while True:
                self._raise_if_cancelled(cancel_token)
                if task.done() and queue.empty():
                    break
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue

                message = item[0] if isinstance(item, tuple) else item
                text = _text_content(message)
                delta = (
                    text[len(previous):]
                    if previous and text.startswith(previous)
                    else text
                )
                previous = text
                if delta:
                    await self._emit_text(on_event, agent, delta)

            return await task
        except BaseException:
            if not task.done():
                task.cancel()
            raise
        finally:
            agent_instance.set_msg_queue_enabled(False)

    async def _emit_text(
        self,
        sink: EventSink | None,
        agent: str,
        text: str,
    ) -> None:
        if not text or sink is None:
            return
        event = AgentEvent(
            run_id="",
            node=agent,
            phase="message_delta",
            timestamp=time(),
            metadata={"delta": text, "framework": "agentscope"},
        )
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
        close = getattr(self.model, "close", None)
        if close is None:
            client = getattr(self.model, "client", None)
            close = getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result
