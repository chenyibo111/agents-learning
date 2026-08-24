"""In-memory idempotency records for the local lesson server."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .contracts import JsonRpcResponse
from .errors import ErrorCode, ProtocolError


def request_fingerprint(method: str, params: dict[str, Any]) -> str:
    encoded = json.dumps({"method": method, "params": params}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class IdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[str, tuple[str, JsonRpcResponse]] = {}

    def lookup(self, key: str, fingerprint: str) -> JsonRpcResponse | None:
        record = self._records.get(key)
        if record is None:
            return None
        saved_fingerprint, response = record
        if saved_fingerprint != fingerprint:
            raise ProtocolError(ErrorCode.IDEMPOTENCY_CONFLICT, "幂等键已用于另一请求")
        return response

    def save(self, key: str, fingerprint: str, response: JsonRpcResponse) -> None:
        self._records[key] = (fingerprint, response)
