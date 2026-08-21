"""Lesson 25: a checkpointed, human-reviewable LangGraph workflow."""

from typing import Any, Literal, TypedDict

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # Compatibility with older LangGraph releases.
    try:
        from langgraph.checkpoint.memory import MemorySaver as InMemorySaver
    except ImportError:
        InMemorySaver = None  # type: ignore[assignment,misc]

try:
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command, interrupt

    LANGGRAPH_AVAILABLE = InMemorySaver is not None
except ImportError:
    END = START = StateGraph = Command = interrupt = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False


class ResearchState(TypedDict, total=False):
    topic: str
    notes: list[str]
    draft: str
    approved: bool
    status: str
    published: str
    events: list[str]


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "本课需要 LangGraph，请先运行："
            "python -m pip install -r projects/25-langgraph-state/requirements.txt"
        )


def _event(state: ResearchState, message: str) -> list[str]:
    return [*state.get("events", []), message]


def collect_notes(state: ResearchState) -> dict[str, Any]:
    topic = state["topic"]
    return {
        "notes": [
            f"主题：{topic}",
            "LangGraph 使用 StateGraph 描述节点和边。",
            "Checkpointer 可以保存每个 thread 的状态并支持恢复。",
        ],
        "status": "collected",
        "events": _event(state, "collect_notes 完成"),
    }


def draft_summary(state: ResearchState) -> dict[str, Any]:
    draft = "；".join(state.get("notes", []))
    return {
        "draft": f"研究摘要：{draft}",
        "status": "drafted",
        "events": _event(state, "draft_summary 完成"),
    }


def human_review(state: ResearchState) -> dict[str, Any]:
    """Pause here until the caller resumes the same thread with a decision."""
    decision = interrupt(
        {
            "type": "human_review",
            "question": "是否批准这份研究摘要？",
            "draft": state.get("draft", ""),
        }
    )
    if isinstance(decision, dict):
        approved = bool(decision.get("approved", False))
    else:
        approved = bool(decision)
    return {
        "approved": approved,
        "status": "approved" if approved else "rejected",
        "events": _event(state, f"human_review {'批准' if approved else '拒绝'}"),
    }


def route_after_review(state: ResearchState) -> Literal["publish", "revise"]:
    return "publish" if state.get("approved", False) else "revise"


def revise(state: ResearchState) -> dict[str, Any]:
    return {
        "draft": state.get("draft", "") + "（已根据审核意见补充说明）",
        "status": "revised",
        "events": _event(state, "revise 完成"),
    }


def publish(state: ResearchState) -> dict[str, Any]:
    return {
        "published": state.get("draft", ""),
        "status": "completed",
        "events": _event(state, "publish 完成"),
    }


def build_graph(checkpointer: Any = None) -> Any:
    require_langgraph()
    builder = StateGraph(ResearchState)
    builder.add_node("collect_notes", collect_notes)
    builder.add_node("draft_summary", draft_summary)
    builder.add_node("human_review", human_review)
    builder.add_node("revise", revise)
    builder.add_node("publish", publish)

    builder.add_edge(START, "collect_notes")
    builder.add_edge("collect_notes", "draft_summary")
    builder.add_edge("draft_summary", "human_review")
    builder.add_conditional_edges(
        "human_review",
        route_after_review,
        {"publish": "publish", "revise": "revise"},
    )
    builder.add_edge("revise", "human_review")
    builder.add_edge("publish", END)

    return builder.compile(checkpointer=checkpointer or InMemorySaver())

