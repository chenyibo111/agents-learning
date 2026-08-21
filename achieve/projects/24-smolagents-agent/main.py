"""Lesson 24 entry point: offline tools and a real smolagents Agent."""

import argparse
import json
from typing import Callable

from agent_runner import build_agent_from_env
from tools import add_numbers, mul_numbers, read_resource, search_notes


def run_demo(output_fn: Callable[[str], None] = print) -> None:
    """Run tools directly so the demo works without smolagents or an API key."""
    examples = [
        ("add_numbers", add_numbers(2, 3)),
        ("mul_numbers", mul_numbers(6, 7)),
        ("search_notes", search_notes("工具 协议")),
        ("read_resource", read_resource("note://agent-basics")),
    ]
    for name, result in examples:
        output_fn(
            json.dumps(
                {"tool": name, "result": result},
                ensure_ascii=False,
                sort_keys=True,
            )
        )


def run_interactive(
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    agent = build_agent_from_env()
    output_fn("smolagents Agent 已启动，输入“退出”结束。")
    while True:
        try:
            user_input = input_fn("你：").strip()
        except EOFError:
            break
        if user_input in {"退出", "exit", "quit"}:
            output_fn("Agent：再见。")
            break
        if not user_input:
            continue
        try:
            answer = agent.run(user_input)
        except Exception:
            answer = "Agent 执行失败，请检查模型配置或稍后重试。"
        output_fn(f"Agent：{answer}")


def main() -> None:
    parser = argparse.ArgumentParser(description="第24课：用 smolagents 重写 Agent")
    parser.add_argument("--demo", action="store_true", help="运行离线工具 Demo")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="运行真实 smolagents Agent",
    )
    args = parser.parse_args()
    if args.demo:
        run_demo()
    elif args.interactive:
        try:
            run_interactive()
        except RuntimeError as error:
            parser.error(str(error))
    else:
        parser.error("请使用 --demo 或 --interactive")


if __name__ == "__main__":
    main()
