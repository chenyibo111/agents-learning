"""Minimal JSON protocol data structures for the lesson 23 demo."""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union


INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
EXECUTION_ERROR = -32001


class ProtocolError(Exception):
    """A stable error that can safely cross the protocol boundary."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass(frozen=True)
class ProtocolRequest:
    request_id: Any
    method: str
    params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.request_id,
            "method": self.method,
            "params": self.params,
        }


@dataclass(frozen=True)
class ProtocolResponse:
    request_id: Any
    result: Any = None
    error: Optional[Dict[str, Any]] = None

    @classmethod
    def success(cls, request_id: Any, result: Any) -> "ProtocolResponse":
        return cls(request_id=request_id, result=result)

    @classmethod
    def failure(
        cls,
        request_id: Any,
        code: int,
        message: str,
        data: Any = None,
    ) -> "ProtocolResponse":
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return cls(request_id=request_id, error=error)

    def to_dict(self) -> Dict[str, Any]:
        if self.error is not None:
            return {"id": self.request_id, "error": self.error}
        return {"id": self.request_id, "result": self.result}


def encode_message(message: Dict[str, Any]) -> str:
    """Encode one protocol object without serializing Python exceptions."""
    if not isinstance(message, dict):
        raise ProtocolError(INVALID_REQUEST, "协议消息必须是对象")
    try:
        return json.dumps(message, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ProtocolError(INVALID_REQUEST, "协议消息不可序列化") from error


def decode_message(payload: str) -> Dict[str, Any]:
    try:
        message = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise ProtocolError(INVALID_REQUEST, "协议消息不是合法 JSON") from error
    if not isinstance(message, dict):
        raise ProtocolError(INVALID_REQUEST, "协议消息必须是对象")
    return message


def decode_request(payload: Union[str, Dict[str, Any]]) -> ProtocolRequest:
    message = decode_message(payload) if isinstance(payload, str) else payload
    if not isinstance(message, dict):
        raise ProtocolError(INVALID_REQUEST, "协议请求必须是对象")
    if "id" not in message:
        raise ProtocolError(INVALID_REQUEST, "协议请求缺少 id")
    method = message.get("method")
    params = message.get("params")
    if not isinstance(method, str) or not method.strip():
        raise ProtocolError(INVALID_REQUEST, "协议请求缺少有效 method")
    if not isinstance(params, dict):
        raise ProtocolError(INVALID_REQUEST, "协议请求的 params 必须是对象")
    return ProtocolRequest(
        request_id=message["id"],
        method=method,
        params=params,
    )
