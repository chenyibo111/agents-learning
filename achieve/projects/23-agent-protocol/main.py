"""Offline client/server demo for the minimal tool and resource protocol."""

import argparse
import json
from typing import Any, Callable, Dict, Optional

from agent import LLMToolAgent, LocalRuleAgent, create_llm_client
from business import build_registry
from protocol import decode_message, encode_message
from server import ProtocolServer


def request(server: ProtocolServer, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send one request through the JSON boundary and decode its response."""
    wire_request = encode_message(payload)
    decoded_request = decode_message(wire_request)
    response = server.handle(decoded_request)
    return decode_message(encode_message(response))


def print_exchange(
    server: ProtocolServer,
    title: str,
    payload: Dict[str, Any],
) -> None:
    response = request(server, payload)
    print(f"\n--- {title} ---")
    print(json.dumps(response, ensure_ascii=False, indent=2, sort_keys=True))


def run_demo() -> None:
    server = ProtocolServer(build_registry())
    print_exchange(
        server,
        "发现工具",
        {"id": 1, "method": "tools/list", "params": {}},
    )
    print_exchange(
        server,
        "发现资源",
        {"id": 2, "method": "resources/list", "params": {}},
    )
    print_exchange(
        server,
        "调用工具",
        {
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
            },
        },
    )
    print_exchange(
        server,
        "调用工具",
        {
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "mul_numbers",
                "arguments": {"a": 2, "b": 3},
            },
        },
    )
    print_exchange(
        server,
        "读取资源",
        {
            "id": 4,
            "method": "resources/read",
            "params": {"uri": "note://agent-basics"},
        },
    )
    print_exchange(
        server,
        "读取资源",
        {
            "id": 4,
            "method": "resources/read",
            "params": {"uri": "note://short-memory"},
        },
    )
    print_exchange(
        server,
        "未知工具",
        {
            "id": 5,
            "method": "tools/call",
            "params": {"name": "delete_everything", "arguments": {}},
        },
    )
    print_exchange(
        server,
        "错误参数",
        {
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "add_numbers",
                "arguments": {"a": 2},
            },
        },
    )


def run_interactive(
    agent_name: str,
    server: Optional[ProtocolServer] = None,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> None:
    server = server or ProtocolServer(build_registry())
    if agent_name == "local":
        current_agent = LocalRuleAgent(server)
    elif agent_name == "llm":
        client, model = create_llm_client()
        current_agent = LLMToolAgent(server, client, model)
    else:
        raise ValueError(f"未知 Agent 类型：{agent_name}")

    output_fn(f"已启动 {agent_name} Agent，输入“退出”结束。")
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
            answer = current_agent.run(user_input)
        except Exception:
            answer = "执行失败，请检查 Agent 配置或稍后重试。"
        output_fn(f"Agent：{answer}")


def main() -> None:
    parser = argparse.ArgumentParser(description="第23课：Agent 工具与资源协议")
    parser.add_argument("--demo", action="store_true", help="运行离线协议 Demo")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="进入用户输入模式",
    )
    parser.add_argument(
        "--agent",
        choices=["local", "llm"],
        default="local",
        help="interactive 模式使用的 Agent 类型",
    )
    args = parser.parse_args()
    if args.demo:
        run_demo()
    elif args.interactive:
        run_interactive(args.agent)
    else:
        parser.error("请使用 --demo 或 --interactive")


if __name__ == "__main__":
    main()
