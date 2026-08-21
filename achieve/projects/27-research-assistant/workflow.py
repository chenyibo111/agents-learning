"""Shared LangGraph workflow for the lesson 27 research assistant."""

from __future__ import annotations

from typing import Any

from runtime import ResearchRuntime
from state import ResearchState

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # Compatibility with older LangGraph releases.
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


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "第27课需要 LangGraph，请先运行："
            "python -m pip install -r projects/27-research-assistant/requirements.txt"
        )


def _event(state: ResearchState, name: str) -> list[str]:
    return [*state.get("events", []), name]


def plan_node(state: ResearchState, runtime: ResearchRuntime) -> dict[str, Any]:
    return {
        "plan": runtime.plan(state["topic"]),
        "status": "planned",
        "events": _event(state, "plan 完成"),
    }


def collect_sources_node(
    state: ResearchState, runtime: ResearchRuntime
) -> dict[str, Any]:
    return {
        "sources": runtime.collect_sources(state["topic"], state.get("plan", [])),
        "status": "sources_collected",
        "events": _event(state, "collect_sources 完成"),
    }


def extract_evidence_node(
    state: ResearchState, runtime: ResearchRuntime
) -> dict[str, Any]:
    return {
        "evidence": runtime.extract_evidence(
            state["topic"], state.get("sources", [])
        ),
        "status": "evidence_extracted",
        "events": _event(state, "extract_evidence 完成"),
    }


def verify_evidence_node(
    state: ResearchState, runtime: ResearchRuntime
) -> dict[str, Any]:
    return {
        "verified_evidence": runtime.verify_evidence(
            state["topic"], state.get("evidence", [])
        ),
        "status": "evidence_verified",
        "events": _event(state, "verify_evidence 完成"),
    }


def write_report_node(
    state: ResearchState, runtime: ResearchRuntime
) -> dict[str, Any]:
    return {
        "report": runtime.write_report(
            state["topic"], state.get("verified_evidence", [])
        ),
        "status": "completed",
        "events": _event(state, "write_report 完成"),
    }


def build_graph(runtime: ResearchRuntime, checkpointer: Any = None) -> Any:
    require_langgraph()
    builder = StateGraph(ResearchState)
    builder.add_node("plan", lambda state: plan_node(state, runtime))
    builder.add_node(
        "collect_sources", lambda state: collect_sources_node(state, runtime)
    )
    builder.add_node(
        "extract_evidence", lambda state: extract_evidence_node(state, runtime)
    )
    builder.add_node(
        "verify_evidence", lambda state: verify_evidence_node(state, runtime)
    )
    builder.add_node(
        "write_report", lambda state: write_report_node(state, runtime)
    )

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "collect_sources")
    builder.add_edge("collect_sources", "extract_evidence")
    builder.add_edge("extract_evidence", "verify_evidence")
    builder.add_edge("verify_evidence", "write_report")
    builder.add_edge("write_report", END)

    if checkpointer is None:
        checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


def run_workflow(
    topic: str,
    runtime: ResearchRuntime,
    thread_id: str = "lesson-27-demo",
) -> ResearchState:
    graph = build_graph(runtime)
    return graph.invoke(
        {"topic": topic, "events": []},
        {"configurable": {"thread_id": thread_id}},
    )
