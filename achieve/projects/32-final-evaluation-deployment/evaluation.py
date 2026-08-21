"""Offline regression evaluation for the final research assistant."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


class ResearchApp(Protocol):
    def run(self, query: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    query: str
    expected_sources: tuple[str, ...] = ()
    require_citation: bool = True
    expected_status: str = "completed"


DEFAULT_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        case_id="state-recovery",
        query="状态如何在节点之间流转",
        expected_sources=("agent-state.md",),
    ),
    EvalCase(
        case_id="workflow-safety",
        query="外部副作用节点如何保证安全",
        expected_sources=("workflow.md",),
    ),
    EvalCase(
        case_id="retrieval-comparison",
        query="关键词检索和向量检索有什么区别",
        expected_sources=("retrieval.md",),
    ),
)


def _source_names(values: Sequence[Any]) -> set[str]:
    names: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            source = value.get("source", "")
        else:
            source = str(value)
        if source:
            names.add(source.split("#", 1)[0])
    return names


def _citation_ok(report: str, expected_sources: Sequence[str]) -> bool:
    if not expected_sources:
        return True
    if not re.search(r"(?<!\w)\[\d+\]", report):
        return False
    return all(f"{source}#" in report for source in expected_sources)


class Evaluator:
    """Run fixed cases against an injected app and return JSON-safe metrics."""

    def __init__(self, cases: Sequence[EvalCase] = DEFAULT_CASES):
        self.cases = tuple(cases)

    def evaluate(self, app: ResearchApp) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for case in self.cases:
            started = time.perf_counter()
            try:
                output = app.run(case.query)
                status_ok = output.get("status") == case.expected_status
                source_hit = set(case.expected_sources).issubset(
                    _source_names(output.get("sources", []))
                )
                citation_ok = (
                    not case.require_citation
                    or _citation_ok(
                        str(output.get("report", "")),
                        case.expected_sources,
                    )
                )
                passed = status_ok and source_hit and citation_ok
                error = ""
            except Exception as exc:  # Evaluation must continue to the next case.
                status_ok = False
                source_hit = False
                citation_ok = False
                passed = False
                error = str(exc)
            results.append(
                {
                    "case_id": case.case_id,
                    "query": case.query,
                    "passed": passed,
                    "status_ok": status_ok,
                    "source_hit": source_hit,
                    "citation_ok": citation_ok,
                    "duration_ms": round(
                        (time.perf_counter() - started) * 1000,
                        3,
                    ),
                    "error": error,
                }
            )

        total = len(results)
        passed_count = sum(1 for result in results if result["passed"])
        return {
            "total": total,
            "passed": passed_count,
            "failed": total - passed_count,
            "pass_rate": round(passed_count / total, 4) if total else 1.0,
            "results": results,
        }
