"""Lesson 26 entry point."""

import argparse

from workflow import InMemorySaver, build_graph, require_langgraph


def run_demo(task: str) -> None:
    require_langgraph()
    graph = build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "lesson-26-demo"}}
    result = graph.invoke(
        {"task": task, "events": []},
        config,
    )

    print("执行事件：", " → ".join(result["events"]))
    print("最终状态：", result["status"])
    print("最终答案：\n", result["final_answer"])


def main() -> None:
    parser = argparse.ArgumentParser(description="第26课：多 Agent 协作")
    parser.add_argument("--demo", action="store_true", help="运行离线协作 Demo")
    parser.add_argument(
        "--task",
        default="评估多 Agent 协作是否适合生产环境",
        help="交给协作团队的任务",
    )
    args = parser.parse_args()
    if not args.demo:
        parser.error("请使用 --demo")
    run_demo(args.task)


if __name__ == "__main__":
    main()

