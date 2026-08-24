"""Offline retrieval quality metrics for a small labeled query set."""

from __future__ import annotations

from typing import Any, Iterable


def evaluate_retriever(
    retriever: Any,
    cases: Iterable[dict[str, Any]],
    *,
    tenant_id: str,
    top_k: int = 5,
) -> dict[str, float]:
    if top_k < 1:
        raise ValueError("top_k 必须大于 0")
    rows = list(cases)
    if not rows:
        raise ValueError("评测集不能为空")

    hit_scores: list[float] = []
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    reciprocal_ranks: list[float] = []
    for case in rows:
        relevant = set(case.get("relevant_ids", []))
        if not relevant:
            raise ValueError("每个评测问题必须包含 relevant_ids")
        hits = retriever.search(
            case["query"], tenant_id=tenant_id, top_k=top_k
        )
        returned = [hit.id for hit in hits]
        relevant_count = sum(document_id in relevant for document_id in returned)
        hit_scores.append(float(bool(relevant_count)))
        precision_scores.append(relevant_count / top_k)
        recall_scores.append(relevant_count / len(relevant))
        reciprocal_rank = 0.0
        for rank, document_id in enumerate(returned, start=1):
            if document_id in relevant:
                reciprocal_rank = 1 / rank
                break
        reciprocal_ranks.append(reciprocal_rank)

    count = len(rows)
    return {
        "hit_at_k": sum(hit_scores) / count,
        "precision_at_k": sum(precision_scores) / count,
        "recall_at_k": sum(recall_scores) / count,
        "mrr": sum(reciprocal_ranks) / count,
    }
