"""框架无关的多 Agent Runtime：消息、状态图、并行、检查点和观测。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sqlite3
from time import perf_counter, sleep, time
from typing import Any
from uuid import uuid4


@dataclass
class AgentMessage:
    """三种框架都可以适配到的统一消息结构。"""

    sender: str
    recipient: str
    content: str
    role: str = "assistant"
    usage_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentState:
    task: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "running"
    current_node: str = ""
    completed_nodes: list[str] = field(default_factory=list)
    results: dict[str, str] = field(default_factory=dict)
    messages: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""
    total_usage_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AgentState":
        return cls(**payload)


class SQLiteCheckpointStore:
    """保存每个 run 的完整状态，模拟框架中的 checkpointer。"""

    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS checkpoints (run_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at REAL NOT NULL)"
        )
        self.connection.commit()

    def save(self, state: AgentState) -> None:
        self.connection.execute(
            """
            INSERT INTO checkpoints(run_id, payload, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
            """,
            (state.run_id, json.dumps(state.to_dict(), ensure_ascii=False), time()),
        )
        self.connection.commit()

    def load(self, run_id: str) -> AgentState:
        row = self.connection.execute("SELECT payload FROM checkpoints WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"找不到 checkpoint: {run_id}")
        return AgentState.from_dict(json.loads(row["payload"]))


class BaseAdapter:
    """真实框架只需实现 respond，即可接入同一个 Runtime。"""

    framework_name = "framework-neutral"

    def respond(self, agent: str, prompt: str) -> AgentMessage:
        if agent == "research":
            content = "研究结果：Agent 由模型、工具、状态和 Runtime 组成。"
        elif agent == "critic":
            content = "审查结果：需要明确消息格式、终止条件和失败恢复。"
        else:
            content = f"写作草稿：根据资料整理“{prompt}”。"
        return AgentMessage(
            sender=agent,
            recipient="runtime",
            content=content,
            usage_tokens=max(1, len(content) // 4),
            metadata={"framework": self.framework_name},
        )


class ScriptedAdapter(BaseAdapter):
    """可控的测试适配器，用来模拟失败和慢调用。"""

    framework_name = "scripted"

    def __init__(self, *, fail_on: str | None = None, delay_seconds: float = 0):
        self.fail_on = fail_on
        self.delay_seconds = delay_seconds

    def respond(self, agent: str, prompt: str) -> AgentMessage:
        if self.delay_seconds:
            sleep(self.delay_seconds)
        if self.fail_on == agent:
            raise RuntimeError(f"Agent {agent} 执行失败")
        return super().respond(agent, prompt)


class AutoGenStyleAdapter(BaseAdapter):
    framework_name = "autogen-style"


class AgentScopeStyleAdapter(BaseAdapter):
    framework_name = "agentscope-style"


class LangGraphStyleAdapter(BaseAdapter):
    framework_name = "langgraph-style"


def build_adapters() -> list[BaseAdapter]:
    """返回三个风格相同、边界不同的教学适配器。"""
    return [AutoGenStyleAdapter(), AgentScopeStyleAdapter(), LangGraphStyleAdapter()]


class AgentRuntime:
    """负责节点调度、并行汇总、检查点、超时和成本事件。"""

    def __init__(
        self,
        adapter: BaseAdapter,
        *,
        checkpoint_store: SQLiteCheckpointStore | None = None,
        timeout_seconds: float = 10,
        max_steps: int = 8,
    ):
        if timeout_seconds <= 0 or max_steps < 1:
            raise ValueError("timeout_seconds 必须大于 0，max_steps 必须大于 0")
        self.adapter = adapter
        self.checkpoint_store = checkpoint_store or SQLiteCheckpointStore(":memory:")
        self.timeout_seconds = timeout_seconds
        self.max_steps = max_steps

    def _save(self, state: AgentState) -> None:
        self.checkpoint_store.save(state)

    @staticmethod
    def _event(state: AgentState, node: str, phase: str, duration_ms: float, usage_tokens: int = 0, error: str = "") -> None:
        state.events.append({
            "node": node,
            "phase": phase,
            "duration_ms": round(duration_ms, 3),
            "usage_tokens": usage_tokens,
            "error": error,
        })

    def _call(self, state: AgentState, agent: str, prompt: str) -> AgentMessage:
        started = perf_counter()
        message = self.adapter.respond(agent, prompt)
        elapsed = perf_counter() - started
        if elapsed > self.timeout_seconds:
            raise TimeoutError(f"Agent {agent} 超时：{elapsed:.3f}s")
        state.total_usage_tokens += message.usage_tokens
        state.messages.append(message.to_dict())
        return message

    def _fail(self, state: AgentState, node: str, error: Exception, started: float) -> AgentState:
        state.status = "failed"
        state.current_node = node
        state.error = str(error)
        self._event(state, node, "failed", (perf_counter() - started) * 1000, error=str(error))
        self._save(state)
        return state

    def _research(self, state: AgentState) -> None:
        state.current_node = "research"
        message = self._call(state, "research", state.task)
        state.results["research"] = message.content
        if "research" not in state.completed_nodes:
            state.completed_nodes.append("research")

    def _critic(self, state: AgentState) -> None:
        state.current_node = "critic"
        message = self._call(state, "critic", state.task)
        state.results["critic"] = message.content
        if "critic" not in state.completed_nodes:
            state.completed_nodes.append("critic")

    def _writing(self, state: AgentState) -> None:
        state.current_node = "writing"
        prompt = "\n".join(state.results.values())
        message = self._call(state, "writing", prompt)
        state.results["draft"] = message.content
        if "writing" not in state.completed_nodes:
            state.completed_nodes.append("writing")

    def run_serial(self, task: str, *, stop_after: str | None = None) -> AgentState:
        state = AgentState(task=task)
        return self._run_serial_state(state, stop_after=stop_after)

    def _run_serial_state(self, state: AgentState, *, stop_after: str | None = None) -> AgentState:
        steps = 0
        for node, function in (("research", self._research), ("writing", self._writing)):
            if node in state.completed_nodes:
                continue
            if steps >= self.max_steps:
                return self._fail(state, node, RuntimeError(f"超过最大步数 {self.max_steps}"), perf_counter())
            started = perf_counter()
            try:
                function(state)
            except Exception as error:
                return self._fail(state, node, error, started)
            self._event(state, node, "execute", (perf_counter() - started) * 1000)
            self._save(state)
            steps += 1
            if stop_after == node:
                state.status = "paused"
                self._event(state, node, "checkpoint", 0)
                self._save(state)
                return state
        state.status = "completed"
        state.current_node = "end"
        self._save(state)
        return state

    def run_parallel(self, task: str) -> AgentState:
        state = AgentState(task=task)
        started = perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    pool.submit(self.adapter.respond, "research", task): "research",
                    pool.submit(self.adapter.respond, "critic", task): "critic",
                }
                messages: dict[str, AgentMessage] = {}
                for future in as_completed(futures):
                    name = futures[future]
                    message = future.result()
                    messages[name] = message
                    state.total_usage_tokens += message.usage_tokens
                    state.messages.append(message.to_dict())
            if perf_counter() - started > self.timeout_seconds:
                raise TimeoutError("并行 Agent 汇总超时")
            for name in ("research", "critic"):
                state.results[name] = messages[name].content
                state.completed_nodes.append(name)
            self._event(state, "fan-out", "parallel", (perf_counter() - started) * 1000)
            self._save(state)
            writing_started = perf_counter()
            self._writing(state)
            self._event(state, "writing", "fan-in", (perf_counter() - writing_started) * 1000)
            state.status = "completed"
            state.current_node = "end"
            self._save(state)
            return state
        except Exception as error:
            return self._fail(state, "parallel", error, started)

    def resume(self, run_id: str) -> AgentState:
        state = self.checkpoint_store.load(run_id)
        if state.status == "completed":
            return state
        if state.status == "failed":
            return state
        return self._run_serial_state(state)


def demo() -> dict[str, Any]:
    results = {}
    for adapter in build_adapters():
        result = AgentRuntime(adapter).run_serial("总结 Agent")
        results[adapter.framework_name] = result.to_dict()
    parallel = AgentRuntime(build_adapters()[0]).run_parallel("总结 Agent")
    results["parallel"] = parallel.to_dict()
    return results
