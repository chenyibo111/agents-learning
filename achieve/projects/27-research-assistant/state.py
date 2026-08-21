"""Shared state and record types for lesson 27."""

from typing import TypedDict


class SourceRecord(TypedDict, total=False):
    title: str
    url: str
    summary: str


class EvidenceRecord(TypedDict, total=False):
    claim: str
    source_url: str
    verified: bool
    note: str


class ResearchState(TypedDict, total=False):
    topic: str
    plan: list[str]
    sources: list[SourceRecord]
    evidence: list[EvidenceRecord]
    verified_evidence: list[EvidenceRecord]
    report: str
    status: str
    events: list[str]
    error: str
