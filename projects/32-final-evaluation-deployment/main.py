"""Lesson 32 CLI: evaluate, monitor, and check deployment readiness."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from app_adapter import build_app
from deployment import validate_config
from evaluation import DEFAULT_CASES, Evaluator
from monitoring import ModelPricing, Monitor


def _mode(args: argparse.Namespace) -> str:
    return "llm" if args.llm else "demo"


class MonitoredApp:
    def __init__(self, app: Any, monitor: Monitor, mode: str):
        self.app = app
        self.monitor = monitor
        self.mode = mode

    def run(self, query: str) -> dict[str, Any]:
        span = self.monitor.start_span("research_task", kind="workflow")
        try:
            result = self.app.run(query)
            if self.mode == "llm":
                self.monitor.record_model_call(
                    span.span_id,
                    query,
                    result.get("report", ""),
                    ModelPricing(input_per_million=0.15, output_per_million=0.60),
                )
            self.monitor.finish_span(span.span_id)
            return result
        except Exception as error:
            self.monitor.finish_span(
                span.span_id,
                status="error",
                error=str(error),
            )
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="第32课：最终评测与部署")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--demo", action="store_true", help="离线 Demo")
    modes.add_argument("--llm", action="store_true", help="真实 LLM 模式")
    parser.add_argument("--evaluate", action="store_true", help="运行固定评测集")
    parser.add_argument("--health", action="store_true", help="检查部署配置")
    parser.add_argument("--retriever", choices=["keyword", "vector", "both"], default="keyword")
    parser.add_argument("--query", default="状态如何在节点之间流转")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--budget-usd", type=float, default=0.01)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    mode = _mode(args)

    config = validate_config(os.environ, mode=mode)
    if args.health:
        print(json.dumps(config.health_summary(), ensure_ascii=False, indent=2))
        if not args.evaluate and not args.query:
            return
    if not config.ready:
        parser.error("部署配置未就绪：" + "；".join(config.problems))

    try:
        app = build_app(
            mode=mode,
            retriever_mode=args.retriever,
            top_k=args.top_k,
            rebuild=args.rebuild,
        )
        monitor = Monitor(budget_usd=args.budget_usd)
        monitored_app = MonitoredApp(app, monitor, mode)
        if args.evaluate:
            result = Evaluator(DEFAULT_CASES).evaluate(monitored_app)
            result["monitor"] = monitor.report()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            result = monitored_app.run(args.query)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print(json.dumps({"monitor": monitor.report()}, ensure_ascii=False, indent=2))
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
