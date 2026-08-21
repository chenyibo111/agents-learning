import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def pipeline(task: str) -> dict:
    return {"task": task, "state": ["received", "planned", "executed", "evaluated"], "offline": True, "approval": "not-needed"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("给 Agent 毕业项目列出最小交付清单：状态、工具、测试、安全和评测。") if args.llm else pipeline("完成一份带引用的知识摘要"))


if __name__ == "__main__":
    main()
