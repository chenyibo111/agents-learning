import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm

from cyber_town.engine import SimulationEngine
from cyber_town.evaluation import evaluate_simulation
from cyber_town.storage import ArtifactStore


def tick(world: dict) -> dict:
    """保留课程最小 Demo 的兼容入口。"""
    next_world = {**world, "time": world["time"] + 1, "events": list(world["events"])}
    next_world["events"].append(f"{world['time']}: {world['alice']} 给 {world['bob']} 发送问候")
    return next_world


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--ticks", type=int, default=1)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--interrupt-after-tick", type=int)
    args = parser.parse_args()
    if args.llm:
        print(ask_llm("解释赛博小镇中 Agent、环境、共享状态和长期记忆的关系。"))
        return

    if args.resume:
        state = SimulationEngine.resume(args.resume, ticks=args.ticks)
    else:
        state = SimulationEngine(seed=args.seed).run(
            ticks=args.ticks,
            interrupt_after_tick=args.interrupt_after_tick,
            checkpoint_path=(args.output_dir / "checkpoint.json" if args.output_dir else None),
        )
    report = evaluate_simulation(state)
    artifacts = ArtifactStore(args.output_dir).write(state, report) if args.output_dir else {}
    payload = {"state": state.to_dict(), "report": report, "artifacts": artifacts}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
