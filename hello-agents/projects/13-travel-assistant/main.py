import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


def plan_trip(budget: int = 2000) -> dict:
    options = [{"city": "上海", "days": 2, "cost": 1200}, {"city": "杭州", "days": 2, "cost": 800}]
    return {"options": [item for item in options if item["cost"] <= budget], "approval_required": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    args = parser.parse_args()
    print(ask_llm("设计一个安全的旅行助手，说明搜索、规划和预订审批的边界。") if args.llm else plan_trip())


if __name__ == "__main__":
    main()
