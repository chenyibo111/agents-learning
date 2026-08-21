import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm

STAGES = [("规则", "显式规则", "可解释但覆盖有限"), ("搜索", "状态与动作", "组合空间可能爆炸"), ("学习", "数据与奖励", "需要高质量反馈"), ("LLM Agent", "自然语言与工具", "需要运行时约束")]


def demo() -> str:
    return "\n".join(f"{name}: 表示={representation}；限制={limit}" for name, representation, limit in STAGES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("简要比较规则系统、搜索、强化学习和 LLM Agent。") if args.llm else demo())


if __name__ == "__main__":
    main()
