"""轨迹生成器：策略、环境、奖励计算的唯一编排入口。"""

from typing import Iterable

from .environment import ArithmeticEnvironment
from .policies import get_policy
from .rewards import get_reward_config, score_steps
from .schemas import TaskCase, Trajectory, TrajectoryStep


EXPERIMENT_VERSION = "arithmetic-v1"


def generate_trajectory(
    policy: str,
    task: TaskCase,
    *,
    split: str,
    reward_version: str = "v1",
    trajectory_id: str | None = None,
    environment: ArithmeticEnvironment | None = None,
) -> Trajectory:
    if split not in {"train", "eval"}:
        raise ValueError(f"split 必须是 train 或 eval，实际为: {split}")
    env = environment or ArithmeticEnvironment()
    actions = get_policy(policy).propose(task)
    raw_steps: list[TrajectoryStep] = []
    state = "task"
    for action in actions:
        observation = env.execute(task, action)
        raw_steps.append(
            TrajectoryStep(state, action.name, observation.content, observation.legal)
        )
        state = "tool_result" if action.name.startswith("tool:") else "answer"
    steps, success, tool_used, unsafe, breakdown = score_steps(
        raw_steps, task, get_reward_config(reward_version)
    )
    return Trajectory(
        trajectory_id=trajectory_id or f"{split}-{task.task_id}-{policy}",
        task_id=task.task_id,
        policy=policy,
        split=split,
        reward_version=reward_version,
        steps=steps,
        success=success,
        tool_used=tool_used,
        unsafe=unsafe,
        total_reward=breakdown.total,
        reward_breakdown=breakdown,
        metadata={"experiment": EXPERIMENT_VERSION, "target": task.target},
    )


def sample_trajectories(
    policies: Iterable[str],
    tasks: Iterable[TaskCase],
    *,
    split: str,
    reward_version: str = "v1",
) -> list[Trajectory]:
    return [
        generate_trajectory(policy, task, split=split, reward_version=reward_version)
        for task in tasks
        for policy in policies
    ]
