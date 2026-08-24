"""Serializable contracts shared by memory stores and retrievers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Document:
    """A tenant-scoped, citeable knowledge chunk."""

    id: str
    source: str
    chunk_id: str
    text: str
    tenant_id: str = "default"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryItem:
    """A user-scoped long-term memory record."""

    id: str
    tenant_id: str
    user_id: str
    content: str
    kind: str = "fact"
    created_at: float = 0.0
    expires_at: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrievalHit:
    """A document returned by a retriever, with a ranking score."""

    document: Document
    score: float
    rank: int

    @property
    def id(self) -> str:
        return self.document.id

    def to_dict(self) -> dict[str, Any]:
        payload = self.document.to_dict()
        payload.update({"score": self.score, "rank": self.rank})
        return payload
