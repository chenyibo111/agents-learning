"""Stable, JSON-safe protocol errors."""

from __future__ import annotations

from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    AUTH_REQUIRED = -32001
    FORBIDDEN = -32003
    VERSION_MISMATCH = -32004
    TASK_NOT_FOUND = -32005
    INVALID_STATE = -32006
    TIMEOUT = -32007
    CANCELLED = -32008
    IDEMPOTENCY_CONFLICT = -32009
    REPLAY_DETECTED = -32010
    RESOURCE_NOT_FOUND = -32011
    TOOL_NOT_FOUND = -32012
    DUPLICATE_TASK = -32013


class ProtocolError(Exception):
    """An expected protocol failure safe to return to a remote caller."""

    def __init__(self, code: ErrorCode | int, message: str, data: Any = None):
        self.code = int(code)
        self.message = message
        self.data = data
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            payload["data"] = self.data
        return payload
