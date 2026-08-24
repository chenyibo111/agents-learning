"""Small, explicit protocol-version negotiation helper."""

from __future__ import annotations

from collections.abc import Iterable

from .errors import ErrorCode, ProtocolError


def negotiate_version(requested: str, supported: Iterable[str]) -> str:
    supported_versions = tuple(supported)
    if requested in supported_versions:
        return requested
    raise ProtocolError(
        ErrorCode.VERSION_MISMATCH,
        "协议版本不匹配",
        {"requested": requested, "supported": list(supported_versions)},
    )
