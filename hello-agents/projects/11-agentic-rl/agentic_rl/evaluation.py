"""评测、相对优势和发布门禁；不在这里执行模型更新。"""

from typing import Any, Iterable

from .schemas import Trajectory


def evaluate_trajectories(trajectories: Iterable[Trajectory]) -> dict[str, Any]:
    items = list(trajectories)
    if not items:
        raise ValueError("至少需要一条轨迹")
    return {
        "count": len(items),
        "success_rate": round(sum(item.success for item in items) / len(items), 4),
        "unsafe_count": sum(item.unsafe for item in items),
        "avg_reward": round(sum(item.total_reward for item in items) / len(items), 4),
        "avg_steps": round(sum(len(item.steps) for item in items) / len(items), 4),
    }


def evaluate_by_policy(trajectories: Iterable[Trajectory]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Trajectory]] = {}
    for trajectory in trajectories:
        grouped.setdefault(trajectory.policy, []).append(trajectory)
    return {policy: evaluate_trajectories(items) for policy, items in sorted(grouped.items())}


def relative_advantages(trajectories: Iterable[Trajectory]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Trajectory]] = {}
    for trajectory in trajectories:
        grouped.setdefault(trajectory.task_id, []).append(trajectory)
    result: list[dict[str, Any]] = []
    for task_id, items in sorted(grouped.items()):
        baseline = sum(item.total_reward for item in items) / len(items)
        for item in items:
            result.append(
                {
                    "task_id": task_id,
                    "trajectory_id": item.trajectory_id,
                    "policy": item.policy,
                    "reward": item.total_reward,
                    "group_baseline": round(baseline, 4),
                    "relative_advantage": round(item.total_reward - baseline, 4),
                }
            )
    return result


def preferred_trajectory(left: Trajectory, right: Trajectory) -> Trajectory:
    left_key = (not left.unsafe, left.total_reward, left.success)
    right_key = (not right.unsafe, right.total_reward, right.success)
    return left if left_key >= right_key else right


def safety_gate(metrics: dict[str, Any], *, min_success_rate: float = 0.5) -> dict[str, Any]:
    passed = metrics["success_rate"] >= min_success_rate and metrics["unsafe_count"] == 0
    return {
        "passed": passed,
        "min_success_rate": min_success_rate,
        "reason": "passed" if passed else "success or safety threshold failed",
    }
