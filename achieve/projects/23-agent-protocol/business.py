"""Safe, offline business handlers used by the protocol demo."""

from typing import Any, Dict, List

from registry import (
    ResourceDefinition,
    ToolDefinition,
    ToolResourceRegistry,
)


NOTES: List[Dict[str, Any]] = [
    {
        "uri": "note://agent-basics",
        "name": "Agent 基础",
        "keywords": ["agent", "模型", "工具"],
        "content": (
            "Agent 通常通过模型决定下一步行动，再通过工具完成外部操作。"
        ),
    },
    {
        "uri": "note://protocol-boundary",
        "name": "协议边界",
        "keywords": ["协议", "工具", "资源"],
        "content": (
            "协议层负责描述、请求、路由和错误格式，业务层负责真正执行。"
        ),
    },
    {
        "uri": "note://short-memory",
        "name": "短期记忆",
        "keywords": ["记忆", "历史记录", "上下文"],
        "content": (
            "Agent 短期记忆通常是根据用户之前的问题和之前做出的回复的历史记录，也是 Agent 的上下文"
        ),
    },
]
NOTES_BY_URI = {note["uri"]: note for note in NOTES}


def add_numbers(a: int, b: int) -> Dict[str, int]:
    return {"a": a, "b": b, "sum": a + b}

def mul_numbers(a: int, b: int) -> Dict[str, int]:
    return {"a": a, "b": b, "sum": a * b}


def search_notes(query: str) -> List[Dict[str, str]]:
    query_terms = {term.lower() for term in query.split() if term}
    return [
        {"uri": note["uri"], "name": note["name"]}
        for note in NOTES
        if query_terms & set(note["keywords"])
    ]


def read_note(uri: str) -> str:
    return NOTES_BY_URI[uri]["content"]


def build_registry() -> ToolResourceRegistry:
    registry = ToolResourceRegistry()
    registry.register_tool(
        ToolDefinition(
            name="add_numbers",
            description="计算两个整数的和",
            input_schema={
                "type": "object",
                "required": ["a", "b"],
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        ),
        add_numbers,
    )
    registry.register_tool(
        ToolDefinition(
            name="mul_numbers",
            description="计算两个整数的乘积",
            input_schema={
                "type": "object",
                "required": ["a", "b"],
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
            },
        ),
        mul_numbers,
    )
    registry.register_tool(
        ToolDefinition(
            name="search_notes",
            description="按关键词搜索内置学习笔记",
            input_schema={
                "type": "object",
                "required": ["query"],
                "properties": {"query": {"type": "string"}},
            },
        ),
        search_notes,
    )
    for note in NOTES:
        registry.register_resource(
            ResourceDefinition(
                uri=note["uri"],
                name=note["name"],
                description=f"{note['name']} 学习笔记",
                mime_type="text/markdown",
            ),
            read_note,
        )
    return registry
