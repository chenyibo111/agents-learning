"""第 11 课 CLI 兼容层；核心实现位于同目录的 ``agentic_rl`` 包。"""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Iterable

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root.parents[0]))
from common import ask_llm

from agentic_rl import *  # noqa: F401,F403 - 保持课程旧示例的导入接口
from agentic_rl.rewards import score_steps
from agentic_rl.schemas import SCHEMA_VERSION


def score_trajectory(
    raw_steps: Iterable[TrajectoryStep], task: TaskCase, config: RewardConfig
) -> tuple[tuple[TrajectoryStep, ...], bool, bool, bool, float]:
    """兼容旧课程代码的评分函数签名。"""
    steps, success, tool_used, unsafe, breakdown = score_steps(raw_steps, task, config)
    return steps, success, tool_used, unsafe, breakdown.total


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic-RL 离线实验运行器")
    parser.add_argument("--demo", action="store_true", help="运行确定性离线实验")
    parser.add_argument("--llm", action="store_true", help="请求模型解释概念")
    parser.add_argument("--reward-version", choices=sorted(REWARD_VERSIONS), default="v1")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出报告")
    parser.add_argument("--save-trajectories", help="额外保存 JSONL 轨迹文件")
    parser.add_argument("--output-dir", help="保存完整 run 产物目录")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.llm:
        output = ask_llm(
            "解释 SFT、Agent 轨迹、奖励、优势、偏好优化、GRPO 和 reward hacking 的关系。"
            "重点说明为什么奖励函数必须经过安全审计。"
        )
    else:
        policies = ("tool_first", "shortcut", "wrong")
        manifest, trajectories, report = run_experiment(
            reward_version=args.reward_version, policies=policies
        )
        artifacts = None
        if args.save_trajectories:
            TrajectoryStore.save(args.save_trajectories, trajectories)
        if args.output_dir:
            artifacts = ArtifactStore(args.output_dir).save_run(manifest, trajectories, report)
            report = {**report, "artifacts": artifacts}
        output = json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_report(report)
    print(output)


if __name__ == "__main__":
    main()
