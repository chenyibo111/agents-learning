"""一次完整评测实验的编排。"""

from typing import Any

from .comparison import compare_strategies, pareto_frontier
from .dataset import EVAL_DATASET_VERSION, evaluation_cases
from .gate import evaluate_release_gate
from .judges import calibrate_judges, judge_run
from .metrics import compute_metrics
from .runner import run_dataset


def run_experiment(
    strategies: tuple[str, ...] = ("guarded", "fast", "unsafe"),
) -> dict[str, Any]:
    cases = evaluation_cases()
    all_runs = []
    reports = {}
    judge_sections: dict[str, Any] = {}
    for strategy in strategies:
        runs = run_dataset(strategy, cases)
        all_runs.extend(runs)
        metric_report = compute_metrics(strategy, runs)
        reports[strategy] = metric_report
        judge_results = [judge_run(run) for run in runs]
        judge_sections[strategy] = {
            "results": [result.to_dict() for result in judge_results],
            "calibration": calibrate_judges(judge_results, {}),
        }
    guarded_report = reports.get("guarded") or next(iter(reports.values()))
    gate = evaluate_release_gate(guarded_report)
    manifest = {
        "run_id": f"{EVAL_DATASET_VERSION}-seed0",
        "schema_version": "1.0",
        "dataset_version": EVAL_DATASET_VERSION,
        "seed": 0,
        "strategies": list(strategies),
        "case_ids": [case.case_id for case in cases],
    }
    return {
        "manifest": manifest,
        "runs": all_runs,
        "report": {
            "dataset_version": EVAL_DATASET_VERSION,
            "strategies": list(strategies),
            "metrics": compare_strategies(reports),
            "judges": judge_sections,
            "pareto_frontier": pareto_frontier(reports),
            "gate": gate.to_dict(),
            "failed_samples": sorted(set(guarded_report.failed_case_ids)),
        },
    }
