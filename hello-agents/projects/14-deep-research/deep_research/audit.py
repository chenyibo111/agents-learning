"""引用支持关系审计。"""

from .schemas import ResearchState


def audit_citations(state: ResearchState) -> dict[str, object]:
    sources = {source.source_id for source in state.sources}
    evidence = {item.evidence_id: item for item in state.evidence}
    claims = {claim.claim_id: claim for claim in state.claims}
    issues: list[str] = []
    for claim in state.claims:
        if not claim.evidence_ids:
            issues.append(f"claim_without_evidence:{claim.claim_id}")
        for evidence_id in claim.evidence_ids:
            if evidence_id not in evidence:
                issues.append(f"missing_evidence:{claim.claim_id}:{evidence_id}")
    for citation in state.citations:
        item = evidence.get(citation.evidence_id)
        claim = claims.get(citation.claim_id)
        if claim is None:
            issues.append(f"missing_claim:{citation.citation_id}")
        if item is None:
            issues.append(f"missing_evidence:{citation.citation_id}")
        if citation.source_id not in sources:
            issues.append(f"missing_source:{citation.citation_id}")
        if claim and citation.evidence_id not in claim.evidence_ids:
            issues.append(f"citation_not_supporting_claim:{citation.citation_id}")
        if item and item.source_id != citation.source_id:
            issues.append(f"source_mismatch:{citation.citation_id}")
    return {"passed": not issues, "issues": issues}
