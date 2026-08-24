"""Replaceable offline retrievers with one tenant-aware search contract."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from .contracts import Document, RetrievalHit


def tokenize(value: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", value.lower())


class Retriever(Protocol):
    @property
    def version(self) -> int:
        ...

    def search(self, query: str, *, tenant_id: str, top_k: int = 5) -> list[RetrievalHit]:
        ...

    def add(self, document: Document) -> None:
        ...

    def delete(self, document_id: str, *, tenant_id: str) -> bool:
        ...


class _BaseRetriever:
    def __init__(self, documents: list[Document] | None = None):
        self._documents: dict[str, Document] = {
            document.id: document for document in (documents or [])
        }
        self._version = 1

    @property
    def version(self) -> int:
        return self._version

    def add(self, document: Document) -> None:
        self._documents[document.id] = document
        self._version += 1

    def delete(self, document_id: str, *, tenant_id: str) -> bool:
        document = self._documents.get(document_id)
        if document is None or document.tenant_id != tenant_id:
            return False
        del self._documents[document_id]
        self._version += 1
        return True

    def _tenant_documents(self, tenant_id: str) -> list[Document]:
        return [
            document
            for document in self._documents.values()
            if document.tenant_id == tenant_id
        ]

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if top_k < 1:
            raise ValueError("top_k 必须大于 0")

    def retrieve(self, query: str, *, tenant_id: str, top_k: int = 5) -> list[RetrievalHit]:
        return self.search(query, tenant_id=tenant_id, top_k=top_k)


class KeywordRetriever(_BaseRetriever):
    """Character/term-overlap retriever that works without external packages."""

    def search(self, query: str, *, tenant_id: str, top_k: int = 5) -> list[RetrievalHit]:
        self._validate_top_k(top_k)
        query_tokens = set(tokenize(query))
        if not query_tokens:
            return []
        ranked: list[tuple[float, Document]] = []
        for document in self._tenant_documents(tenant_id):
            document_tokens = set(tokenize(document.text))
            score = len(query_tokens & document_tokens) / len(query_tokens)
            if score > 0:
                ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        return [
            RetrievalHit(document=document, score=score, rank=index)
            for index, (score, document) in enumerate(ranked[:top_k], start=1)
        ]


class VectorRetriever(_BaseRetriever):
    """Deterministic bag-of-tokens cosine retriever for offline experiments."""

    @staticmethod
    def _vector(text: str) -> Counter[str]:
        return Counter(tokenize(text))

    @staticmethod
    def _cosine(left: Counter[str], right: Counter[str]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(left[token] * right[token] for token in left.keys() & right.keys())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0

    def search(self, query: str, *, tenant_id: str, top_k: int = 5) -> list[RetrievalHit]:
        self._validate_top_k(top_k)
        query_vector = self._vector(query)
        if not query_vector:
            return []
        ranked: list[tuple[float, Document]] = []
        for document in self._tenant_documents(tenant_id):
            score = self._cosine(query_vector, self._vector(document.text))
            if score > 0:
                ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1].id))
        return [
            RetrievalHit(document=document, score=score, rank=index)
            for index, (score, document) in enumerate(ranked[:top_k], start=1)
        ]


class HybridRetriever(_BaseRetriever):
    """Fuse keyword and vector rankings with Reciprocal Rank Fusion."""

    def __init__(self, documents: list[Document] | None = None, *, rrf_k: int = 60):
        super().__init__(documents)
        if rrf_k < 1:
            raise ValueError("rrf_k 必须大于 0")
        self.rrf_k = rrf_k
        self._keyword = KeywordRetriever(documents)
        self._vector = VectorRetriever(documents)

    @property
    def version(self) -> int:
        return max(self._version, self._keyword.version, self._vector.version)

    def add(self, document: Document) -> None:
        super().add(document)
        self._keyword.add(document)
        self._vector.add(document)

    def delete(self, document_id: str, *, tenant_id: str) -> bool:
        deleted = super().delete(document_id, tenant_id=tenant_id)
        if deleted:
            self._keyword.delete(document_id, tenant_id=tenant_id)
            self._vector.delete(document_id, tenant_id=tenant_id)
        return deleted

    def search(self, query: str, *, tenant_id: str, top_k: int = 5) -> list[RetrievalHit]:
        self._validate_top_k(top_k)
        candidate_limit = max(top_k, 10)
        keyword_hits = self._keyword.search(
            query, tenant_id=tenant_id, top_k=candidate_limit
        )
        vector_hits = self._vector.search(
            query, tenant_id=tenant_id, top_k=candidate_limit
        )
        documents = {
            hit.id: hit.document for hit in [*keyword_hits, *vector_hits]
        }
        scores: dict[str, float] = {}
        for hit in keyword_hits:
            scores[hit.id] = scores.get(hit.id, 0.0) + 1 / (self.rrf_k + hit.rank)
        for hit in vector_hits:
            scores[hit.id] = scores.get(hit.id, 0.0) + 1 / (self.rrf_k + hit.rank)
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:top_k]
        return [
            RetrievalHit(document=documents[document_id], score=score, rank=index)
            for index, (document_id, score) in enumerate(ranked, start=1)
        ]
