"""实验定义、训练/评测切分和报告生成。"""

from typing import Any

from .evaluation import evaluate_by_policy, relative_advantages, safety_gate
from .rewards import audit_reward_versions
from .runner import sample_trajectories
from .schemas import ExperimentManifest, TaskCase, Trajectory


EXPERIMENT_VERSION = "arithmetic-v1"
TRAIN_TASKS = (TaskCase("train-01", 8, 4), TaskCase("train-02", 2, 7))
EVAL_TASKS = (TaskCase("eval-01", 10, 5), TaskCase("eval-02", 3, 6))


def build_manifest(
    *, reward_version: str = "v1", policies: tuple[str, ...] = ("tool_first", "shortcut", "wrong")
) -> ExperimentManifest:
    return ExperimentManifest(
        run_id=f"{EXPERIMENT_VERSION}-{reward_version}-seed0",
        experiment=EXPERIMENT_VERSION,
        seed=0,
        reward_version=reward_version,
        policies=policies,
        train_task_ids=tuple(task.task_id for task in TRAIN_TASKS),
        eval_task_ids=tuple(task.task_id for task in EVAL_TASKS),
    )


def run_experiment(
    *, reward_version: str = "v1", policies: tuple[str, ...] = ("tool_first", "shortcut", "wrong")
) -> tuple[ExperimentManifest, list[Trajectory], dict[str, Any]]:
    manifest = build_manifest(reward_version=reward_version, policies=policies)
    train = sample_trajectories(policies, TRAIN_TASKS, split="train", reward_version=reward_version)
    evaluation = sample_trajectories(policies, EVAL_TASKS, split="eval", reward_version=reward_version)
    all_trajectories = [*train, *evaluation]

    audit_values: dict[str, list[tuple[str, float, bool]]] = {}
    for version in ("v0", "v1"):
        audit_values[version] = [
            (
                policy,
                sum(
                    item.total_reward
                    for item in sample_trajectories(
                        (policy,), EVAL_TASKS, split="eval", reward_version=version
                    )
                )
                / len(EVAL_TASKS),
                all(item.tool_used and not item.unsafe for item in sample_trajectories(
                    (policy,), EVAL_TASKS, split="eval", reward_version=version
                )),
            )
            for policy in policies
        ]

    eval_metrics = evaluate_by_policy(evaluation)
    report = {
        "experiment": EXPERIMENT_VERSION,
        "seed": manifest.seed,
        "reward_version": reward_version,
        "train": evaluate_by_policy(train),
        "eval": eval_metrics,
        "relative_advantages": relative_advantages(evaluation),
        "safety_gate": {policy: safety_gate(metrics) for policy, metrics in eval_metrics.items()},
        "reward_audit": audit_reward_versions(audit_values),
        "trajectory_count": len(all_trajectories),
        "splits": {"train": len(train), "eval": len(evaluation)},
    }
    return manifest, all_trajectories, report


def experiment_report(
    *, reward_version: str = "v1", policies: tuple[str, ...] = ("tool_first", "shortcut", "wrong")
) -> dict[str, Any]:
    return run_experiment(reward_version=reward_version, policies=policies)[2]


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"experiment={report['experiment']}; reward_version={report['reward_version']}; seed={report['seed']}",
        f"trajectories={report['trajectory_count']}; splits={report['splits']}",
        "train:",
    ]
    lines.extend(f"  {policy}: {metrics}" for policy, metrics in report["train"].items())
    lines.append("eval:")
    lines.extend(f"  {policy}: {metrics}" for policy, metrics in report["eval"].items())
    lines.append("safety_gate:")
    lines.extend(f"  {policy}: {gate}" for policy, gate in report["safety_gate"].items())
    lines.append(f"reward_audit: {report['reward_audit']}")
    return "\n".join(lines)
