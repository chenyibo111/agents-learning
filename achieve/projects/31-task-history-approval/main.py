"""Lesson 31 demo: persist a task and resume after human approval."""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

from langgraph.types import Command

from store import TaskStore
from workflow import InMemorySaver, build_graph, require_langgraph


DEFAULT_DB = Path(__file__).with_name("task_history.sqlite3")


def run_demo(
    query: str,
    decision: str,
    database: str,
    task_id: str | None = None,
) -> dict:
    require_langgraph()
    task_id = task_id or f"lesson-31-{uuid.uuid4().hex[:8]}"
    store = TaskStore(database)
    store.create_task(task_id, query)
    graph = build_graph(store, InMemorySaver())
    config = {"configurable": {"thread_id": task_id}}

    paused = graph.invoke(
        {"task_id": task_id, "query": query, "events": []},
        config,
    )
    print("暂停状态：", json.dumps(paused, ensure_ascii=False, default=str))

    finished = graph.invoke(
        Command(
            resume={
                "decision": decision,
                "comment": "第31课 Demo 审批意见",
            }
        ),
        config,
    )
    record = store.get_task(task_id)
    print("恢复结果：", json.dumps(finished, ensure_ascii=False, default=str))
    print("历史任务：", json.dumps(record, ensure_ascii=False, indent=2))
    store.close()
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description="第31课：历史任务与人工确认")
    parser.add_argument("--query", default="评估报告是否可以发布")
    parser.add_argument(
        "--decision",
        choices=["approved", "rejected"],
        default="approved",
    )
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--db", default=str(DEFAULT_DB))
    args = parser.parse_args()
    run_demo(args.query, args.decision, args.db, args.task_id)


if __name__ == "__main__":
    main()
