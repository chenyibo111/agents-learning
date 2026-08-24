"""Evidence formatting and citation validation for grounded answers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .contracts import RetrievalHit


@dataclass(frozen=True)
class CitationValidation:
    valid: bool
    used_labels: list[str] = field(default_factory=list)
    unknown_labels: list[str] = field(default_factory=list)


def evidence_label(rank: int) -> str:
    return f"S{rank}"


def build_evidence(hits: list[RetrievalHit]) -> str:
    lines: list[str] = []
    for hit in hits:
        label = evidence_label(hit.rank)
        document = hit.document
        lines.append(
            f"[{label}] source={document.source}#{document.chunk_id} "
            f"score={hit.score:.4f}\n{document.text}"
        )
    return "\n\n".join(lines)


def evidence_sufficient(hits: list[RetrievalHit], *, min_score: float = 0.0) -> bool:
    return bool(hits) and hits[0].score > min_score


def validate_citations(answer: str, hits: list[RetrievalHit]) -> CitationValidation:
    allowed = {evidence_label(hit.rank) for hit in hits}
    used = list(dict.fromkeys(re.findall(r"\[(S\d+)\]", answer)))
    unknown = [label for label in used if label not in allowed]
    return CitationValidation(
        valid=bool(used) and not unknown,
        used_labels=used,
        unknown_labels=unknown,
    )
