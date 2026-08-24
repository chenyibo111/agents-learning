"""Token-based cost accounting and pre-call budget gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass


class BudgetExceededError(RuntimeError):
    """Raised before a model call would exceed the configured USD budget."""


@dataclass(frozen=True)
class ModelPricing:
    model: str
    input_per_million: float
    output_per_million: float

    def __post_init__(self) -> None:
        if self.input_per_million < 0 or self.output_per_million < 0:
            raise ValueError("模型价格不能为负数")


@dataclass(frozen=True)
class CostReport:
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    budget_usd: float | None
    remaining_budget: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class CostMonitor:
    """Track cumulative usage and reject calls above a configured budget."""

    def __init__(self, pricing: ModelPricing, *, budget_usd: float | None = None):
        if budget_usd is not None and budget_usd < 0:
            raise ValueError("budget_usd 不能为负数")
        self.pricing = pricing
        self.budget_usd = budget_usd
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0

    def estimate_cost(self, *, input_tokens: int, output_tokens: int) -> float:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("Token 数不能为负数")
        return (
            input_tokens / 1_000_000 * self.pricing.input_per_million
            + output_tokens / 1_000_000 * self.pricing.output_per_million
        )

    def reserve(self, *, input_tokens: int, max_output_tokens: int) -> float:
        estimated = self.estimate_cost(
            input_tokens=input_tokens,
            output_tokens=max_output_tokens,
        )
        if self.budget_usd is not None and self.total_cost + estimated > self.budget_usd:
            raise BudgetExceededError(
                f"预计成本 {estimated:.8f} 超出剩余预算 {self.remaining_budget:.8f}"
            )
        return estimated

    def record(self, *, input_tokens: int, output_tokens: int) -> CostReport:
        cost = self.estimate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        if self.budget_usd is not None and self.total_cost + cost > self.budget_usd:
            raise BudgetExceededError(
                f"实际成本 {cost:.8f} 超出剩余预算 {self.remaining_budget:.8f}"
            )
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_cost += cost
        return self.report()

    @property
    def remaining_budget(self) -> float | None:
        if self.budget_usd is None:
            return None
        return max(0.0, self.budget_usd - self.total_cost)

    def report(self) -> CostReport:
        input_cost = (
            self.input_tokens / 1_000_000 * self.pricing.input_per_million
        )
        output_cost = (
            self.output_tokens / 1_000_000 * self.pricing.output_per_million
        )
        return CostReport(
            model=self.pricing.model,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=input_cost + output_cost,
            budget_usd=self.budget_usd,
            remaining_budget=self.remaining_budget,
        )
