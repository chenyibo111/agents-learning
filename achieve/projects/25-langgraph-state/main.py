"""Lesson 25 entry point."""

import argparse
import json

from workflow import Command, InMemorySaver, build_graph, require_langgraph


def run_demo(reject_once: bool = False) -> None:
    require_langgraph()
    graph = build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "lesson-25-demo"}}

    result = graph.invoke(
        {"topic": "LangGraph 状态管理", "events": []},
        config,
    )
    print("工作流已暂停，等待人工审核：")
    print(json.dumps(result.get("__interrupt__"), ensure_ascii=False, default=str))

    if reject_once:
        result = graph.invoke(Command(resume={"approved": False}), config)
        print("第一次审核：拒绝，工作流回到 revise 节点。")
        print(json.dumps(result.get("__interrupt__"), ensure_ascii=False, default=str))

    result = graph.invoke(Command(resume={"approved": True}), config)
    print("最终状态：", result["status"])
    print("执行事件：", " → ".join(result["events"]))
    print("发布内容：", result["published"])


def main() -> None:
    parser = argparse.ArgumentParser(description="第25课：用 LangGraph 管理状态")
    parser.add_argument("--demo", action="store_true", help="运行离线工作流 Demo")
    parser.add_argument(
        "--reject-once",
        action="store_true",
        help="第一次审核拒绝，修改后再次批准",
    )
    args = parser.parse_args()
    if not args.demo:
        parser.error("请使用 --demo")
    run_demo(reject_once=args.reject_once)


if __name__ == "__main__":
    main()

