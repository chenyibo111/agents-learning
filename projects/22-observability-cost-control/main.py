import argparse
import json
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    pricing: ModelPricing,
) -> float:
    return (
        input_tokens / 1_000_000 * pricing.input_per_million
        + output_tokens / 1_000_000 * pricing.output_per_million
    )


class BudgetExceededError(RuntimeError):
    """本次模型调用会超过预算。"""


@dataclass
class BudgetTracker:
    budget_usd: float
    spent_usd: float = 0.0

    def reserve(self, cost_usd: float) -> None:
        if self.spent_usd + cost_usd > self.budget_usd:
            raise BudgetExceededError(
                f"预算不足：当前已用 ${self.spent_usd:.6f}，"
                f"本次需要 ${cost_usd:.6f}，预算上限 ${self.budget_usd:.6f}"
            )
        self.spent_usd += cost_usd


@dataclass
class Span:
    trace_id: str
    span_id: str
    name: str
    parent_id: Optional[str] = None
    kind: str = "node"
    status: str = "running"
    started_at: str = field(default_factory=now_iso)
    ended_at: str = ""
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str = ""


class TraceRecorder:
    def __init__(
        self,
        trace_id: Optional[str] = None,
        budget_usd: float = 0.01,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.trace_id = trace_id or str(uuid.uuid4())
        self.clock = clock
        self.budget = BudgetTracker(budget_usd=budget_usd)
        self.spans: list[Span] = []
        self._start_ticks: dict[str, float] = {}

    def start_span(
        self,
        name: str,
        parent_id: Optional[str] = None,
        kind: str = "node",
    ) -> Span:
        span = Span(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            name=name,
            parent_id=parent_id,
            kind=kind,
        )
        self.spans.append(span)
        self._start_ticks[span.span_id] = self.clock()
        return span

    def finish_span(
        self,
        span_id: str,
        status: str = "ok",
        error: str = "",
    ) -> Span:
        span = self._find_span(span_id)
        span.status = status
        span.error = error
        span.ended_at = now_iso()
        span.duration_ms = (self.clock() - self._start_ticks.pop(span_id)) * 1000
        return span

    def record_model_call(
        self,
        span_id: str,
        input_text: str,
        output_text: str,
        pricing: ModelPricing,
    ) -> dict[str, Any]:
        span = self._find_span(span_id)
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        cost_usd = calculate_cost(input_tokens, output_tokens, pricing)
        self.budget.reserve(cost_usd)
        span.input_tokens = input_tokens
        span.output_tokens = output_tokens
        span.cost_usd = cost_usd
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }

    def record_node(
        self,
        name: str,
        operation: Callable[[], Any],
        parent_id: Optional[str] = None,
    ) -> Any:
        span = self.start_span(name, parent_id=parent_id)
        try:
            result = operation()
        except Exception as error:
            self.finish_span(span.span_id, status="error", error=str(error))
            raise
        self.finish_span(span.span_id)
        return result

    def report(self) -> dict[str, Any]:
        finished_spans = [span for span in self.spans if span.status != "running"]
        node_spans = [span for span in finished_spans if span.kind != "workflow"]
        slowest_candidates = node_spans or finished_spans
        slowest = max(
            slowest_candidates,
            key=lambda span: span.duration_ms,
            default=None,
        )
        return {
            "trace_id": self.trace_id,
            "total_spans": len(self.spans),
            "total_duration_ms": round(
                max((span.duration_ms for span in finished_spans), default=0.0),
                3,
            ),
            "total_input_tokens": sum(span.input_tokens for span in self.spans),
            "total_output_tokens": sum(span.output_tokens for span in self.spans),
            "total_cost_usd": round(self.budget.spent_usd, 8),
            "budget_usd": self.budget.budget_usd,
            "remaining_budget_usd": round(
                self.budget.budget_usd - self.budget.spent_usd,
                8,
            ),
            "failed_spans": [
                span.name for span in self.spans if span.status not in {"ok", "running"}
            ],
            "slowest_span": slowest.name if slowest else None,
            "spans": [
                {
                    "span_id": span.span_id,
                    "parent_id": span.parent_id,
                    "name": span.name,
                    "kind": span.kind,
                    "status": span.status,
                    "duration_ms": round(span.duration_ms, 3),
                    "input_tokens": span.input_tokens,
                    "output_tokens": span.output_tokens,
                    "cost_usd": round(span.cost_usd, 8),
                    "error": span.error,
                }
                for span in self.spans
            ],
        }

    def _find_span(self, span_id: str) -> Span:
        for span in self.spans:
            if span.span_id == span_id:
                return span
        raise KeyError(f"找不到 span：{span_id}")


def run_demo(budget_usd: float, fail_review: bool = False) -> dict[str, Any]:
    pricing = ModelPricing(input_per_million=0.15, output_per_million=0.60)
    recorder = TraceRecorder(budget_usd=budget_usd)
    root = recorder.start_span("workflow", kind="workflow")
    current_span: Optional[Span] = None

    try:
        current_span = recorder.start_span(
            "planner",
            parent_id=root.span_id,
            kind="llm",
        )
        recorder.record_model_call(
            current_span.span_id,
            "请规划一个研究任务",
            "步骤一：收集资料；步骤二：整理结果",
            pricing,
        )
        recorder.finish_span(current_span.span_id)

        recorder.record_node(
            "retrieval",
            lambda: time.sleep(0.01),
            parent_id=root.span_id,
        )

        current_span = recorder.start_span(
            "reviewer",
            parent_id=root.span_id,
            kind="llm",
        )
        if fail_review:
            raise RuntimeError("模拟审查节点失败")
        recorder.record_model_call(
            current_span.span_id,
            "请检查研究结果是否完整",
            "结果完整，可以生成报告",
            pricing,
        )
        recorder.finish_span(current_span.span_id)
        recorder.finish_span(root.span_id)
    except BudgetExceededError as error:
        if current_span and current_span.status == "running":
            recorder.finish_span(
                current_span.span_id,
                status="budget_exceeded",
                error=str(error),
            )
        recorder.finish_span(root.span_id, status="budget_exceeded", error=str(error))
    except Exception as error:
        if current_span and current_span.status == "running":
            recorder.finish_span(current_span.span_id, status="error", error=str(error))
        recorder.finish_span(root.span_id, status="error", error=str(error))

    return recorder.report()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--budget", type=float, default=0.01)
    parser.add_argument("--fail-review", action="store_true")
    args = parser.parse_args()
    if not args.demo:
        parser.error("本课目前提供离线演示，请使用 --demo")

    report = run_demo(args.budget, fail_review=args.fail_review)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
