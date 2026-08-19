"""Lesson 29 entry point for the research task workflow."""

from __future__ import annotations

import argparse
import json
from typing import Callable

from retrieval_source import build_retriever
from runtime import DemoRuntime, build_llm_runtime_from_env
from workflow import require_langgraph, run_workflow


DEFAULT_QUERY = "Agent 如何保存状态并恢复工作流？"


def print_result(result: dict, output_fn: Callable[[str], None] = print) -> None:
    output_fn(
        json.dumps(
            {
                "status": result.get("status"),
                "events": result.get("events", []),
                "retrieved_count": len(result.get("retrieved_chunks", [])),
                "evidence_count": len(result.get("verified_evidence", [])),
                "evidence": result.get("verified_evidence", []),
            },
            ensure_ascii=False,
        )
    )


def run(
    query: str,
    runtime: object,
    retriever: object,
    top_k: int = 3,
    thread_id: str = "lesson-29-demo",
    output_fn: Callable[[str], None] = print,
) -> dict:
    require_langgraph()
    result = run_workflow(
        query,
        runtime,
        retriever,
        thread_id=thread_id,
        top_k=top_k,
    )
    print_result(result, output_fn)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="第29课：研究任务工作流")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--demo", action="store_true", help="离线 Demo，不访问模型")
    modes.add_argument("--llm", action="store_true", help="使用真实 OpenAI 兼容模型")
    parser.add_argument("--retriever", choices=["keyword", "vector", "both"], default="keyword")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="研究问题")
    parser.add_argument("--top-k", type=int, default=3, help="最多召回的资料片段数")
    parser.add_argument("--thread-id", default="lesson-29-demo", help="LangGraph 检查点线程 ID")
    parser.add_argument("--rebuild", action="store_true", help="重建向量索引")
    args = parser.parse_args()

    try:
        retriever = build_retriever(args.retriever, rebuild=args.rebuild)
        runtime = build_llm_runtime_from_env() if args.llm else DemoRuntime()
        run(args.query, runtime, retriever, args.top_k, args.thread_id)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
