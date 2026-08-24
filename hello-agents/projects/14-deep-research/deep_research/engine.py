"""可预算约束、可中断恢复的研究状态机。"""

from dataclasses import replace
from pathlib import Path

from .audit import audit_citations
from .evidence import build_claims, extract_evidence
from .planner import decompose_question
from .retriever import RetrievalError
from .schemas import Citation, ResearchQuery, ResearchState
from .storage import CheckpointStore


class ResearchEngine:
    def __init__(self, retriever):
        self.retriever = retriever

    def plan(self, query: ResearchQuery) -> tuple[str, ...]:
        return decompose_question(query)

    def run(
        self,
        query: ResearchQuery,
        *,
        interrupt_after_round: int | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> ResearchState:
        state = ResearchState(query=query, status="RUNNING", queries=self.plan(query))
        return self._continue(state, interrupt_after_round=interrupt_after_round, checkpoint_path=checkpoint_path)

    def resume(self, checkpoint_path: str | Path) -> ResearchState:
        store = CheckpointStore(checkpoint_path)
        state = store.load()
        if state.status != "INTERRUPTED":
            return state
        return self._continue(state, checkpoint_path=checkpoint_path)

    def _continue(
        self,
        state: ResearchState,
        *,
        interrupt_after_round: int | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> ResearchState:
        for round_index in range(state.round + 1, state.query.max_rounds + 1):
            if len(state.sources) >= state.query.max_sources:
                state = replace(state, status="COMPLETED", warnings=tuple(sorted(set((*state.warnings, "source_budget_exhausted")))))
                break
            try:
                found = self.retriever.search(state.query, round_index=round_index)
            except RetrievalError as exc:
                state = replace(state, status="COMPLETED", warnings=tuple(sorted(set((*state.warnings, str(exc))))))
                break
            existing_ids = {item.source_id for item in state.sources}
            new_sources = [item for item in found if item.source_id not in existing_ids]
            if len(state.sources) + len(new_sources) > state.query.max_sources:
                new_sources = new_sources[: state.query.max_sources - len(state.sources)]
                warnings = (*state.warnings, "source_budget_exhausted")
            else:
                warnings = state.warnings
            sources = (*state.sources, *new_sources)
            evidence = extract_evidence(sources)
            claims = build_claims(evidence)
            citations = tuple(
                citation
                for claim in claims
                for citation in (
                    Citation(
                        f"cite-{claim.claim_id}-{evidence_id}",
                        claim.claim_id,
                        evidence_id,
                        next(item.source_id for item in evidence if item.evidence_id == evidence_id),
                    )
                    for evidence_id in claim.evidence_ids
                )
            )
            tokens = sum(len(item.content.split()) for item in new_sources)
            state = replace(
                state,
                status="RUNNING",
                round=round_index,
                sources=sources,
                evidence=evidence,
                claims=claims,
                citations=citations,
                warnings=tuple(sorted(set(warnings))),
                tokens_used=state.tokens_used + tokens,
                cost_usd=round(state.cost_usd + tokens * 0.00001, 6),
            )
            if state.tokens_used >= state.query.max_tokens or state.cost_usd >= state.query.budget_usd:
                state = replace(state, status="COMPLETED", warnings=tuple(sorted(set((*state.warnings, "research_budget_exhausted")))))
                break
            if interrupt_after_round == round_index:
                state = replace(state, status="INTERRUPTED")
                if checkpoint_path:
                    CheckpointStore(checkpoint_path).save(state)
                return state
        else:
            state = replace(state, status="COMPLETED")
        if state.status == "RUNNING":
            state = replace(state, status="COMPLETED")
        if any(claim.uncertain for claim in state.claims):
            state = replace(state, warnings=tuple(sorted(set((*state.warnings, "conflicting_evidence")))))
        audit_citations(state)
        if checkpoint_path:
            CheckpointStore(checkpoint_path).save(state)
        return state
