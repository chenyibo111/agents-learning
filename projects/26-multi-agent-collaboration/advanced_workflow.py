"""Lesson 26 extension: dynamic specialist dispatch with Send."""

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
    from langgraph.types import Send

    LANGGRAPH_AVAILABLE = InMemorySaver is not None
except ImportError:
    END = START = StateGraph = Send = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False


class CollaborationState(TypedDict, total=False):
    task: str
    requested_roles: list[str]
    simulate_failure: bool
    worker_results: Annotated[list[dict[str, Any]], operator.add]
    failures: Annotated[list[dict[str, str]], operator.add]
    events: Annotated[list[str], operator.add]
    final_answer: str
    status: str


def require_langgraph() -> None:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError(
            "本课需要 LangGraph，请先运行："
            "python -m pip install -r projects/26-multi-agent-collaboration/requirements.txt"
        )


def choose_roles(state: CollaborationState) -> dict[str, Any]:
    """Select specialists from the task instead of using fixed graph edges."""
    task = state["task"]
    text = task.lower()
    roles = ["researcher", "critic"]
    risk_keywords = ("生产", "上线", "风险", "安全", "production", "deploy")
    if state.get("simulate_failure") or any(
        keyword in text for keyword in risk_keywords
    ):
        roles.append("fact_checker")
    return {
        "requested_roles": roles,
        "status": "roles_selected",
        "events": [f"coordinator 选择角色：{', '.join(roles)}"],
    }


def dispatch_workers(state: CollaborationState) -> list[Any]:
    """Create one worker invocation for each selected role."""
    return [
        Send(
            "specialist_worker",
            {
                "task": state["task"],
                "role": role,
                "simulate_failure": state.get("simulate_failure", False),
            },
        )
        for role in state.get("requested_roles", [])
    ]


def _role_output(role: str, task: str) -> list[str]:
    outputs = {
        "researcher": [
            f"围绕“{task}”收集背景事实。",
            "记录来源、假设和不确定性。",
        ],
        "critic": [
            "检查结论是否存在证据缺口。",
            "关注成本、延迟、冲突和失败恢复。",
        ],
        "fact_checker": [
            "核验关键结论是否能被独立来源支持。",
            "对无法验证的内容标记为不确定。",
        ],
    }
    if role not in outputs:
        raise ValueError(f"未知专家角色：{role}")
    return outputs[role]


def specialist_worker(state: CollaborationState) -> dict[str, Any]:
    """Execute one dynamically dispatched specialist and isolate its failure."""
    role = state["role"]
    try:
        if state.get("simulate_failure") and role == "fact_checker":
            raise TimeoutError("事实核验服务超时")
        return {
            "worker_results": [
                {
                    "role": role,
                    "ok": True,
                    "findings": _role_output(role, state["task"]),
                }
            ],
            "events": [f"{role} 完成"],
        }
    except Exception as error:
        return {
            "failures": [
                {
                    "role": role,
                    "error": str(error),
                }
            ],
            "events": [f"{role} 失败，已记录 warning"],
        }


def synthesize(state: CollaborationState) -> dict[str, Any]:
    """Aggregate successful specialists and expose failures explicitly."""
    ordered_results = sorted(
        state.get("worker_results", []),
        key=lambda item: item["role"],
    )
    sections = [
        f"{item['role']}：{'；'.join(item['findings'])}"
        for item in ordered_results
    ]
    failures = state.get("failures", [])
    warning = ""
    if failures:
        warning = "\nWarning：" + "；".join(
            f"{item['role']} 失败（{item['error']}）"
            for item in failures
        )
    return {
        "final_answer": (
            f"任务：{state['task']}\n"
            + "\n".join(sections)
            + warning
            + "\n综合建议：仅基于成功角色的结果形成初步结论，并明确标记未完成的核验。"
        ),
        "status": "completed_with_warnings" if failures else "completed",
        "events": ["synthesizer 完成动态结果汇总"],
    }


def build_advanced_graph(checkpointer: Any = None) -> Any:
    require_langgraph()
    builder = StateGraph(CollaborationState)
    builder.add_node("coordinator", choose_roles)
    builder.add_node("specialist_worker", specialist_worker)
    builder.add_node("synthesizer", synthesize)
    builder.add_edge(START, "coordinator")
    builder.add_conditional_edges(
        "coordinator",
        dispatch_workers,
        ["specialist_worker"],
    )
    builder.add_edge("specialist_worker", "synthesizer")
    builder.add_edge("synthesizer", END)
    return builder.compile(checkpointer=checkpointer or InMemorySaver())

