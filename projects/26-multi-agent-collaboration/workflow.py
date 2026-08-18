"""Lesson 26: a small fan-out/fan-in multi-agent collaboration graph."""

import operator
from typing import Annotated, Any, TypedDict

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
    try:
        from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
    except ImportError:
        InMemorySaver = None  # type: ignore[assignment,misc]

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = InMemorySaver is not None
except ImportError:
    END = START = StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False


class CollaborationState(TypedDict, total=False):
    task: str
    assignments: list[str]
    research: list[str]
    critiques: list[str]
    final_answer: str
    status: str
    events: Annotated[list[str], operator.add]


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "本课需要 LangGraph，请先运行："
            "python -m pip install -r projects/26-multi-agent-collaboration/requirements.txt"
        )


def coordinator(state: CollaborationState) -> dict[str, Any]:
    """Delegate complementary roles instead of doing every task itself."""
    return {
        "assignments": ["researcher", "critic"],
        "status": "delegated",
        "events": ["coordinator 完成任务委派"],
    }


def researcher(state: CollaborationState) -> dict[str, Any]:
    """Return evidence from the researcher role."""
    return {
        "research": [
            f"围绕“{state['task']}”收集背景资料。",
            "先拆分任务再分配角色，可以减少单个 Agent 的上下文负担。",
            "研究结果应保留来源、假设和不确定性。",
        ],
        "events": ["researcher 完成研究"],
    }


def critic(state: CollaborationState) -> dict[str, Any]:
    """Return risks and missing checks from an independent role."""
    return {
        "critiques": [
            "需要检查研究结论是否有可验证证据。",
            "多个 Agent 会增加调用次数、延迟和成本。",
            "协调者必须处理角色失败、结果冲突和超时。",
        ],
        "events": ["critic 完成审查"],
    }


def synthesizer(state: CollaborationState) -> dict[str, Any]:
    """Combine specialist outputs into one answer."""
    research = "；".join(state.get("research", []))
    critiques = "；".join(state.get("critiques", []))
    answer = (
        f"任务：{state['task']}\n"
        f"研究员结论：{research}\n"
        f"审查员意见：{critiques}\n"
        "综合建议：先验证证据，再根据风险、成本和失败恢复能力决定是否上线。"
    )
    return {
        "final_answer": answer,
        "status": "completed",
        "events": ["synthesizer 完成结果汇总"],
    }


def build_graph(checkpointer: Any = None) -> Any:
    require_langgraph()
    builder = StateGraph(CollaborationState)
    builder.add_node("coordinator", coordinator)
    builder.add_node("researcher", researcher)
    builder.add_node("critic", critic)
    builder.add_node("synthesizer", synthesizer)

    builder.add_edge(START, "coordinator")
    builder.add_edge("coordinator", "researcher")
    builder.add_edge("coordinator", "critic")
    builder.add_edge("researcher", "synthesizer")
    builder.add_edge("critic", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())

