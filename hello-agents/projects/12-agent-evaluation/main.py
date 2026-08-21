import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def evaluate(rows: list[dict]) -> dict:
    total = len(rows)
    return {"success_rate": sum(r["success"] for r in rows) / total, "avg_steps": sum(r["steps"] for r in rows) / total, "unsafe": sum(r["unsafe"] for r in rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    rows = [{"success": 1, "steps": 2, "unsafe": 0}, {"success": 0, "steps": 4, "unsafe": 1}]
    print(ask_llm("设计 Agent 评测指标，覆盖成功率、轨迹、成本和安全。") if args.llm else evaluate(rows))


if __name__ == "__main__":
    main()
