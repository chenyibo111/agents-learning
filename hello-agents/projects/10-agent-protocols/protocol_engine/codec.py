"""JSON encoding and decoding at the protocol boundary."""

from __future__ import annotations

import json
from typing import Any, Mapping

from .contracts import JsonRpcRequest, JsonRpcResponse
from .errors import ErrorCode, ProtocolError


def decode_request(payload: str | bytes | Mapping[str, Any]) -> JsonRpcRequest:
    try:
        data: Any = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    except (TypeError, json.JSONDecodeError) as exc:
        raise ProtocolError(ErrorCode.PARSE_ERROR, "请求不是合法 JSON") from exc
    return JsonRpcRequest.from_dict(data)


def encode_response(response: JsonRpcResponse) -> str:
    return json.dumps(response.to_dict(), ensure_ascii=False, sort_keys=True)
