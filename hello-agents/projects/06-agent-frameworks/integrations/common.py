"""Framework-neutral async contracts used by real Agent adapters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any, Awaitable, Callable, Protocol


class AdapterError(RuntimeError):
    """Base error for adapter and provider failures."""


class ProviderError(AdapterError):
    """Normalized provider error with an optional HTTP status code."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class MissingOptionalDependency(AdapterError):
    """Raised when a selected optional framework is not installed."""

    def __init__(self, dependency: str, install_hint: str):
        super().__init__(
            f"缺少可选依赖 {dependency}；请执行：{install_hint}"
        )
        self.dependency = dependency
        self.install_hint = install_hint


class RunCancelled(AdapterError):
    """Raised when the caller cancels an Agent run."""


class RunTimeout(AdapterError):
    """Raised when an adapter or node exceeds its timeout."""


@dataclass
class AgentMessage:
    """The normalized message exchanged by every async adapter."""

    sender: str
    recipient: str
    content: str
    role: str = "assistant"
    usage_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        json.dumps(payload, ensure_ascii=False)
        return payload


@dataclass(frozen=True)
class AdapterCapabilities:
    """Capabilities that an adapter can truthfully expose."""

    supports_streaming: bool = False
    supports_interrupt: bool = False
    supports_checkpoint: bool = False
    supports_cancellation: bool = True


@dataclass
class AgentEvent:
    """A normalized lifecycle or streaming event."""

    run_id: str
    node: str
    phase: str
    timestamp: float
    duration_ms: float | None = None
    usage_tokens: int | None = None
    attempt: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        json.dumps(payload, ensure_ascii=False)
        return payload


EventSink = Callable[[AgentEvent], Awaitable[None] | None]


class CancellationToken(Protocol):
    """Small cancellation boundary shared by adapters and Runtime."""

    def is_cancelled(self) -> bool:
        ...

    def raise_if_cancelled(self) -> None:
        ...


class AsyncAgentAdapter(Protocol):
    """Protocol implemented by real LLM and framework adapters."""

    capabilities: AdapterCapabilities

    async def respond(
        self,
        agent: str,
        prompt: str,
        *,
        on_event: EventSink | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> AgentMessage:
        ...


def redact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return metadata with common credential fields replaced."""

    sensitive = {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "password",
        "token",
    }
    return {
        key: "[REDACTED]" if key.lower() in sensitive else value
        for key, value in metadata.items()
    }
