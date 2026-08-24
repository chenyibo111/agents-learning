"""TTL-based replay protection for request ids."""

from __future__ import annotations

import time

from .errors import ErrorCode, ProtocolError


class ReplayGuard:
    def __init__(self, ttl_seconds: float = 300.0):
        self.ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}

    def check(self, message_id: str | int, *, now: float | None = None) -> None:
        current = time.time() if now is None else now
        key = str(message_id)
        expired = [item for item, timestamp in self._seen.items() if current - timestamp >= self.ttl_seconds]
        for item in expired:
            del self._seen[item]
        if key in self._seen:
            raise ProtocolError(ErrorCode.REPLAY_DETECTED, "检测到重复请求")
        self._seen[key] = current
