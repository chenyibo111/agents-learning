"""Async Agent Runtime with lifecycle events, retry, cancellation and checkpoints."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import inspect
import re
from time import perf_counter, time
from typing import Any

from frameworks import AgentState, SQLiteCheckpointStore
from integrations.common import (
    AgentEvent,
    AsyncAgentAdapter,
    CancellationToken,
    EventSink,
    RunCancelled,
    RunTimeout,
    redact_metadata,
)
from retry import RetryPolicy, retry_async


async def noop_sleep(delay: float) -> None:
    """Injectable no-op sleep for deterministic tests."""


class RuntimeCancellationToken:
    """Cancellation boundary shared by Runtime and an adapter."""

    def __init__(self):
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def raise_if_cancelled(self) -> None:
        if self._cancelled:
            raise RunCancelled("Agent 运行已取消")


class AsyncAgentRuntime:
    """Run a small serial workflow without importing a concrete framework."""

    def __init__(
        self,
        adapter: AsyncAgentAdapter,
        *,
        checkpoint_store: SQLiteCheckpointStore | None = None,
        timeout_seconds: float = 10,
        retry_policy: RetryPolicy | None = None,
        sleep=asyncio.sleep,
    ):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        self.adapter = adapter
        self.checkpoint_store = checkpoint_store or SQLiteCheckpointStore(":memory:")
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.sleep = sleep
        self._active_tokens: dict[asyncio.Task[Any], RuntimeCancellationToken] = {}

    async def run(self, task: str) -> AgentState:
        """Start a new serial research → writing run."""

        return await self._run_state(AgentState(task=task))

    async def run_with_events(
        self,
        task: str,
    ) -> tuple[AgentState, list[AgentEvent]]:
        """Run a task and collect normalized events for tests or callers."""

        events: list[AgentEvent] = []

        async def collect(event: AgentEvent) -> None:
            events.append(event)

        state = await self._run_state(AgentState(task=task), collect)
        return state, events

    async def stream(self, task: str) -> AsyncIterator[AgentEvent]:
        """Yield lifecycle and adapter streaming events as they occur."""

        queue: asyncio.Queue[AgentEvent | object] = asyncio.Queue()
        sentinel = object()

        async def publish(event: AgentEvent) -> None:
            await queue.put(event)

        async def produce() -> None:
            try:
                await self._run_state(AgentState(task=task), publish)
            finally:
                await queue.put(sentinel)

        producer = asyncio.create_task(produce())
        try:
            while True:
                event = await queue.get()
                if event is sentinel:
                    break
                yield event
        finally:
            if not producer.done():
                producer.cancel()
            await producer

    async def resume(self, run_id: str) -> AgentState:
        """Resume a non-terminal checkpoint without repeating completed nodes."""

        state = self.checkpoint_store.load(run_id)
        if state.status in {"completed", "failed", "cancelled"}:
            return state
        return await self._run_state(state)

    async def cancel(self, task: asyncio.Task[Any]) -> None:
        """Cancel an active run task and propagate cancellation to its adapter."""

        token = self._active_tokens.get(task)
        if token is not None:
            token.cancel()
        task.cancel()

    async def _run_state(
        self,
        state: AgentState,
        sink: EventSink | None = None,
    ) -> AgentState:
        current_task = asyncio.current_task()
        token = RuntimeCancellationToken()
        if current_task is not None:
            self._active_tokens[current_task] = token

        state.status = "running"
        self.checkpoint_store.save(state)
        await self._record(state, "runtime", "run_started", sink=sink)

        try:
            await self._execute_serial(state, token, sink)
            state.status = "completed"
            state.current_node = "end"
            await self._record(state, "runtime", "run_completed", sink=sink)
            self.checkpoint_store.save(state)
            return state
        except (RunCancelled, asyncio.CancelledError) as error:
            token.cancel()
            state.status = "cancelled"
            state.error = self._safe_error(error) or "Agent 运行已取消"
            await self._record(
                state,
                state.current_node or "runtime",
                "run_cancelled",
                error=state.error,
                sink=sink,
            )
            self.checkpoint_store.save(state)
            return state
        except Exception as error:
            state.status = "failed"
            state.error = self._safe_error(error)
            await self._record(
                state,
                state.current_node or "runtime",
                "node_failed",
                error=state.error,
                sink=sink,
            )
            self.checkpoint_store.save(state)
            return state
        finally:
            if current_task is not None:
                self._active_tokens.pop(current_task, None)

    async def _execute_serial(
        self,
        state: AgentState,
        token: RuntimeCancellationToken,
        sink: EventSink | None,
    ) -> None:
        for node in ("research", "writing"):
            if node in state.completed_nodes:
                continue
            prompt = state.task if node == "research" else "\n".join(state.results.values())
            state.current_node = node
            started = perf_counter()
            await self._record(state, node, "node_started", sink=sink)
            message = await self._run_node(state, node, prompt, token, sink)
            state.results["research" if node == "research" else "draft"] = message.content
            state.completed_nodes.append(node)
            await self._record(
                state,
                node,
                "node_completed",
                duration_ms=(perf_counter() - started) * 1000,
                usage_tokens=message.usage_tokens,
                metadata=message.metadata,
                sink=sink,
            )
            self.checkpoint_store.save(state)

    async def _run_node(
        self,
        state: AgentState,
        node: str,
        prompt: str,
        token: RuntimeCancellationToken,
        sink: EventSink | None,
    ):
        async def operation(attempt: int):
            token.raise_if_cancelled()

            async def forward_adapter_event(event: AgentEvent) -> None:
                event.run_id = state.run_id
                event.node = node
                event.attempt = attempt
                event.metadata = redact_metadata(event.metadata)
                await self._record_existing(state, event, sink)

            try:
                message = await asyncio.wait_for(
                    self.adapter.respond(
                        node,
                        prompt,
                        on_event=forward_adapter_event,
                        cancel_token=token,
                    ),
                    timeout=self.timeout_seconds,
                )
            except asyncio.TimeoutError as error:
                raise RunTimeout(f"节点 {node} 超时") from error

            token.raise_if_cancelled()
            return message

        async def on_retry(attempt: int, error: Exception, delay: float) -> None:
            await self._record(
                state,
                node,
                "retry_scheduled",
                attempt=attempt + 1,
                metadata={"delay_seconds": delay},
                error=self._safe_error(error),
                sink=sink,
            )

        message = await retry_async(
            operation,
            policy=self.retry_policy,
            on_retry=on_retry,
            sleep=self.sleep,
        )
        message_payload = message.to_dict()
        message_payload["metadata"] = redact_metadata(
            message_payload.get("metadata", {})
        )
        state.messages.append(message_payload)
        state.total_usage_tokens += message.usage_tokens
        await self._record(
            state,
            node,
            "message_completed",
            usage_tokens=message.usage_tokens,
            metadata=message.metadata,
            sink=sink,
        )
        return message

    async def _record(
        self,
        state: AgentState,
        node: str,
        phase: str,
        *,
        duration_ms: float | None = None,
        usage_tokens: int | None = None,
        attempt: int = 1,
        metadata: dict[str, Any] | None = None,
        error: str = "",
        sink: EventSink | None = None,
    ) -> None:
        event = AgentEvent(
            run_id=state.run_id,
            node=node,
            phase=phase,
            timestamp=time(),
            duration_ms=duration_ms,
            usage_tokens=usage_tokens,
            attempt=attempt,
            metadata=redact_metadata(metadata or {}),
            error=error,
        )
        await self._record_existing(state, event, sink)

    async def _record_existing(
        self,
        state: AgentState,
        event: AgentEvent,
        sink: EventSink | None,
    ) -> None:
        state.events.append(event.to_dict())
        if sink is None:
            return
        try:
            result = sink(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            # Observability must not change the business result.
            return

    @staticmethod
    def _safe_error(error: BaseException) -> str:
        if isinstance(error, asyncio.CancelledError):
            return "Agent 运行已取消"
        text = str(error)
        text = re.sub(
            r"(?i)(api[_-]?key|authorization|cookie|password|token)"
            r"(\s*[:=]\s*)([^\s,;]+)",
            r"\1\2[REDACTED]",
            text,
        )
        return text[:500]
