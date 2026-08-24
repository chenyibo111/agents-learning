"""Small in-memory retrieval cache with automatic index-version isolation."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from .contracts import RetrievalHit


class RetrievalCache:
    """Cache retrieval results without allowing stale index versions to match."""

    def __init__(self, *, max_entries: int = 128):
        if max_entries < 1:
            raise ValueError("max_entries 必须大于 0")
        self.max_entries = max_entries
        self._entries: OrderedDict[tuple[Any, ...], list[RetrievalHit]] = OrderedDict()

    def search(
        self,
        retriever: Any,
        query: str,
        *,
        tenant_id: str,
        top_k: int = 5,
    ) -> tuple[list[RetrievalHit], bool]:
        key = (
            retriever.__class__.__name__,
            retriever.version,
            tenant_id,
            query.strip(),
            top_k,
        )
        if key in self._entries:
            self._entries.move_to_end(key)
            return list(self._entries[key]), True

        hits = retriever.search(query, tenant_id=tenant_id, top_k=top_k)
        self._entries[key] = list(hits)
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)
        return list(hits), False

    def clear(self) -> None:
        self._entries.clear()
