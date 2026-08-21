"""Lesson 27 entry point with offline Demo and real LLM modes."""

from __future__ import annotations

import argparse
import json
from typing import Callable

from runtime import DemoRuntime, build_llm_runtime_from_env
from workflow import require_langgraph, run_workflow


DEFAULT_TOPIC = "评估多 Agent 协作是否适合生产环境"


def print_result(result: dict, output_fn: Callable[[str], None] = print) -> None:
    output_fn(
        json.dumps(
            {
                "status": result.get("status"),
                "events": result.get("events", []),
                "source_count": len(result.get("sources", [])),
                "evidence_count": len(result.get("verified_evidence", [])),
            },
            ensure_ascii=False,
        )
    )
    output_fn(result.get("report", ""))


def run_demo(
    topic: str = DEFAULT_TOPIC,
    output_fn: Callable[[str], None] = print,
) -> dict:
    """Run the shared graph with deterministic providers and no model config."""
    require_langgraph()
    result = run_workflow(topic, DemoRuntime())
    print_result(result, output_fn)
    return result


def run_llm(
    topic: str = DEFAULT_TOPIC,
    output_fn: Callable[[str], None] = print,
) -> dict:
    """Run the same graph with the OpenAI-compatible runtime from .env."""
    require_langgraph()
    result = run_workflow(topic, build_llm_runtime_from_env(), thread_id="lesson-27-llm")
    print_result(result, output_fn)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="第27课：研究助手需求与双运行时架构"
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--demo", action="store_true", help="离线 Demo，不访问模型")
    modes.add_argument("--llm", action="store_true", help="使用真实 OpenAI 兼容模型")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="研究主题")
    args = parser.parse_args()

    try:
        if args.demo:
            run_demo(args.topic)
        else:
            run_llm(args.topic)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
