import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def run_workflow(question: str) -> list[dict]:
    state = {"question": question}
    events = []
    for name, fn in [("normalize", lambda s: {**s, "normalized": s["question"].strip()}), ("route", lambda s: {**s, "route": "knowledge"}), ("answer", lambda s: {**s, "answer": "从知识库回答：" + s["normalized"]})]:
        state = fn(state)
        events.append({"node": name, "state": dict(state)})
    return events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    if args.llm:
        print(ask_llm("解释 Dify、Coze 和 n8n 的定位差异，并指出低代码 Agent 的两个风险。"))
    else:
        for event in run_workflow("  如何配置 Agent？ "):
            print(event)


if __name__ == "__main__":
    main()
