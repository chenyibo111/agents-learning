"""Lesson 26 advanced entry point: dynamic roles and failure isolation."""

import argparse

from advanced_workflow import InMemorySaver, build_advanced_graph, require_langgraph


def run_demo(task: str, simulate_failure: bool = False) -> None:
    require_langgraph()
    graph = build_advanced_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "lesson-26-advanced"}}
    result = graph.invoke(
        {
            "task": task,
            "simulate_failure": simulate_failure,
            "events": [],
            "worker_results": [],
            "failures": [],
        },
        config,
    )
    print("选择角色：", ", ".join(result["requested_roles"]))
    print("执行事件：", " → ".join(result["events"]))
    print("最终状态：", result["status"])
    print("最终答案：\n", result["final_answer"])


def main() -> None:
    parser = argparse.ArgumentParser(description="第26课扩展：动态多 Agent 协作")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument(
        "--task",
        default="评估多 Agent 协作是否适合生产环境",
    )
    parser.add_argument(
        "--simulate-failure",
        action="store_true",
        help="模拟 fact_checker 超时，观察部分失败汇总",
    )
    args = parser.parse_args()
    if not args.demo:
        parser.error("请使用 --demo")
    run_demo(args.task, args.simulate_failure)


if __name__ == "__main__":
    main()

