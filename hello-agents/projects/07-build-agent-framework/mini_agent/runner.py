"""Bounded Agent loop that composes Model, Policy, ToolRegistry and Memory."""

from __future__ import annotations

import json
import re
from time import perf_counter, time
from typing import Any, Callable

from .contracts import Action, AgentEvent, Message, ModelResponse, RunResult
from .errors import FrameworkError, RetryableToolError, ToolExecutionError
from .memory import Memory, SQLiteCheckpointStore
from .policy import Policy
from .tools import ToolRegistry


class Runner:
    """Execute a finite tool-using loop and persist every completed step."""

    def __init__(
        self,
        *,
        model: Any,
        tools: ToolRegistry,
        policy: Policy | None = None,
        permissions: set[str] | frozenset[str] | None = None,
        max_steps: int = 5,
        tool_max_attempts: int = 1,
        pause_after_step: int | None = None,
        checkpoint_store: SQLiteCheckpointStore | None = None,
        on_event: Callable[[AgentEvent], None] | None = None,
    ):
        if max_steps < 1:
            raise ValueError("max_steps 必须大于 0")
        if tool_max_attempts < 1:
            raise ValueError("tool_max_attempts 必须大于 0")
        if pause_after_step is not None and pause_after_step < 1:
            raise ValueError("pause_after_step 必须大于 0")
        self.model = model
        self.tools = tools
        self.policy = policy or Policy()
        self.permissions = frozenset(permissions or set())
        self.max_steps = max_steps
        self.tool_max_attempts = tool_max_attempts
        self.pause_after_step = pause_after_step
        self.checkpoint_store = checkpoint_store or SQLiteCheckpointStore(":memory:")
        self.on_event = on_event

    def run(self, task: str) -> RunResult:
        memory = Memory(task=task)
        memory.add_message(Message(role="user", content=task))
        return self._run_memory(memory)

    def resume(self, run_id: str) -> RunResult:
        memory = self.checkpoint_store.load(run_id)
        if memory.status in {"completed", "failed"}:
            return self._result(memory)
        return self._run_memory(memory)

    def _run_memory(self, memory: Memory) -> RunResult:
        memory.status = "running"
        self._record(memory, "run_started", step=memory.step)
        self.checkpoint_store.save(memory)

        try:
            while memory.step < self.max_steps:
                memory.step += 1
                response_started = perf_counter()
                raw_response = self.model.generate(
                    list(memory.messages),
                    self.tools.schemas(),
                )
                response = (
                    raw_response
                    if isinstance(raw_response, ModelResponse)
                    else ModelResponse(action=self.policy.parse(raw_response))
                )
                memory.total_usage_tokens += response.usage_tokens
                action = self.policy.parse(response)

                if action.kind == "final":
                    memory.add_message(
                        Message(role="assistant", content=action.content or "")
                    )
                    memory.completed_steps.append(memory.step)
                    memory.status = "completed"
                    self._record(
                        memory,
                        "run_completed",
                        step=memory.step,
                        duration_ms=(perf_counter() - response_started) * 1000,
                        usage_tokens=response.usage_tokens,
                    )
                    self.checkpoint_store.save(memory)
                    return self._result(memory, answer=action.content or "")

                tool_call = action.tool_call
                if tool_call is None:
                    raise FrameworkError("tool_call action 缺少工具调用")

                memory.add_message(
                    Message(
                        role="assistant",
                        content=json.dumps(action.to_dict(), ensure_ascii=False),
                    )
                )
                observation = self._execute_tool(memory, tool_call.name, tool_call.arguments)
                memory.add_message(
                    Message(
                        role="tool",
                        name=tool_call.name,
                        content=self._serialize_observation(observation),
                    )
                )
                memory.completed_steps.append(memory.step)
                self.checkpoint_store.save(memory)
                if self.pause_after_step == memory.step:
                    memory.status = "paused"
                    self._record(memory, "checkpoint", step=memory.step)
                    self.checkpoint_store.save(memory)
                    return self._result(memory)

            memory.status = "max_steps"
            memory.error = f"超过最大步数 {self.max_steps}"
            self._record(memory, "max_steps", step=memory.step, error=memory.error)
            self.checkpoint_store.save(memory)
            return self._result(memory)
        except Exception as error:
            memory.status = "failed"
            memory.error = self._safe_error(error)
            self._record(memory, "run_failed", step=memory.step, error=memory.error)
            self.checkpoint_store.save(memory)
            return self._result(memory)

    def _execute_tool(self, memory: Memory, name: str, arguments: dict[str, Any]) -> Any:
        started = perf_counter()
        self._record(memory, "tool_started", step=memory.step, metadata={"tool": name})
        for attempt in range(1, self.tool_max_attempts + 1):
            try:
                result = self.tools.execute(name, arguments, self.permissions)
                self._record(
                    memory,
                    "tool_completed",
                    step=memory.step,
                    duration_ms=(perf_counter() - started) * 1000,
                    metadata={"tool": name, "attempt": attempt},
                )
                return result
            except RetryableToolError as error:
                if not self.tools.get(name).retryable:
                    raise ToolExecutionError(str(error)) from error
                if attempt >= self.tool_max_attempts:
                    raise ToolExecutionError(str(error)) from error
                self._record(
                    memory,
                    "retry_scheduled",
                    step=memory.step,
                    metadata={"tool": name, "attempt": attempt + 1},
                    error=self._safe_error(error),
                )
            except FrameworkError:
                raise
            except Exception as error:
                raise ToolExecutionError(
                    f"工具 {name} 执行失败：{self._safe_error(error)}"
                ) from error
        raise ToolExecutionError(f"工具执行失败：{name}")

    def _record(
        self,
        memory: Memory,
        phase: str,
        *,
        step: int,
        duration_ms: float | None = None,
        usage_tokens: int | None = None,
        metadata: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        event = AgentEvent(
            run_id=memory.run_id,
            step=step,
            phase=phase,
            duration_ms=duration_ms,
            usage_tokens=usage_tokens,
            metadata=self._redact_metadata(metadata or {}),
            error=self._safe_error_text(error),
        )
        memory.add_event(event)
        if self.on_event is not None:
            try:
                self.on_event(event)
            except Exception:
                pass

    @staticmethod
    def _serialize_observation(value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _result(memory: Memory, *, answer: str = "") -> RunResult:
        if not answer:
            for message in reversed(memory.messages):
                if message.role == "assistant":
                    answer = message.content
                    break
        return RunResult(
            status=memory.status,
            answer=answer,
            steps=memory.step,
            run_id=memory.run_id,
            messages=list(memory.messages),
            events=list(memory.events),
            error=memory.error,
            total_usage_tokens=memory.total_usage_tokens,
        )

    @staticmethod
    def _redact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        sensitive = {"api_key", "apikey", "authorization", "cookie", "password", "token"}
        return {
            key: "[REDACTED]" if key.lower() in sensitive else value
            for key, value in metadata.items()
        }

    @staticmethod
    def _safe_error_text(value: str) -> str:
        return re.sub(
            r"(?i)(api[_-]?key|authorization|cookie|password|token)"
            r"(\s*[:=]\s*)([^\s,;]+)",
            r"\1\2[REDACTED]",
            value or "",
        )[:500]

    @classmethod
    def _safe_error(cls, error: Exception) -> str:
        return cls._safe_error_text(str(error) or error.__class__.__name__)
