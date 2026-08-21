import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def demo() -> str:
    return "\n".join([
        "ReAct: decide -> tool -> observe -> decide -> answer",
        "Plan-and-Solve: plan=[查资料, 汇总] -> execute -> answer",
        "Reflection: draft -> critique -> revise -> answer",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("比较 ReAct、Plan-and-Solve、Reflection，并说明适用场景。") if args.llm else demo())


if __name__ == "__main__":
    main()
