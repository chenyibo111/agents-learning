import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def tick(world: dict) -> dict:
    next_world = {**world, "time": world["time"] + 1, "events": list(world["events"])}
    next_world["events"].append(f"{world['time']}: {world['alice']} 给 {world['bob']} 发送问候")
    return next_world


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    if args.llm:
        print(ask_llm("解释赛博小镇中 Agent、环境、共享状态和长期记忆的关系。"))
    else:
        print(tick({"time": 0, "alice": "商人", "bob": "研究员", "events": []}))


if __name__ == "__main__":
    main()
