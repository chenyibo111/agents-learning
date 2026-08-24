"""实验引擎使用的版本化领域模型。"""

from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class TaskCase:
    task_id: str
    a: int
    b: int

    @property
    def target(self) -> int:
        return self.a + self.b


@dataclass(frozen=True)
class RewardConfig:
    version: str
    correct_reward: float
    incorrect_reward: float
    step_penalty: float
    missing_tool_penalty: float
    illegal_action_penalty: float


@dataclass(frozen=True)
class Action:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Observation:
    content: str
    legal: bool
    error: str | None = None


@dataclass(frozen=True)
class TrajectoryStep:
    state: str
    action: str
    observation: str
    legal: bool
    reward: float = 0.0


@dataclass(frozen=True)
class RewardBreakdown:
    correctness: float
    step_cost: float
    missing_tool: float
    illegal_action: float
    total: float


@dataclass(frozen=True)
class Trajectory:
    trajectory_id: str
    task_id: str
    policy: str
    split: str
    reward_version: str
    steps: tuple[TrajectoryStep, ...]
    success: bool
    tool_used: bool
    unsafe: bool
    total_reward: float
    reward_breakdown: RewardBreakdown
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Trajectory":
        payload = dict(value)
        steps = tuple(TrajectoryStep(**step) for step in payload.pop("steps"))
        breakdown = RewardBreakdown(**payload.pop("reward_breakdown"))
        schema_version = payload.get("schema_version", SCHEMA_VERSION)
        if schema_version != SCHEMA_VERSION:
            raise ValueError(f"不支持的轨迹 schema 版本: {schema_version}")
        return cls(steps=steps, reward_breakdown=breakdown, **payload)


@dataclass(frozen=True)
class ExperimentManifest:
    run_id: str
    experiment: str
    seed: int
    reward_version: str
    policies: tuple[str, ...]
    train_task_ids: tuple[str, ...]
    eval_task_ids: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
