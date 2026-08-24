"""Token-to-scope authorization without logging credentials."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .errors import ErrorCode, ProtocolError


@dataclass(frozen=True)
class AuthContext:
    principal: str = "anonymous"
    scopes: frozenset[str] = field(default_factory=frozenset)


class Authorizer:
    def __init__(self, tokens: Mapping[str, tuple[str, Iterable[str]] | Iterable[str]] | None = None):
        self._tokens: dict[str, AuthContext] = {}
        for token, value in (tokens or {}).items():
            if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], str):
                principal, scopes = value
            else:
                principal, scopes = token, value
            self._tokens[token] = AuthContext(principal, frozenset(scopes))

    def authenticate(self, token: str | None) -> AuthContext:
        if not token:
            return AuthContext()
        context = self._tokens.get(token)
        if context is None:
            raise ProtocolError(ErrorCode.AUTH_REQUIRED, "认证失败")
        return context

    @staticmethod
    def require(context: AuthContext, required_scopes: Iterable[str]) -> None:
        required = frozenset(required_scopes)
        missing = sorted(required - context.scopes)
        if missing:
            raise ProtocolError(ErrorCode.FORBIDDEN, "权限不足", {"missing_scopes": missing})
