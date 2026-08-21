"""Lesson 26 real LLM multi-agent entry point."""

import argparse

from llm_workflow import InMemorySaver, create_client_from_env, require_langgraph
from llm_workflow import LLMCollaborationRuntime


def run(task: str) -> None:
    require_langgraph()
    client, model = create_client_from_env()
    runtime = LLMCollaborationRuntime(client, model)
    graph = runtime.build_graph(InMemorySaver())
    config = {"configurable": {"thread_id": "lesson-26-llm"}}
    result = graph.invoke(
        {
            "task": task,
            "events": [],
            "worker_results": [],
            "failures": [],
        },
        config,
    )
    print("选择角色：", ", ".join(result.get("requested_roles", [])))
    print("执行事件：", " → ".join(result.get("events", [])))
    print("最终状态：", result.get("status"))
    print("最终答案：\n", result.get("final_answer", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="第26课：真实 LLM 多 Agent 协作")
    parser.add_argument(
        "--task",
        default="评估多 Agent 协作是否适合生产环境",
    )
    args = parser.parse_args()
    run(args.task)


if __name__ == "__main__":
    main()

