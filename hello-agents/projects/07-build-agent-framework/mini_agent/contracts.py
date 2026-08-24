"""Serializable contracts shared by Model, Policy, Tool and Runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Any

from .errors import InvalidActionError


def _json_payload(value: Any) -> dict[str, Any]:
    payload = asdict(value)
    json.dumps(payload, ensure_ascii=False)
    return payload


@dataclass
class Message:
    role: str
    content: str
    name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _json_payload(self)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name 不能为空")
        if not isinstance(self.arguments, dict):
            raise TypeError("tool arguments 必须是 dict")

    def to_dict(self) -> dict[str, Any]:
        return _json_payload(self)


@dataclass
class Action:
    kind: str
    content: str | None = None
    tool_call: ToolCall | None = None

    def __post_init__(self) -> None:
        if self.kind == "final":
            if self.content is None or self.tool_call is not None:
                raise InvalidActionError("final action 必须只有 content")
        elif self.kind == "tool_call":
            if self.tool_call is None or self.content is not None:
                raise InvalidActionError("tool_call action 必须只有 tool_call")
        else:
            raise InvalidActionError(f"未知 action 类型：{self.kind}")

    def to_dict(self) -> dict[str, Any]:
        return _json_payload(self)


@dataclass
class ModelResponse:
    action: Action
    usage_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.usage_tokens < 0:
            raise ValueError("usage_tokens 不能小于 0")

    def to_dict(self) -> dict[str, Any]:
        return _json_payload(self)


@dataclass
class AgentEvent:
    run_id: str
    step: int
    phase: str
    node: str = "runner"
    duration_ms: float | None = None
    usage_tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _json_payload(self)


@dataclass
class RunResult:
    status: str
    answer: str = ""
    steps: int = 0
    run_id: str = ""
    messages: list[Message] = field(default_factory=list)
    events: list[AgentEvent] = field(default_factory=list)
    error: str = ""
    total_usage_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        json.dumps(payload, ensure_ascii=False)
        return payload
