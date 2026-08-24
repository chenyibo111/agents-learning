"""Wire contracts for JSON-RPC, MCP capabilities and A2A tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping

from .errors import ErrorCode, ProtocolError


JsonValue = Any


@dataclass(frozen=True)
class JsonRpcRequest:
    id: str | int
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    jsonrpc: str = "2.0"

    def __post_init__(self) -> None:
        if self.jsonrpc != "2.0":
            raise ProtocolError(ErrorCode.INVALID_REQUEST, "jsonrpc 必须是 2.0")
        if isinstance(self.id, bool) or not isinstance(self.id, (str, int)):
            raise ProtocolError(ErrorCode.INVALID_REQUEST, "request id 必须是字符串或整数")
        if not self.method or not isinstance(self.method, str):
            raise ProtocolError(ErrorCode.INVALID_REQUEST, "method 必须是非空字符串")
        if not isinstance(self.params, dict):
            raise ProtocolError(ErrorCode.INVALID_PARAMS, "params 必须是 JSON 对象")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "JsonRpcRequest":
        if not isinstance(payload, Mapping):
            raise ProtocolError(ErrorCode.INVALID_REQUEST, "请求必须是 JSON 对象")
        if "id" not in payload or "method" not in payload:
            raise ProtocolError(ErrorCode.INVALID_REQUEST, "请求缺少 id 或 method")
        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ProtocolError(ErrorCode.INVALID_PARAMS, "params 必须是 JSON 对象")
        return cls(
            id=payload["id"],
            method=payload["method"],
            params=dict(params),
            jsonrpc=payload.get("jsonrpc", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params,
        }


@dataclass(frozen=True)
class JsonRpcResponse:
    id: str | int | None
    result: Any = None
    error: dict[str, Any] | None = None
    jsonrpc: str = "2.0"

    @classmethod
    def success(cls, request_id: str | int | None, result: Any) -> "JsonRpcResponse":
        return cls(id=request_id, result=result)

    @classmethod
    def failure(cls, request_id: str | int | None, error: ProtocolError | dict[str, Any]) -> "JsonRpcResponse":
        return cls(id=request_id, error=error.to_dict() if isinstance(error, ProtocolError) else error)

    def to_dict(self) -> dict[str, Any]:
        if self.error is not None:
            return {"jsonrpc": self.jsonrpc, "id": self.id, "error": self.error}
        return {"jsonrpc": self.jsonrpc, "id": self.id, "result": self.result}


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], Any] = field(repr=False, compare=False)
    required_scopes: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    def validate_arguments(self, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ProtocolError(ErrorCode.INVALID_PARAMS, "工具 arguments 必须是 JSON 对象")
        schema = self.input_schema or {"type": "object"}
        if schema.get("type", "object") != "object":
            raise ProtocolError(ErrorCode.INVALID_PARAMS, "工具 schema 顶层必须是 object")
        required = schema.get("required", [])
        missing = [name for name in required if name not in arguments]
        if missing:
            raise ProtocolError(ErrorCode.INVALID_PARAMS, "缺少工具参数", {"missing": missing})
        for name, value in arguments.items():
            property_schema = schema.get("properties", {}).get(name)
            if property_schema and not _matches_json_type(value, property_schema.get("type")):
                raise ProtocolError(
                    ErrorCode.INVALID_PARAMS,
                    f"工具参数 {name} 类型错误",
                    {"expected": property_schema.get("type")},
                )
        return arguments


@dataclass(frozen=True)
class ResourceDefinition:
    uri: str
    description: str
    content: str | Callable[[], str]
    mime_type: str = "text/plain"
    required_scopes: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict[str, Any]:
        return {"uri": self.uri, "name": self.uri, "description": self.description, "mimeType": self.mime_type}

    def read(self) -> str:
        return self.content() if callable(self.content) else self.content


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class TaskEnvelope:
    task_id: str
    capability: str
    input: dict[str, Any]
    version: str = "1.0"
    status: TaskState = TaskState.SUBMITTED
    created_at: float = 0.0
    deadline_at: float | None = None
    result: Any = None
    error: dict[str, Any] | None = None
    idempotency_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": "a2a",
            "version": self.version,
            "task_id": self.task_id,
            "capability": self.capability,
            "input": self.input,
            "status": self.status.value,
            "created_at": self.created_at,
        }
        if self.deadline_at is not None:
            payload["deadline_at"] = self.deadline_at
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        if self.idempotency_key is not None:
            payload["idempotency_key"] = self.idempotency_key
        return payload


def _matches_json_type(value: Any, expected: str | None) -> bool:
    if expected is None:
        return True
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return False
