"""评测数据、轨迹、指标和门禁的稳定数据契约。"""

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    split: str
    scenario: str
    prompt: str
    expected_answer: str
    required_tool: str | None
    requires_evidence: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]
    success: bool
    latency_ms: float
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TraceEvent:
    step: int
    state: str
    action: str
    observation: str
    latency_ms: float
    input_tokens: int
    output_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    case_id: str
    strategy: str
    dataset_version: str
    final_output: str
    success: bool
    safety_violations: tuple[str, ...]
    trace: tuple[TraceEvent, ...]
    tool_calls: tuple[ToolCall, ...]
    steps: int
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    tool_parameters_correct: bool
    evidence_complete: bool
    failure_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AgentRun":
        payload = dict(value)
        schema_version = payload.get("schema_version", SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"不支持的轨迹 schema 版本: {schema_version}")
        payload["safety_violations"] = tuple(payload["safety_violations"])
        payload["trace"] = tuple(TraceEvent(**event) for event in payload["trace"])
        payload["tool_calls"] = tuple(ToolCall(**call) for call in payload["tool_calls"])
        return cls(**payload)


@dataclass(frozen=True)
class JudgeResult:
    run_id: str
    rubric: dict[str, str]
    score: float
    reason: str
    human_calibrated: bool = False
    human_label: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetricReport:
    strategy: str
    dataset_version: str
    count: int
    success_rate: float
    avg_steps: float
    avg_latency_ms: float
    avg_tokens: float
    avg_cost_usd: float
    safety_violation_rate: float
    tool_parameter_accuracy: float
    evidence_completeness_rate: float
    failed_case_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["failed_case_ids"] = list(self.failed_case_ids)
        return value


@dataclass(frozen=True)
class GateResult:
    passed: bool
    thresholds: dict[str, float]
    failed_metrics: tuple[str, ...]
    failed_case_ids: tuple[str, ...]
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["failed_metrics"] = list(self.failed_metrics)
        value["failed_case_ids"] = list(self.failed_case_ids)
        value["reasons"] = list(self.reasons)
        return value
