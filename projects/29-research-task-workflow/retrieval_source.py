"""Load and compose the retrievers implemented in lesson 28."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Sequence

from state import SearchResult


LESSON_28_DIR = Path(__file__).resolve().parents[1] / "28-document-retrieval"
DEFAULT_KNOWLEDGE_DIR = LESSON_28_DIR / "knowledge"
DEFAULT_VECTOR_STORE_DIR = LESSON_28_DIR / "vector_store"


def _lesson_28_modules() -> tuple[Any, Any, Any]:
    module_path = str(LESSON_28_DIR)
    if module_path not in sys.path:
        sys.path.insert(0, module_path)
    from ingest import load_chunks
    from retrievers import KeywordRetriever, VectorRetriever

    return load_chunks, KeywordRetriever, VectorRetriever


class CombinedRetriever:
    """Merge keyword and vector results while preserving the common result shape."""

    def __init__(self, retrievers: Sequence[Any]):
        self.retrievers = list(retrievers)

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        merged: dict[str, SearchResult] = {}
        for retriever in self.retrievers:
            for item in retriever.search(query, top_k=top_k):
                current = merged.get(item["chunk_id"])
                if current is None or item["score"] > current["score"]:
                    merged[item["chunk_id"]] = item
        return sorted(
            merged.values(), key=lambda item: (-item["score"], item["chunk_id"])
        )[: max(1, int(top_k))]


def build_retriever(
    mode: str,
    knowledge_dir: str | Path = DEFAULT_KNOWLEDGE_DIR,
    persist_dir: str | Path = DEFAULT_VECTOR_STORE_DIR,
    rebuild: bool = False,
) -> Any:
    load_chunks, keyword_cls, vector_cls = _lesson_28_modules()
    chunks = load_chunks(knowledge_dir)
    if not chunks:
        raise ValueError(f"知识库为空：{knowledge_dir}")
    if mode == "keyword":
        return keyword_cls(chunks)
    if mode == "vector":
        return vector_cls.from_local(chunks, str(persist_dir), rebuild=rebuild)
    if mode == "both":
        return CombinedRetriever(
            [
                keyword_cls(chunks),
                vector_cls.from_local(chunks, str(persist_dir), rebuild=rebuild),
            ]
        )
    raise ValueError(f"未知检索模式：{mode}")
