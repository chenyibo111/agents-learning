import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def demo() -> dict:
    state = {"task": "总结", "messages": ["研究 Agent：找到资料", "写作 Agent：形成草稿"], "checkpoint": "after-research"}
    return {"state": state, "route": "research -> writing -> end", "frameworks": ["AutoGen", "AgentScope", "LangGraph"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("比较 AutoGen、AgentScope 和 LangGraph 时，应该关注哪些架构问题？") if args.llm else demo())


if __name__ == "__main__":
    main()
