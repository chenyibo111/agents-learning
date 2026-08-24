"""只依赖轨迹硬数据的可计算指标。"""

from typing import Iterable

from .schemas import AgentRun, MetricReport


def compute_metrics(strategy: str, runs: Iterable[AgentRun]) -> MetricReport:
    items = list(runs)
    if not items:
        raise ValueError("至少需要一条 Agent 运行记录")
    count = len(items)
    failed = sorted(
        {
            run.case_id
            for run in items
            if not run.success or run.safety_violations or not run.evidence_complete
        }
    )
    return MetricReport(
        strategy=strategy,
        dataset_version=items[0].dataset_version,
        count=count,
        success_rate=round(sum(run.success for run in items) / count, 4),
        avg_steps=round(sum(run.steps for run in items) / count, 4),
        avg_latency_ms=round(sum(run.latency_ms for run in items) / count, 4),
        avg_tokens=round(sum(run.input_tokens + run.output_tokens for run in items) / count, 4),
        avg_cost_usd=round(sum(run.cost_usd for run in items) / count, 6),
        safety_violation_rate=round(sum(bool(run.safety_violations) for run in items) / count, 4),
        tool_parameter_accuracy=round(sum(run.tool_parameters_correct for run in items) / count, 4),
        evidence_completeness_rate=round(sum(run.evidence_complete for run in items) / count, 4),
        failed_case_ids=tuple(failed),
    )
