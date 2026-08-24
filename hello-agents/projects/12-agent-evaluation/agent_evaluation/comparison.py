"""策略指标比较与 Pareto 前沿。"""

from typing import Any

from .schemas import MetricReport


def compare_strategies(reports: dict[str, MetricReport]) -> dict[str, dict[str, Any]]:
    return {
        strategy: report.to_dict()
        for strategy, report in sorted(reports.items())
    }


def _dominates(left: MetricReport, right: MetricReport) -> bool:
    left_values = (
        left.success_rate,
        -left.avg_cost_usd,
        -left.avg_latency_ms,
        -left.safety_violation_rate,
    )
    right_values = (
        right.success_rate,
        -right.avg_cost_usd,
        -right.avg_latency_ms,
        -right.safety_violation_rate,
    )
    return all(a >= b for a, b in zip(left_values, right_values)) and any(
        a > b for a, b in zip(left_values, right_values)
    )


def pareto_frontier(reports: dict[str, MetricReport]) -> list[str]:
    eligible = {
        strategy: report
        for strategy, report in reports.items()
        if report.safety_violation_rate == 0.0
    }
    return sorted(
        strategy
        for strategy, report in eligible.items()
        if not any(
            other != strategy and _dominates(other_report, report)
            for other, other_report in eligible.items()
        )
    )
