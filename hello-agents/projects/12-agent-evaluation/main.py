"""第 12 课 Agent 性能评估 CLI。"""

import argparse
import json
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from agent_evaluation.dataset import EVAL_DATASET_VERSION, get_case
from agent_evaluation.experiment import run_experiment
from agent_evaluation.runner import run_case
from agent_evaluation.storage import ArtifactStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 离线评测和发布门禁")
    parser.add_argument("--demo", action="store_true", help="运行完整离线评测")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    parser.add_argument("--strategy", choices=("guarded", "fast", "unsafe"), default="guarded")
    parser.add_argument("--output-dir")
    parser.add_argument("--replay-case")
    args = parser.parse_args()

    if args.replay_case:
        run = run_case(args.strategy, get_case(args.replay_case))
        print(json.dumps(run.to_dict(), ensure_ascii=False, indent=2))
        return

    result = run_experiment()
    report = result["report"]
    if args.output_dir:
        artifacts = ArtifactStore(args.output_dir).save_run(**result)
        report = {**report, "artifacts": artifacts}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"dataset={EVAL_DATASET_VERSION}; strategies={report['strategies']}")
        for strategy, metrics in report["metrics"].items():
            print(
                f"{strategy}: success={metrics['success_rate']}; "
                f"safety_violation={metrics['safety_violation_rate']}; "
                f"cost={metrics['avg_cost_usd']}"
            )
        print(f"pareto_frontier={report['pareto_frontier']}")
        print(f"gate={report['gate']}")


if __name__ == "__main__":
    main()
