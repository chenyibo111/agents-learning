import argparse
import json
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parents[0]))
from common import ask_llm
from travel_assistant.experiment import run_demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--weather-failure", action="store_true")
    parser.add_argument("--inventory-expired", action="store_true")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.llm:
        output = ask_llm("设计一个安全的旅行助手，说明搜索、规划和预订审批的边界。")
    else:
        report = run_demo(
            weather_failure=args.weather_failure,
            inventory_expired=args.inventory_expired,
            approve=args.approve,
            output_dir=args.output_dir,
        )
        if args.json:
            output = json.dumps(report, ensure_ascii=False, indent=2)
        else:
            candidates = report["plan"]["candidates"]
            status = report["reservation"]["status"] if report["reservation"] else "NO_CANDIDATE"
            output = (
                f"destination={report['request']['destination']}; "
                f"candidates={len(candidates)}; reservation={status}; "
                f"warnings={report['plan']['warnings']}"
            )
    print(output)


if __name__ == "__main__":
    main()
