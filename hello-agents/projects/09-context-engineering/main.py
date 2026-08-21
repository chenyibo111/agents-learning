import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def select_context(items: list[tuple[str, int, int]], budget: int) -> list[str]:
    selected, used = [], 0
    for text, priority, cost in sorted(items, key=lambda x: x[1], reverse=True):
        if used + cost <= budget:
            selected.append(text)
            used += cost
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    if args.llm:
        print(ask_llm("说明 Agent 上下文工程中的选择、排序、压缩和预算。"))
    else:
        items = [("安全约束", 100, 2), ("当前任务", 90, 3), ("旧闲聊", 10, 5)]
        print({"context": select_context(items, budget=5)})


if __name__ == "__main__":
    main()
