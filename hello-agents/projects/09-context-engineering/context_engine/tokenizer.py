"""Model-aware Token counting with an explicit offline fallback."""

from __future__ import annotations

import math
from typing import Any


class TokenCounter:
    """Use tiktoken when available, otherwise expose a deterministic estimate."""

    def __init__(
        self,
        *,
        model: str = "gpt-4o-mini",
        force_fallback: bool = False,
    ):
        self.model = model
        self._encoding: Any | None = None
        self.mode = "heuristic"
        if not force_fallback:
            try:
                import tiktoken

                try:
                    self._encoding = tiktoken.encoding_for_model(model)
                except KeyError:
                    self._encoding = tiktoken.get_encoding("cl100k_base")
                self.mode = "tiktoken"
            except Exception:
                # tiktoken may be installed while its encoding table is not
                # cached yet; loading it can attempt a network request.
                # Offline Demo mode must degrade to the explicit heuristic.
                self._encoding = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return max(1, math.ceil(len(text) / 4))

    def count_messages(self, messages: list[dict[str, Any]]) -> int:
        return sum(
            self.count(str(message.get("role", "")))
            + self.count(str(message.get("content", "")))
            for message in messages
        )
