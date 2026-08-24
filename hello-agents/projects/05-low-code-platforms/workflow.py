"""工程层低代码工作流：节点、路由、SQLite、审批和工具权限。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import sqlite3
from time import perf_counter, time
from typing import Callable
from uuid import uuid4

from tools import ToolRegistry, ToolSpec, send_email_tool


class NodeInputError(ValueError):
    """节点需要的状态字段不存在或为空。"""


class WorkflowStateError(RuntimeError):
    """工作流状态不允许当前操作。"""


@dataclass
class WorkflowState:
    question: str
    workflow_id: str = field(default_factory=lambda: str(uuid4()))
    normalized: str = ""
    route: str = ""
    answer: str = ""
    status: str = "running"
    failure: str = ""
    approval_id: str | None = None
    approval_expires_at: float | None = None
    tool_result: str = ""
    permissions: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    completed_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        return cls(**data)


class SQLiteStateStore:
    """用 SQLite 保存工作流状态和本地 outbox，替换原来的 JSON 文件。"""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflow_states (
                workflow_id TEXT PRIMARY KEY,
                approval_id TEXT UNIQUE,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                idempotency_key TEXT NOT NULL UNIQUE,
                recipient TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        self.connection.commit()

    def save(self, state: WorkflowState) -> None:
        self.connection.execute(
            """
            INSERT INTO workflow_states(workflow_id, approval_id, status, payload, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                approval_id=excluded.approval_id,
                status=excluded.status,
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """ ,
            (state.workflow_id, state.approval_id, state.status, json.dumps(state.to_dict(), ensure_ascii=False), time()),
        )
        self.connection.commit()

    def load(self, *, workflow_id: str | None = None, approval_id: str | None = None) -> WorkflowState:
        if not workflow_id and not approval_id:
            raise ValueError("workflow_id 和 approval_id 至少提供一个")
        if workflow_id:
            row = self.connection.execute(
                "SELECT payload FROM workflow_states WHERE workflow_id = ?", (workflow_id,)
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT payload FROM workflow_states WHERE approval_id = ?", (approval_id,)
            ).fetchone()
        if row is None:
            raise FileNotFoundError("找不到工作流状态")
        return WorkflowState.from_dict(json.loads(row["payload"]))

    def load_latest(self) -> WorkflowState:
        row = self.connection.execute(
            "SELECT payload FROM workflow_states ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row is None:
            raise FileNotFoundError("找不到工作流状态")
        return WorkflowState.from_dict(json.loads(row["payload"]))

    def save_outbox(self, *, idempotency_key: str, recipient: str, body: str) -> dict:
        self.connection.execute(
            "INSERT OR IGNORE INTO outbox(idempotency_key, recipient, body, created_at) VALUES (?, ?, ?, ?)",
            (idempotency_key, recipient, body, time()),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT id, idempotency_key, recipient, body FROM outbox WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        return dict(row)

    def count_outbox(self) -> int:
        return int(self.connection.execute("SELECT COUNT(*) FROM outbox").fetchone()[0])

    def close(self) -> None:
        self.connection.close()


@dataclass(frozen=True)
class NodeSpec:
    name: str
    required_inputs: tuple[str, ...]
    output_keys: tuple[str, ...]
    execute: Callable[[WorkflowState], WorkflowState]

    def run(self, state: WorkflowState) -> WorkflowState:
        missing = [key for key in self.required_inputs if not getattr(state, key, None)]
        if missing:
            raise NodeInputError(f"节点 {self.name} 缺少输入：{', '.join(missing)}")
        next_state = self.execute(state)
        missing_outputs = [key for key in self.output_keys if not getattr(next_state, key, None)]
        if missing_outputs:
            raise NodeInputError(f"节点 {self.name} 没有产生输出：{', '.join(missing_outputs)}")
        return next_state


def normalize_node(state: WorkflowState) -> WorkflowState:
    state.normalized = state.question.strip()
    return state


def route_node(state: WorkflowState) -> WorkflowState:
    high_risk_words = ("发送", "付款", "删除", "发布", "下单")
    chat_words = ("你好", "嗨", "再见", "闲聊", "介绍一下你自己")
    if any(word in state.normalized for word in chat_words):
        state.route = "chat"
    elif any(word in state.normalized for word in high_risk_words):
        state.route = "approval"
    else:
        state.route = "knowledge"
    return state


def make_tool_node(registry: ToolRegistry) -> Callable[[WorkflowState], WorkflowState]:
    def tool_node(state: WorkflowState) -> WorkflowState:
        state.tool_result = registry.execute(
            "send_email",
            state,
            idempotency_key=f"{state.workflow_id}:send_email",
        )
        return state

    return tool_node


def answer_node(state: WorkflowState) -> WorkflowState:
    action_id = f"{state.workflow_id}:answer"
    if action_id in state.completed_actions:
        return state
    if state.route == "chat":
        state.answer = "你好，我是课程工作流助手。"
    elif state.route == "approval":
        if not state.tool_result:
            raise NodeInputError("高风险回答缺少工具结果")
        state.answer = f"已通过审批，工具执行结果：{state.tool_result}"
    else:
        state.answer = "从知识库回答：" + state.normalized
    state.completed_actions.append(action_id)
    return state


class WorkflowRunner:
    """节点调度器：负责错误、耗时、审批、恢复、终止和持久化。"""

    def __init__(
        self,
        nodes: dict[str, NodeSpec],
        *,
        store: SQLiteStateStore,
        max_steps: int = 10,
        approval_timeout_seconds: float = 300,
        clock: Callable[[], float] = time,
    ):
        if max_steps < 1:
            raise ValueError("max_steps 必须大于 0")
        if approval_timeout_seconds <= 0:
            raise ValueError("approval_timeout_seconds 必须大于 0")
        self.nodes = nodes
        self.store = store
        self.max_steps = max_steps
        self.approval_timeout_seconds = approval_timeout_seconds
        self.clock = clock
        self._states: dict[str, WorkflowState] = {}

    def _save(self, state: WorkflowState) -> None:
        self._states[state.workflow_id] = state
        self.store.save(state)

    @staticmethod
    def _record(state: WorkflowState, node: str, action: str, duration_ms: float = 0.0) -> None:
        state.events.append({
            "node": node,
            "action": action,
            "status": state.status,
            "duration_ms": round(duration_ms, 3),
            "state": {
                "normalized": state.normalized,
                "route": state.route,
                "answer": state.answer,
                "tool_result": state.tool_result,
            },
        })

    def _failed(self, state: WorkflowState, reason: str, node: str = "runtime", duration_ms: float = 0.0) -> WorkflowState:
        state.status = "failed"
        state.failure = reason
        state.answer = "工作流失败：" + reason
        self._record(state, node, "failed", duration_ms)
        self._save(state)
        return state

    def run(self, question: str) -> WorkflowState:
        return self.run_state(WorkflowState(question=question), start="normalize")

    def run_state(self, state: WorkflowState, *, start: str) -> WorkflowState:
        if state.status in {"completed", "rejected", "failed", "waiting_approval"} and start != "answer" and start != "tool":
            self._save(state)
            return state
        current = start
        steps = 0
        while current:
            if steps >= self.max_steps:
                return self._failed(state, f"超过最大步数 {self.max_steps}")
            started = perf_counter()
            try:
                node = self.nodes[current]
                state = node.run(state)
            except Exception as error:
                return self._failed(state, str(error), node=current, duration_ms=(perf_counter() - started) * 1000)
            duration_ms = (perf_counter() - started) * 1000
            steps += 1
            if node.name == "answer":
                state.status = "completed"
            self._record(state, node.name, node.name, duration_ms)

            if node.name == "route" and state.route == "approval":
                state.status = "waiting_approval"
                state.approval_id = state.approval_id or f"approval-{state.workflow_id}"
                state.approval_expires_at = self.clock() + self.approval_timeout_seconds
                state.answer = "等待人工审批：" + state.normalized
                self._record(state, "approval", "pause")
                self._save(state)
                return state
            if node.name == "answer":
                self._save(state)
                return state
            current = {"normalize": "route", "route": "answer", "tool": "answer"}.get(node.name)
            if node.name == "route" and state.route == "approval":
                current = None
        return self._failed(state, "工作流没有终止节点")

    def resume(self, approval_id: str | None, *, approved: bool) -> WorkflowState:
        if not approval_id:
            raise WorkflowStateError("缺少 approval_id")
        try:
            state = self.store.load(approval_id=approval_id)
        except FileNotFoundError:
            state = self._states.get(approval_id.removeprefix("approval-"))
        if state is None or state.approval_id != approval_id:
            raise WorkflowStateError("找不到待审批工作流")
        if state.status in {"completed", "rejected", "failed"}:
            return state
        if state.status != "waiting_approval":
            raise WorkflowStateError(f"当前状态不能审批：{state.status}")
        if state.approval_expires_at is not None and self.clock() > state.approval_expires_at:
            return self._failed(state, "审批已超时", node="approval")
        if not approved:
            state.status = "rejected"
            state.answer = "人工审批拒绝，工作流结束。"
            self._record(state, "approval", "reject")
            self._save(state)
            return state
        state.status = "running"
        state.permissions.append("send_email")
        self._record(state, "approval", "approve")
        return self.run_state(state, start="tool")


def build_workflow(
    *,
    store: SQLiteStateStore | None = None,
    max_steps: int = 10,
    approval_timeout_seconds: float = 300,
    clock: Callable[[], float] = time,
) -> WorkflowRunner:
    store = store or SQLiteStateStore(":memory:")
    registry = ToolRegistry(store)
    registry.register(ToolSpec("send_email", "send_email", send_email_tool))
    nodes = {
        "normalize": NodeSpec("normalize", ("question",), ("normalized",), normalize_node),
        "route": NodeSpec("route", ("normalized",), ("route",), route_node),
        "tool": NodeSpec("tool", ("normalized", "route"), ("tool_result",), make_tool_node(registry)),
        "answer": NodeSpec("answer", ("normalized", "route"), ("answer",), answer_node),
    }
    return WorkflowRunner(
        nodes,
        store=store,
        max_steps=max_steps,
        approval_timeout_seconds=approval_timeout_seconds,
        clock=clock,
    )
