"""Unified JSON-RPC dispatcher for MCP-style and A2A-style methods."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

from .auth import AuthContext, Authorizer
from .codec import decode_request
from .contracts import JsonRpcRequest, JsonRpcResponse, TaskState
from .errors import ErrorCode, ProtocolError
from .idempotency import IdempotencyStore, request_fingerprint
from .registry import CapabilityRegistry
from .replay import ReplayGuard
from .tasks import TaskManager
from .versioning import negotiate_version


class ProtocolServer:
    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        authorizer: Authorizer,
        task_manager: TaskManager | None = None,
        supported_versions: Iterable[str] = ("1.0",),
        replay_guard: ReplayGuard | None = None,
        idempotency: IdempotencyStore | None = None,
    ):
        self.registry = registry
        self.authorizer = authorizer
        self.task_manager = task_manager or TaskManager()
        self.supported_versions = tuple(supported_versions)
        self.replay_guard = replay_guard or ReplayGuard()
        self.idempotency = idempotency or IdempotencyStore()
        self._task_handlers: dict[str, tuple[Callable[[Any], Any], frozenset[str]]] = {}

    def register_task_handler(self, capability: str, handler: Callable[[Any], Any], *, required_scopes: Iterable[str] = ()) -> None:
        self._task_handlers[capability] = (handler, frozenset(required_scopes))

    def handle(
        self,
        payload: JsonRpcRequest | str | bytes | dict[str, Any],
        *,
        token: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> JsonRpcResponse:
        request_id: str | int | None = None
        try:
            request = payload if isinstance(payload, JsonRpcRequest) else decode_request(payload)
            request_id = request.id
            metadata = request.params.get("_meta", {})
            if not isinstance(metadata, dict):
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "_meta 必须是 JSON 对象")
            negotiate_version(metadata.get("protocol_version", self.supported_versions[0]), self.supported_versions)
            context = auth_context or self.authorizer.authenticate(token)
            idempotency_key = metadata.get("idempotency_key")
            fingerprint = request_fingerprint(request.method, request.params)
            scoped_key = f"{context.principal}:{idempotency_key}" if idempotency_key else None
            if idempotency_key:
                cached = self.idempotency.lookup(scoped_key, fingerprint)
                if cached is not None:
                    return cached
            else:
                self.replay_guard.check(f"{context.principal}:{request.id}")
            result = self._dispatch(request.method, request.params, context)
            response = JsonRpcResponse.success(request.id, result)
            if scoped_key:
                self.idempotency.save(scoped_key, fingerprint, response)
            return response
        except ProtocolError as error:
            return JsonRpcResponse.failure(request_id, error)
        except Exception:
            return JsonRpcResponse.failure(request_id, ProtocolError(ErrorCode.INTERNAL_ERROR, "协议服务内部错误"))

    def _dispatch(self, method: str, params: dict[str, Any], context: AuthContext) -> dict[str, Any]:
        body = {key: value for key, value in params.items() if key != "_meta"}
        if method == "tools/list":
            return {"tools": self.registry.list_tools(), "protocol_version": self.supported_versions[0]}
        if method == "tools/call":
            name = body.get("name")
            if not isinstance(name, str):
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "tools/call 需要 name")
            value = self.registry.call_tool(name, body.get("arguments", {}), context)
            return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False), "structuredContent": value}]}
        if method == "resources/list":
            return {"resources": self.registry.list_resources(), "protocol_version": self.supported_versions[0]}
        if method == "resources/read":
            uri = body.get("uri")
            if not isinstance(uri, str):
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "resources/read 需要 uri")
            resource = self.registry.read_resource(uri, context)
            return {"contents": [{"uri": resource.uri, "mimeType": resource.mime_type, "text": resource.read()}]}
        if method == "tasks/submit":
            self.authorizer.require(context, {"tasks:submit"})
            capability = body.get("capability")
            task_input = body.get("input", {})
            if not isinstance(capability, str) or not isinstance(task_input, dict):
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "tasks/submit 需要 capability 和 object input")
            handler_record = self._task_handlers.get(capability)
            if handler_record is None:
                raise ProtocolError(ErrorCode.TOOL_NOT_FOUND, "任务能力不存在")
            self.authorizer.require(context, handler_record[1])
            task = self.task_manager.submit(
                capability,
                task_input,
                task_id=body.get("task_id"),
                version=body.get("version", self.supported_versions[0]),
                deadline_seconds=body.get("deadline_seconds"),
                idempotency_key=body.get("idempotency_key"),
            )
            if body.get("run"):
                task = self.task_manager.run(task.task_id, handler_record[0], timeout_seconds=body.get("timeout_seconds"))
            return {"task": task.to_dict()}
        if method == "tasks/get":
            self.authorizer.require(context, {"tasks:read"})
            task_id = body.get("task_id")
            if not isinstance(task_id, str):
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "tasks/get 需要 task_id")
            return {"task": self.task_manager.get(task_id).to_dict()}
        if method == "tasks/cancel":
            self.authorizer.require(context, {"tasks:cancel"})
            task_id = body.get("task_id")
            if not isinstance(task_id, str):
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "tasks/cancel 需要 task_id")
            return {"task": self.task_manager.cancel(task_id).to_dict()}
        if method == "tasks/run":
            self.authorizer.require(context, {"tasks:run"})
            task_id = body.get("task_id")
            task = self.task_manager.get(task_id) if isinstance(task_id, str) else None
            if task is None:
                raise ProtocolError(ErrorCode.INVALID_PARAMS, "tasks/run 需要 task_id")
            handler_record = self._task_handlers.get(task.capability)
            if handler_record is None:
                raise ProtocolError(ErrorCode.TOOL_NOT_FOUND, "任务能力不存在")
            self.authorizer.require(context, handler_record[1])
            return {"task": self.task_manager.run(task_id, handler_record[0], timeout_seconds=body.get("timeout_seconds")).to_dict()}
        raise ProtocolError(ErrorCode.METHOD_NOT_FOUND, "方法不存在")
