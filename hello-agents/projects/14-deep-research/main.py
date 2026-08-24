import argparse
import json
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parents[0]))
from common import ask_llm
from deep_research.experiment import run_demo


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--conflict", action="store_true")
    parser.add_argument("--retrieval-failure", action="store_true")
    parser.add_argument("--interrupt-after-round", type=int)
    parser.add_argument("--resume")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.llm:
        output = ask_llm("设计一个带来源、证据核对和预算的 DeepResearch 流程。")
    else:
        result = run_demo(
            conflict=args.conflict,
            retrieval_failure=args.retrieval_failure,
            interrupt_after_round=args.interrupt_after_round,
            resume_path=args.resume,
            output_dir=args.output_dir,
        )
        output = json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["markdown"]
    print(output)


if __name__ == "__main__":
    main()
