import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def make_task() -> dict:
    return {"protocol": "a2a-demo", "version": "1", "task_id": "demo-001", "capability": "summarize", "status": "submitted"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("解释 MCP、A2A 和 ANP 分别解决什么通信问题。") if args.llm else json.dumps(make_task(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
