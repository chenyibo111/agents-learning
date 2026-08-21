"""LangGraph workflow for planning, retrieval, extraction, and verification."""

from __future__ import annotations

from typing import Any, Protocol

from runtime import ResearchRuntime
from state import ResearchState, SearchResult


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[SearchResult]: ...


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
    END = START = StateGraph = None  # type: ignore[assignment,misc]
    LANGGRAPH_AVAILABLE = False


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "第29课需要 LangGraph，请先运行："
            "python -m pip install -r projects/29-research-task-workflow/requirements.txt"
        )


def _event(state: ResearchState, name: str) -> list[str]:
    return [*state.get("events", []), name]


def plan_node(state: ResearchState, runtime: ResearchRuntime) -> dict[str, Any]:
    return {
        "plan": runtime.plan(state["topic"]),
        "status": "planned",
        "events": _event(state, "plan 完成"),
    }


def retrieve_node(
    state: ResearchState, retriever: Retriever, top_k: int = 3
) -> dict[str, Any]:
    return {
        "retrieved_chunks": retriever.search(state["topic"], top_k=top_k),
        "status": "retrieved",
        "events": _event(state, "retrieve 完成"),
    }


def extract_node(
    state: ResearchState, runtime: ResearchRuntime
) -> dict[str, Any]:
    return {
        "evidence": runtime.extract_evidence(
            state["topic"], state.get("retrieved_chunks", [])
        ),
        "status": "extracted",
        "events": _event(state, "extract 完成"),
    }


def verify_node(
    state: ResearchState, runtime: ResearchRuntime
) -> dict[str, Any]:
    return {
        "verified_evidence": runtime.verify_evidence(
            state["topic"], state.get("evidence", [])
        ),
        "status": "completed",
        "events": _event(state, "verify 完成"),
    }


def build_graph(
    runtime: ResearchRuntime,
    retriever: Retriever,
    top_k: int = 3,
    checkpointer: Any = None,
) -> Any:
    require_langgraph()
    builder = StateGraph(ResearchState)
    builder.add_node("plan", lambda state: plan_node(state, runtime))
    builder.add_node(
        "retrieve", lambda state: retrieve_node(state, retriever, top_k)
    )
    builder.add_node("extract", lambda state: extract_node(state, runtime))
    builder.add_node("verify", lambda state: verify_node(state, runtime))
    builder.add_edge(START, "plan")
    builder.add_edge("plan", "retrieve")
    builder.add_edge("retrieve", "extract")
    builder.add_edge("extract", "verify")
    builder.add_edge("verify", END)
    if checkpointer is None:
        checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


def run_workflow(
    topic: str,
    runtime: ResearchRuntime,
    retriever: Retriever,
    thread_id: str = "lesson-29-demo",
    top_k: int = 3,
) -> ResearchState:
    graph = build_graph(runtime, retriever, top_k=top_k)
    return graph.invoke(
        {"topic": topic, "events": []},
        {"configurable": {"thread_id": thread_id}},
    )
