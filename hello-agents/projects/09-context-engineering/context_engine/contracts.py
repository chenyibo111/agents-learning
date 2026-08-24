"""Serializable contracts used by the context compiler."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContextItem:
    """A candidate piece of information for one model call."""

    id: str
    kind: str
    text: str
    priority: int = 0
    relevance: float = 0.0
    recency: float = 0.0
    required: bool = False
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SelectedContext:
    """One selected item after filtering and Token counting."""

    item: ContextItem
    text: str
    token_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = self.item.to_dict()
        payload.update(
            {
                "item_id": self.item.id,
                "text": self.text,
                "token_count": self.token_count,
            }
        )
        return payload


@dataclass(frozen=True)
class DroppedContext:
    """A candidate that was intentionally omitted, with an explanation."""

    item_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextBuildResult:
    """The auditable output of one context compilation."""

    selected: list[SelectedContext] = field(default_factory=list)
    dropped: list[DroppedContext] = field(default_factory=list)
    rendered: str = ""
    token_count: int = 0
    tokenizer_mode: str = ""
    redacted_fields: list[str] = field(default_factory=list)
    injection_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": [item.to_dict() for item in self.selected],
            "dropped": [item.to_dict() for item in self.dropped],
            "rendered": self.rendered,
            "token_count": self.token_count,
            "tokenizer_mode": self.tokenizer_mode,
            "redacted_fields": list(self.redacted_fields),
            "injection_warnings": list(self.injection_warnings),
        }
