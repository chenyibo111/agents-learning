"""研究系统的来源、证据、结论、引用和状态 Schema。"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ResearchQuery:
    query_id: str
    question: str
    max_rounds: int = 2
    max_sources: int = 5
    max_tokens: int = 2000
    budget_usd: float = 0.10


@dataclass(frozen=True)
class Source:
    source_id: str
    title: str
    url: str
    author: str
    published_at: str
    content: str
    credibility: float
    fetched_at: datetime
    topic: str
    stance: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["fetched_at"] = self.fetched_at.isoformat()
        return value


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_id: str
    chunk_id: str
    quote: str
    topic: str
    stance: str


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    evidence_ids: tuple[str, ...]
    confidence: float
    uncertain: bool = False


@dataclass(frozen=True)
class Citation:
    citation_id: str
    claim_id: str
    evidence_id: str
    source_id: str


@dataclass(frozen=True)
class ResearchState:
    query: ResearchQuery
    status: str
    round: int = 0
    queries: tuple[str, ...] = ()
    sources: tuple[Source, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    claims: tuple[Claim, ...] = ()
    citations: tuple[Citation, ...] = ()
    warnings: tuple[str, ...] = ()
    tokens_used: int = 0
    cost_usd: float = 0.0
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": asdict(self.query),
            "status": self.status,
            "round": self.round,
            "queries": list(self.queries),
            "sources": [source.to_dict() for source in self.sources],
            "evidence": [asdict(item) for item in self.evidence],
            "claims": [asdict(item) for item in self.claims],
            "citations": [asdict(item) for item in self.citations],
            "warnings": list(self.warnings),
            "tokens_used": self.tokens_used,
            "cost_usd": self.cost_usd,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ResearchState":
        if value.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
            raise ValueError("不支持的研究状态 schema 版本")
        query = ResearchQuery(**value["query"])
        sources = tuple(
            Source(
                **{
                    **item,
                    "fetched_at": datetime.fromisoformat(item["fetched_at"]),
                }
            )
            for item in value["sources"]
        )
        return cls(
            query=query,
            status=value["status"],
            round=value.get("round", 0),
            queries=tuple(value.get("queries", [])),
            sources=sources,
            evidence=tuple(Evidence(**item) for item in value.get("evidence", [])),
            claims=tuple(
                Claim(**{**item, "evidence_ids": tuple(item["evidence_ids"])})
                for item in value.get("claims", [])
            ),
            citations=tuple(Citation(**item) for item in value.get("citations", [])),
            warnings=tuple(value.get("warnings", [])),
            tokens_used=value.get("tokens_used", 0),
            cost_usd=value.get("cost_usd", 0.0),
            schema_version=value.get("schema_version", SCHEMA_VERSION),
        )
