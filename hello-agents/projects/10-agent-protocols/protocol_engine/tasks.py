"""A2A-style task envelopes and a small lifecycle manager."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import time
import uuid
from collections.abc import Callable
from typing import Any

from .contracts import TaskEnvelope, TaskState
from .errors import ErrorCode, ProtocolError


_ALLOWED_TRANSITIONS = {
    TaskState.SUBMITTED: {TaskState.WORKING, TaskState.CANCELLED, TaskState.EXPIRED, TaskState.FAILED},
    TaskState.WORKING: {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED, TaskState.EXPIRED},
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
    TaskState.EXPIRED: set(),
}


class TaskManager:
    def __init__(self, *, clock: Callable[[], float] = time.time):
        self.clock = clock
        self._tasks: dict[str, TaskEnvelope] = {}

    def submit(
        self,
        capability: str,
        input: dict[str, Any],
        *,
        task_id: str | None = None,
        version: str = "1.0",
        deadline_seconds: float | None = None,
        idempotency_key: str | None = None,
    ) -> TaskEnvelope:
        actual_id = task_id or str(uuid.uuid4())
        if actual_id in self._tasks:
            raise ProtocolError(ErrorCode.DUPLICATE_TASK, "task_id 已存在")
        created_at = self.clock()
        task = TaskEnvelope(
            task_id=actual_id,
            capability=capability,
            input=dict(input),
            version=version,
            created_at=created_at,
            deadline_at=(created_at + deadline_seconds) if deadline_seconds is not None else None,
            idempotency_key=idempotency_key,
        )
        self._tasks[actual_id] = task
        return task

    def get(self, task_id: str) -> TaskEnvelope:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ProtocolError(ErrorCode.TASK_NOT_FOUND, "任务不存在") from exc

    def transition(
        self,
        task_id: str,
        status: TaskState,
        *,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> TaskEnvelope:
        task = self.get(task_id)
        if status not in _ALLOWED_TRANSITIONS[task.status]:
            raise ProtocolError(ErrorCode.INVALID_STATE, f"不能从 {task.status.value} 转换到 {status.value}")
        task.status = status
        if result is not None:
            task.result = result
        if error is not None:
            task.error = error
        return task

    def cancel(self, task_id: str) -> TaskEnvelope:
        return self.transition(
            task_id,
            TaskState.CANCELLED,
            error={"code": int(ErrorCode.CANCELLED), "message": "任务已取消"},
        )

    def run(self, task_id: str, handler: Callable[[TaskEnvelope], Any], *, timeout_seconds: float | None = None) -> TaskEnvelope:
        task = self.get(task_id)
        if task.status is TaskState.CANCELLED:
            return task
        if task.deadline_at is not None and self.clock() >= task.deadline_at:
            return self.transition(task_id, TaskState.EXPIRED, error={"code": int(ErrorCode.TIMEOUT), "message": "任务已超时"})
        if task.deadline_at is not None:
            remaining = task.deadline_at - self.clock()
            timeout_seconds = remaining if timeout_seconds is None else min(timeout_seconds, remaining)
        self.transition(task_id, TaskState.WORKING)
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(handler, task)
        try:
            result = future.result(timeout=timeout_seconds)
        except FutureTimeout:
            future.cancel()
            return self.transition(task_id, TaskState.EXPIRED, error={"code": int(ErrorCode.TIMEOUT), "message": "任务执行超时"})
        except Exception:
            return self.transition(task_id, TaskState.FAILED, error={"code": int(ErrorCode.INTERNAL_ERROR), "message": "任务执行失败"})
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        if task.status is TaskState.CANCELLED:
            return task
        return self.transition(task_id, TaskState.COMPLETED, result=result)
