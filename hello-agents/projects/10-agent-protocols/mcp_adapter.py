"""Local MCP-style adapter and optional official MCP SDK factory."""

from __future__ import annotations

import json
from typing import Any

from protocol_engine.auth import Authorizer
from protocol_engine.contracts import JsonRpcRequest
from protocol_engine.registry import CapabilityRegistry
from protocol_engine.server import ProtocolServer


def _summarize(arguments: dict[str, Any]) -> dict[str, Any]:
    text = str(arguments.get("text", "")).strip()
    return {"summary": text[:80], "length": len(text)}


def build_demo_server() -> ProtocolServer:
    registry = CapabilityRegistry()
    registry.register_tool(
        "add_numbers",
        lambda arguments: arguments["a"] + arguments["b"],
        description="计算两个整数之和",
        input_schema={
            "type": "object",
            "required": ["a", "b"],
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        },
        required_scopes={"math:use"},
    )
    registry.register_tool(
        "summarize_text",
        _summarize,
        description="生成离线文本摘要",
        input_schema={
            "type": "object",
            "required": ["text"],
            "properties": {"text": {"type": "string"}},
        },
        required_scopes={"text:use"},
    )
    registry.register_resource(
        "lesson://10/intro",
        "MCP 负责工具与资源调用；A2A 负责 Agent 间任务委派。",
        description="第 10 课协议边界",
        required_scopes={"resources:read"},
    )
    authorizer = Authorizer(
        {
            "demo-token": ("demo-agent", {"math:use", "text:use", "resources:read", "tasks:submit", "tasks:read", "tasks:cancel", "tasks:run"}),
            "read-only-token": ("reader", {"resources:read", "tasks:read"}),
        }
    )
    server = ProtocolServer(registry, authorizer=authorizer)
    server.register_task_handler("summarize", lambda task: _summarize(task.input), required_scopes={"text:use"})
    return server


def dispatch(server: ProtocolServer, method: str, params: dict[str, Any], *, request_id: str, token: str) -> dict[str, Any]:
    return server.handle(JsonRpcRequest(id=request_id, method=method, params=params), token=token).to_dict()


def run_demo() -> dict[str, Any]:
    server = build_demo_server()
    listed = dispatch(server, "tools/list", {}, request_id="demo-tools-list", token="demo-token")
    called = dispatch(
        server,
        "tools/call",
        {"name": "add_numbers", "arguments": {"a": 2, "b": 3}},
        request_id="demo-tools-call",
        token="demo-token",
    )
    resource = dispatch(
        server,
        "resources/read",
        {"uri": "lesson://10/intro"},
        request_id="demo-resource-read",
        token="demo-token",
    )
    task = dispatch(
        server,
        "tasks/submit",
        {"capability": "summarize", "input": {"text": "协议任务"}, "task_id": "a2a-demo-001", "run": True},
        request_id="demo-task-submit",
        token="demo-token",
    )
    return {"legacy_task": {"protocol": "a2a-demo", "version": "1", "task_id": "demo-001", "capability": "summarize", "status": "submitted"}, "mcp": {"list": listed, "call": called, "resource": resource}, "a2a": task["result"]["task"]}


def build_official_mcp_server() -> Any:
    """Build an official FastMCP server when the optional SDK is installed."""

    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("官方 MCP 适配需要安装 mcp 依赖") from exc

    server = FastMCP("hello-agents-lesson-10")

    @server.tool()
    def add_numbers(a: int, b: int) -> int:
        """计算两个整数之和。

        Args:
            a: 第一个整数。
            b: 第二个整数。
        """

        return a + b

    @server.resource("lesson://10/intro")
    def lesson_intro() -> str:
        """返回第 10 课协议简介。"""

        return "MCP 负责工具与资源调用；A2A 负责 Agent 间任务委派。"

    return server
