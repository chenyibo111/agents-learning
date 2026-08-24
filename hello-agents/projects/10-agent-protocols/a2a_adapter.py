"""A2A-style client facade over the local JSON-RPC task methods."""

from __future__ import annotations

from typing import Any

from protocol_engine.contracts import JsonRpcRequest, TaskEnvelope, TaskState
from protocol_engine.errors import ProtocolError
from protocol_engine.server import ProtocolServer


class A2AClient:
    def __init__(self, server: ProtocolServer, *, token: str):
        self.server = server
        self.token = token
        self._counter = 0

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        self._counter += 1
        response = self.server.handle(
            JsonRpcRequest(id=f"a2a-client-{self._counter}", method=method, params=params),
            token=self.token,
        )
        if response.error:
            raise ProtocolError(response.error["code"], response.error["message"], response.error.get("data"))
        return response.result

    def submit(self, capability: str, input: dict[str, Any], *, task_id: str | None = None, run: bool = False) -> TaskEnvelope:
        result = self._call("tasks/submit", {"capability": capability, "input": input, "task_id": task_id, "run": run})
        return _task_from_dict(result["task"])

    def get(self, task_id: str) -> TaskEnvelope:
        return _task_from_dict(self._call("tasks/get", {"task_id": task_id})["task"])

    def cancel(self, task_id: str) -> TaskEnvelope:
        return _task_from_dict(self._call("tasks/cancel", {"task_id": task_id})["task"])

    def run(self, task_id: str, *, timeout_seconds: float | None = None) -> TaskEnvelope:
        return _task_from_dict(self._call("tasks/run", {"task_id": task_id, "timeout_seconds": timeout_seconds})["task"])


def _task_from_dict(payload: dict[str, Any]) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=payload["task_id"],
        capability=payload["capability"],
        input=payload["input"],
        version=payload.get("version", "1.0"),
        status=TaskState(payload["status"]),
        created_at=payload.get("created_at", 0.0),
        deadline_at=payload.get("deadline_at"),
        result=payload.get("result"),
        error=payload.get("error"),
        idempotency_key=payload.get("idempotency_key"),
    )
