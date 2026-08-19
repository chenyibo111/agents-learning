"""Lesson 30 entry point for cited Markdown research reports."""

from __future__ import annotations

import argparse
import json
from typing import Callable

from report import DemoReportWriter, LLMReportWriter, ReportWriter
from research_source import lesson_29_modules


DEFAULT_QUERY = "Agent 如何保存状态并恢复工作流？"


def run_report(
    query: str,
    runtime: object,
    retriever: object,
    writer: ReportWriter,
    top_k: int = 3,
    thread_id: str = "lesson-30-demo",
    output_fn: Callable[[str], None] = print,
) -> str:
    _, _, _, require_langgraph, run_workflow = lesson_29_modules()
    require_langgraph()
    result = run_workflow(
        query,
        runtime,
        retriever,
        thread_id=thread_id,
        top_k=top_k,
    )
    report = writer.write_report(
        query,
        result.get("verified_evidence", []),
    )
    output_fn(
        json.dumps(
            {
                "status": result.get("status"),
                "events": result.get("events", []),
                "retrieved_count": len(result.get("retrieved_chunks", [])),
                "evidence_count": len(result.get("verified_evidence", [])),
            },
            ensure_ascii=False,
        )
    )
    output_fn(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="第30课：带引用的 Markdown 报告")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--demo", action="store_true", help="离线 Demo，不访问模型")
    modes.add_argument("--llm", action="store_true", help="使用真实 OpenAI 兼容模型")
    parser.add_argument("--retriever", choices=["keyword", "vector", "both"], default="keyword")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="研究问题")
    parser.add_argument("--top-k", type=int, default=3, help="最多召回的资料片段数")
    parser.add_argument("--thread-id", default="lesson-30-demo", help="LangGraph 检查点线程 ID")
    parser.add_argument("--rebuild", action="store_true", help="重建向量索引")
    args = parser.parse_args()

    try:
        build_retriever, DemoRuntime, build_llm_runtime_from_env, _, _ = lesson_29_modules()
        retriever = build_retriever(args.retriever, rebuild=args.rebuild)
        if args.demo:
            runtime = DemoRuntime()
            writer = DemoReportWriter()
        else:
            runtime = build_llm_runtime_from_env()
            writer = LLMReportWriter(
                client=runtime.client,
                model_id=runtime.model_id,
            )
        run_report(
            args.query,
            runtime,
            retriever,
            writer,
            top_k=args.top_k,
            thread_id=args.thread_id,
        )
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
