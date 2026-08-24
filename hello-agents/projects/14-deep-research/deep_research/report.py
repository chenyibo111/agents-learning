"""带引用的确定性研究报告生成。"""

from .audit import audit_citations
from .schemas import ResearchState


def render_report(state: ResearchState) -> str:
    audit = audit_citations(state)
    sources = {source.source_id: source for source in state.sources}
    evidence = {item.evidence_id: item for item in state.evidence}
    lines = ["# 研究报告", "", f"研究问题：{state.query.question}", "", "## 结论", ""]
    for claim in state.claims:
        uncertainty = "（存在冲突证据，结论不确定）" if claim.uncertain else ""
        citations = [citation for citation in state.citations if citation.claim_id == claim.claim_id]
        marks = " ".join(f"[{citation.citation_id}]" for citation in citations)
        lines.append(f"- {claim.text}{uncertainty} {marks}".rstrip())
    lines.extend(["", "## 来源", ""])
    for citation in state.citations:
        item = evidence[citation.evidence_id]
        source = sources[item.source_id]
        lines.append(f"[{citation.citation_id}] {source.title} ({source.url})")
        lines.append(f"> {item.quote}")
    lines.extend(["", "## 审计", "", f"- passed: {audit['passed']}"])
    if audit["issues"]:
        lines.extend(f"- issue: {issue}" for issue in audit["issues"])
    if state.warnings:
        lines.extend(["", "## 警告", ""])
        lines.extend(f"- {warning}" for warning in state.warnings)
    return "\n".join(lines)
