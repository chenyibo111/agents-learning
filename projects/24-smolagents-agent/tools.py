"""Business tools exposed to smolagents."""

from typing import Any, Dict, List

try:
    from smolagents import tool

    SMOLAGENTS_AVAILABLE = True
except ImportError:
    SMOLAGENTS_AVAILABLE = False

    def tool(function):
        """Keep offline unit tests importable without the optional dependency."""
        return function


NOTES: List[Dict[str, Any]] = [
    {
        "uri": "note://agent-basics",
        "name": "Agent 基础",
        "keywords": ["agent", "模型", "工具"],
        "content": "Agent 通常通过模型决定下一步行动，再通过工具完成外部操作。",
    },
    {
        "uri": "note://protocol-boundary",
        "name": "协议边界",
        "keywords": ["协议", "工具", "资源"],
        "content": "协议层负责描述、请求、路由和错误格式，业务层负责真正执行。",
    },
    {
        "uri": "note://short-memory",
        "name": "短期记忆",
        "keywords": ["记忆", "历史记录", "上下文"],
        "content": "Agent 短期记忆通常来自之前的问题和回复，是 Agent 的上下文。",
    },
]
NOTES_BY_URI = {note["uri"]: note for note in NOTES}


@tool
def add_numbers(a: int, b: int) -> int:
    """计算两个整数的和。

    Args:
        a: 第一个整数。
        b: 第二个整数。
    """
    return a + b


@tool
def mul_numbers(a: int, b: int) -> int:
    """计算两个整数的乘积。

    Args:
        a: 第一个整数。
        b: 第二个整数。
    """
    return a * b


@tool
def search_notes(query: str) -> List[Dict[str, str]]:
    """按关键词搜索内置学习笔记，返回匹配的资源名称和 URI。

    Args:
        query: 用空格分隔的搜索关键词。
    """
    query_terms = {term.lower() for term in query.split() if term}
    return [
        {"uri": note["uri"], "name": note["name"]}
        for note in NOTES
        if query_terms & set(note["keywords"])
    ]


@tool
def read_resource(uri: str) -> str:
    """读取一个已注册的 note:// 资源。

    Args:
        uri: 已注册笔记资源的 URI。
    """
    if uri not in NOTES_BY_URI:
        raise ValueError(f"未知资源 URI：{uri}")
    return NOTES_BY_URI[uri]["content"]


def all_tools() -> List[Any]:
    return [add_numbers, mul_numbers, search_notes, read_resource]
