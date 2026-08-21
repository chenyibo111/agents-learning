"""Small dependency-free runtime monitor for the final lesson."""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float
    output_per_million: float


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
    """The next model call would exceed the configured budget."""


@dataclass
class Span:
    span_id: str
    name: str
    kind: str = "node"
    status: str = "running"
    started_at: str = field(default_factory=now_iso)
    ended_at: str = ""
    duration_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    error: str = ""


class Monitor:
    def __init__(
        self,
        budget_usd: float = 0.01,
        clock: Callable[[], float] = time.perf_counter,
    ):
        self.budget_usd = budget_usd
        self.spent_usd = 0.0
        self.clock = clock
        self.spans: list[Span] = []
        self._start_ticks: dict[str, float] = {}

    def start_span(self, name: str, kind: str = "node") -> Span:
        span = Span(span_id=str(uuid.uuid4()), name=name, kind=kind)
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
        span.duration_ms = (
            self.clock() - self._start_ticks.pop(span_id)
        ) * 1000
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
        if self.spent_usd + cost_usd > self.budget_usd:
            raise BudgetExceededError(
                f"预算不足：当前已用 ${self.spent_usd:.6f}，"
                f"本次需要 ${cost_usd:.6f}，预算上限 ${self.budget_usd:.6f}"
            )
        self.spent_usd += cost_usd
        span.input_tokens = input_tokens
        span.output_tokens = output_tokens
        span.cost_usd = cost_usd
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost_usd,
        }

    def measure(
        self,
        name: str,
        operation: Callable[[], Any],
        kind: str = "node",
    ) -> Any:
        span = self.start_span(name, kind=kind)
        try:
            result = operation()
        except Exception as exc:
            self.finish_span(span.span_id, status="error", error=str(exc))
            raise
        self.finish_span(span.span_id)
        return result

    def report(self) -> dict[str, Any]:
        finished = [span for span in self.spans if span.status != "running"]
        slowest = max(finished, key=lambda span: span.duration_ms, default=None)
        return {
            "total_spans": len(self.spans),
            "total_duration_ms": round(
                sum(span.duration_ms for span in finished),
                3,
            ),
            "total_input_tokens": sum(span.input_tokens for span in self.spans),
            "total_output_tokens": sum(span.output_tokens for span in self.spans),
            "total_cost_usd": round(self.spent_usd, 8),
            "budget_usd": self.budget_usd,
            "remaining_budget_usd": round(self.budget_usd - self.spent_usd, 8),
            "failed_spans": [
                span.name
                for span in self.spans
                if span.status not in {"ok", "running"}
            ],
            "slowest_span": slowest.name if slowest else None,
            "spans": [
                {
                    "span_id": span.span_id,
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
