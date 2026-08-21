"""State and record contracts for the lesson 29 research workflow."""

from __future__ import annotations

from typing import NotRequired, TypedDict


class SearchResult(TypedDict, total=False):
    source: str
    chunk_id: str
    text: str
    score: float
    retriever: str
    distance: float


class EvidenceRecord(TypedDict, total=False):
    claim: str
    source: str
    chunk_id: str
    quote: str
    verified: NotRequired[bool]
    note: NotRequired[str]


class ResearchState(TypedDict, total=False):
    topic: str
    plan: list[str]
    retrieved_chunks: list[SearchResult]
    evidence: list[EvidenceRecord]
    verified_evidence: list[EvidenceRecord]
    status: str
    events: list[str]
