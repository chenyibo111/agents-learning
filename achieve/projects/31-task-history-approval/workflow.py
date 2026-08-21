"""Checkpointed workflow with a human approval gate for lesson 31."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from store import TaskStore

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:
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


class ApprovalState(TypedDict, total=False):
    task_id: str
    query: str
    draft_report: str
    decision: str
    comment: str
    status: str
    events: Annotated[list[str], operator.add]


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "第31课需要 LangGraph，请先安装项目 requirements.txt"
        )


def draft_report_node(
    state: ApprovalState,
    store: TaskStore,
) -> dict[str, Any]:
    report = (
        f"# {state['query']}\n\n"
        "## 草稿\n\n"
        "这是等待人工确认的研究报告草稿。\n"
        "在确认之前，不执行外部发布操作。"
    )
    store.update_task(
        state["task_id"],
        status="awaiting_approval",
        report=report,
        state={"status": "awaiting_approval", "draft_report": report},
    )
    return {
        "draft_report": report,
        "status": "awaiting_approval",
        "events": ["draft_report 完成，等待人工确认"],
    }


def approval_gate_node(
    state: ApprovalState,
    store: TaskStore,
) -> dict[str, Any]:
    answer = interrupt(
        {
            "type": "approval_required",
            "task_id": state["task_id"],
            "report": state["draft_report"],
        }
    )
    if isinstance(answer, dict):
        decision = str(answer.get("decision", "")).strip().lower()
        comment = str(answer.get("comment", "")).strip()
    else:
        decision = str(answer).strip().lower()
        comment = ""

    if decision in {"approve", "approved"}:
        decision = "approved"
    elif decision in {"reject", "rejected"}:
        decision = "rejected"
    else:
        raise ValueError("审批决定必须是 approved 或 rejected")

    store.record_approval(state["task_id"], decision, comment)
    store.update_task(
        state["task_id"],
        status="approval_received",
        state={
            "status": "approval_received",
            "decision": decision,
            "comment": comment,
        },
    )
    return {
        "decision": decision,
        "comment": comment,
        "status": "approval_received",
        "events": [f"收到人工决定：{decision}"],
    }


def route_after_approval(state: ApprovalState) -> str:
    return "publish" if state.get("decision") == "approved" else "reject"


def publish_node(
    state: ApprovalState,
    store: TaskStore,
) -> dict[str, Any]:
    store.update_task(
        state["task_id"],
        status="published",
        state={
            "status": "published",
            "decision": state.get("decision"),
        },
    )
    return {
        "status": "published",
        "events": ["报告已批准并发布"],
    }


def reject_node(
    state: ApprovalState,
    store: TaskStore,
) -> dict[str, Any]:
    store.update_task(
        state["task_id"],
        status="rejected",
        state={
            "status": "rejected",
            "decision": state.get("decision"),
        },
    )
    return {
        "status": "rejected",
        "events": ["报告被拒绝发布"],
    }


def build_graph(
    store: TaskStore,
    checkpointer: Any = None,
) -> Any:
    require_langgraph()
    builder = StateGraph(ApprovalState)
    builder.add_node(
        "draft_report",
        lambda state: draft_report_node(state, store),
    )
    builder.add_node(
        "approval_gate",
        lambda state: approval_gate_node(state, store),
    )
    builder.add_node(
        "publish",
        lambda state: publish_node(state, store),
    )
    builder.add_node(
        "reject",
        lambda state: reject_node(state, store),
    )
    builder.add_edge(START, "draft_report")
    builder.add_edge("draft_report", "approval_gate")
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {"publish": "publish", "reject": "reject"},
    )
    builder.add_edge("publish", END)
    builder.add_edge("reject", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())
