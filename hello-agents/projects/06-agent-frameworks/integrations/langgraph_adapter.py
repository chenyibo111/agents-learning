"""Official LangGraph StateGraph adapter with interrupt/resume support."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from time import time
from types import SimpleNamespace
from typing import Any, TypedDict
from uuid import uuid4

from frameworks import AgentState
from integrations.common import (
    AdapterCapabilities,
    AgentEvent,
    AgentMessage,
    AsyncAgentAdapter,
    CancellationToken,
    EventSink,
    MissingOptionalDependency,
    ProviderError,
    RunCancelled,
)


def load_langgraph_sdk() -> SimpleNamespace:
    """Load official LangGraph graph, checkpoint and interrupt APIs."""

    try:
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Command, interrupt
    except ImportError as exc:
        raise MissingOptionalDependency(
            "langgraph 和 langchain-core",
            "pip install -r requirements-langgraph.txt",
        ) from exc
    return SimpleNamespace(
        Command=Command,
        END=END,
        MemorySaver=MemorySaver,
        START=START,
        StateGraph=StateGraph,
        interrupt=interrupt,
    )


class GraphState(TypedDict, total=False):
    task: str
    prompt: str
    research: str
    approval: str
    draft: str
    answer: str


@dataclass(frozen=True)
class LangGraphRun:
    run_id: str
    status: str
    interrupted: bool
    state: dict[str, Any]


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _content(value: Any) -> str:
    return str(_field(value, "content", value) or "")


class _AdapterModel:
    """Expose the lesson adapter as the minimal LangGraph model boundary."""

    def __init__(self, adapter: AsyncAgentAdapter):
        self.adapter = adapter

    async def ainvoke(self, prompt: str) -> AgentMessage:
        return await self.adapter.respond("langgraph-model", prompt)


class LangGraphAdapter(AsyncAgentAdapter):
    """Build and execute official StateGraph graphs."""

    capabilities = AdapterCapabilities(
        supports_streaming=True,
        supports_interrupt=True,
        supports_checkpoint=True,
        supports_cancellation=True,
    )

    def __init__(
        self,
        *,
        model: Any,
        checkpointer: Any | None = None,
        stream: bool = False,
    ):
        sdk = load_langgraph_sdk()
        self.model = model
        self.checkpointer = checkpointer or sdk.MemorySaver()
        self.stream = stream

    @classmethod
    def from_environment(
        cls,
        *,
        stream: bool = False,
    ) -> "LangGraphAdapter":
        from integrations.openai_compatible import OpenAICompatibleAdapter

        return cls(
            model=_AdapterModel(OpenAICompatibleAdapter.from_environment(stream=False)),
            stream=stream,
        )

    async def respond(
        self,
        agent: str,
        prompt: str,
        *,
        on_event: EventSink | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> AgentMessage:
        self._raise_if_cancelled(cancel_token)
        graph = self._build_answer_graph()
        run_id = str(uuid4())
        config = {"configurable": {"thread_id": run_id}}

        try:
            if self.stream:
                answer = ""
                async for update in graph.astream(
                    {"prompt": prompt},
                    config=config,
                    stream_mode="updates",
                ):
                    self._raise_if_cancelled(cancel_token)
                    for value in update.values():
                        current = _field(value, "answer", "")
                        delta = self._delta(answer, current)
                        answer = current
                        if delta:
                            await self._emit(
                                on_event,
                                AgentEvent(
                                    run_id=run_id,
                                    node=agent,
                                    phase="message_delta",
                                    timestamp=time(),
                                    metadata={
                                        "delta": delta,
                                        "framework": "langgraph",
                                    },
                                ),
                            )
            else:
                result = await graph.ainvoke({"prompt": prompt}, config=config)
                answer = _field(result, "answer", "")

            self._raise_if_cancelled(cancel_token)
            return AgentMessage(
                sender=agent,
                recipient="runtime",
                content=str(answer),
                metadata={"framework": "langgraph", "agent": agent},
            )
        except RunCancelled:
            raise
        except Exception as exc:
            status_code = _field(exc, "status_code", None)
            raise ProviderError(
                str(exc)[:500] or exc.__class__.__name__,
                status_code=int(status_code) if status_code is not None else None,
            ) from exc

    async def run_until_interrupt(self, task: str) -> LangGraphRun:
        """Pause at the official LangGraph interrupt node."""

        graph = self._build_approval_graph()
        run_id = str(uuid4())
        config = {"configurable": {"thread_id": run_id}}
        result = await graph.ainvoke({"task": task}, config=config)
        interrupted = bool(result.get("__interrupt__"))
        return LangGraphRun(
            run_id=run_id,
            status="paused" if interrupted else "completed",
            interrupted=interrupted,
            state=dict(result),
        )

    async def resume(self, run_id: str, approval: Any) -> AgentState:
        """Resume an interrupted graph using official Command(resume=...)."""

        sdk = load_langgraph_sdk()
        graph = self._build_approval_graph()
        config = {"configurable": {"thread_id": run_id}}
        result = await graph.ainvoke(
            sdk.Command(resume=approval),
            config=config,
        )
        interrupted = bool(result.get("__interrupt__"))
        state = AgentState(
            task=str(result.get("task", "")),
            run_id=run_id,
            status="paused" if interrupted else "completed",
            current_node="approval" if interrupted else "end",
            completed_nodes=[
                node
                for node, key in (
                    ("research", "research"),
                    ("approval", "approval"),
                    ("writing", "draft"),
                )
                if key in result
            ],
            results={
                key: str(result[key])
                for key in ("research", "approval", "draft")
                if key in result
            },
        )
        return state

    def _build_answer_graph(self):
        sdk = load_langgraph_sdk()
        graph = sdk.StateGraph(GraphState)

        async def answer_node(state: GraphState) -> dict[str, str]:
            result = await self._invoke_model(state["prompt"])
            return {"answer": _content(result)}

        graph.add_node("answer", answer_node)
        graph.add_edge(sdk.START, "answer")
        graph.add_edge("answer", sdk.END)
        return graph.compile(checkpointer=self.checkpointer)

    def _build_approval_graph(self):
        sdk = load_langgraph_sdk()
        graph = sdk.StateGraph(GraphState)

        async def research_node(state: GraphState) -> dict[str, str]:
            result = await self._invoke_model(state["task"])
            return {"research": _content(result)}

        def approval_node(state: GraphState) -> dict[str, str]:
            value = sdk.interrupt(
                {
                    "type": "approval",
                    "task": state["task"],
                    "research": state.get("research", ""),
                }
            )
            return {"approval": str(value)}

        async def writing_node(state: GraphState) -> dict[str, str]:
            prompt = (
                f"研究：{state.get('research', '')}\n"
                f"审批：{state.get('approval', '')}"
            )
            result = await self._invoke_model(prompt)
            return {"draft": _content(result)}

        graph.add_node("research", research_node)
        graph.add_node("approval", approval_node)
        graph.add_node("writing", writing_node)
        graph.add_edge(sdk.START, "research")
        graph.add_edge("research", "approval")
        graph.add_edge("approval", "writing")
        graph.add_edge("writing", sdk.END)
        return graph.compile(checkpointer=self.checkpointer)

    async def _invoke_model(self, prompt: str) -> Any:
        if hasattr(self.model, "ainvoke"):
            result = self.model.ainvoke(prompt)
        else:
            result = self.model(prompt)
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    async def _emit(sink: EventSink | None, event: AgentEvent) -> None:
        if sink is None:
            return
        result = sink(event)
        if inspect.isawaitable(result):
            await result

    @staticmethod
    def _delta(previous: str, current: str) -> str:
        current = str(current or "")
        if previous and current.startswith(previous):
            return current[len(previous):]
        return current

    @staticmethod
    def _raise_if_cancelled(cancel_token: CancellationToken | None) -> None:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()

    async def aclose(self) -> None:
        close = getattr(self.model, "aclose", None) or getattr(self.model, "close", None)
        if close is None:
            return
        result = close()
        if inspect.isawaitable(result):
            await result
