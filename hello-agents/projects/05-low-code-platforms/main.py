import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm
from workflow import SQLiteStateStore, build_workflow


def run_workflow(question: str) -> list[dict]:
    return build_workflow().run(question).events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--question", default="  如何配置 Agent？ ")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--approval-timeout-seconds", type=float, default=300)
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--reject", action="store_true")
    args = parser.parse_args()
    if args.llm:
        print(ask_llm("解释 Dify、Coze 和 n8n 的定位差异，并指出低代码 Agent 的两个风险。"))
    else:
        store = SQLiteStateStore(args.state_file) if args.state_file else None
        runner = build_workflow(store=store, approval_timeout_seconds=args.approval_timeout_seconds)
        if args.resume:
            if store is None:
                parser.error("--resume 需要同时提供 --state-file")
            persisted = store.load_latest()
            if args.approve or args.reject:
                state = runner.resume(persisted.approval_id, approved=args.approve)
            else:
                state = persisted
        else:
            state = runner.run(args.question)
            if state.status == "waiting_approval" and (args.approve or args.reject):
                state = runner.resume(state.approval_id, approved=args.approve)
        for event in state.events:
            print(event)


if __name__ == "__main__":
    main()
