import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def trajectory(correct: bool, steps: int) -> list[dict]:
    reward = (1 if correct else 0) - 0.1 * steps
    return [{"state": "task", "action": "solve", "reward": reward, "done": True}]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("解释 SFT、Reward、轨迹和 Agentic-RL 的关系。") if args.llm else {"good": trajectory(True, 2), "shortcut": trajectory(False, 1)})


if __name__ == "__main__":
    main()
