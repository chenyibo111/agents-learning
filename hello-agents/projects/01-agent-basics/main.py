import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import run_offline
from llm_agent import run_llm


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demo", action="store_true")
    mode.add_argument("--llm", action="store_true")
    parser.add_argument("--task", default="先计算 8 加 4，再把结果乘以 3")
    args = parser.parse_args()
    if args.llm:
        result = run_llm(args.task)
    else:
        result = run_offline(args.task)
    print(f"answer={result.answer}; steps={result.steps}; tools={result.tool_names}")


if __name__ == "__main__":
    main()
