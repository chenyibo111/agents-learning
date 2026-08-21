"""Adapter that exposes lesson 30 as a small ResearchApp contract."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any


LESSON_30_DIR = Path(__file__).resolve().parents[1] / "30-cited-markdown-report"


def _lesson_30_modules() -> tuple[Any, Any, Any, Any]:
    module_path = str(LESSON_30_DIR)
    if module_path not in sys.path:
        sys.path.insert(0, module_path)
    from report import DemoReportWriter, LLMReportWriter
    from research_source import lesson_29_modules

    return DemoReportWriter, LLMReportWriter, lesson_29_modules, module_path


class ResearchAppAdapter:
    """Run the previous lessons and expose only final evaluation fields."""

    def __init__(
        self,
        runtime: Any,
        retriever: Any,
        writer: Any,
        top_k: int = 3,
        thread_prefix: str = "lesson-32",
    ):
        self.runtime = runtime
        self.retriever = retriever
        self.writer = writer
        self.top_k = top_k
        self.thread_prefix = thread_prefix

    def run(self, query: str) -> dict[str, Any]:
        _, _, lesson_29_modules, _ = _lesson_30_modules()
        _, _, _, require_langgraph, run_workflow = lesson_29_modules()
        require_langgraph()
        result = run_workflow(
            query,
            self.runtime,
            self.retriever,
            thread_id=f"{self.thread_prefix}-{uuid.uuid4().hex[:8]}",
            top_k=self.top_k,
        )
        evidence = result.get("verified_evidence", [])
        report = self.writer.write_report(query, evidence)
        return {
            "status": result.get("status"),
            "events": result.get("events", []),
            "sources": [
                f"{item['source']}#{item['chunk_id']}"
                for item in result.get("retrieved_chunks", [])
            ],
            "report": report,
            "evidence_count": len(evidence),
        }


def build_app(
    mode: str,
    retriever_mode: str = "keyword",
    top_k: int = 3,
    rebuild: bool = False,
) -> ResearchAppAdapter:
    DemoReportWriter, LLMReportWriter, lesson_29_modules, _ = _lesson_30_modules()
    build_retriever, DemoRuntime, build_llm_runtime_from_env, _, _ = lesson_29_modules()
    retriever = build_retriever(retriever_mode, rebuild=rebuild)
    if mode == "demo":
        return ResearchAppAdapter(
            runtime=DemoRuntime(),
            retriever=retriever,
            writer=DemoReportWriter(),
            top_k=top_k,
        )
    if mode == "llm":
        runtime = build_llm_runtime_from_env()
        return ResearchAppAdapter(
            runtime=runtime,
            retriever=retriever,
            writer=LLMReportWriter(
                client=runtime.client,
                model_id=runtime.model_id,
            ),
            top_k=top_k,
        )
    raise ValueError("mode 必须是 demo 或 llm")
