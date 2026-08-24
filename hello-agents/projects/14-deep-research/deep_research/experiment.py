"""第 14 课离线 DeepResearch 实验编排。"""

from .engine import ResearchEngine
from .report import render_report
from .retriever import FixtureRetriever
from .schemas import ResearchQuery
from .storage import ArtifactStore


def run_demo(
    *,
    conflict: bool = False,
    retrieval_failure: bool = False,
    interrupt_after_round: int | None = None,
    resume_path: str | None = None,
    output_dir: str | None = None,
) -> dict:
    query = ResearchQuery(
        query_id="research-demo-001",
        question="Agent 如何保存状态并支持离线回归？",
        max_rounds=2,
        max_sources=5,
        max_tokens=2000,
        budget_usd=0.10,
    )
    retriever = FixtureRetriever(conflict=conflict, fail_on_round=2 if retrieval_failure else None)
    engine = ResearchEngine(retriever)
    checkpoint_path = None
    if output_dir:
        checkpoint_path = f"{output_dir}/checkpoint.json"
    if resume_path:
        state = engine.resume(resume_path)
    else:
        state = engine.run(
            query,
            interrupt_after_round=interrupt_after_round,
            checkpoint_path=checkpoint_path,
        )
    result = {
        "state": state.to_dict(),
        "markdown": render_report(state),
        "warnings": list(state.warnings),
    }
    if output_dir:
        result["artifacts"] = ArtifactStore(output_dir).save_run(state, result)
    return result
