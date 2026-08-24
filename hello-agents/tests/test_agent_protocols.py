import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
import warnings


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "10-agent-protocols"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from a2a_adapter import A2AClient
from mcp_adapter import build_demo_server, run_demo
from protocol_engine.auth import AuthContext, Authorizer
from protocol_engine.codec import decode_request, encode_response
from protocol_engine.contracts import (
    JsonRpcRequest,
    JsonRpcResponse,
    ResourceDefinition,
    TaskState,
    ToolDefinition,
)
from protocol_engine.errors import ErrorCode, ProtocolError
from protocol_engine.registry import CapabilityRegistry
from protocol_engine.tasks import TaskManager
from protocol_engine.versioning import negotiate_version


MAIN_SPEC = importlib.util.spec_from_file_location(
    "lesson10_main",
    PROJECT / "main.py",
)
lesson10_main = importlib.util.module_from_spec(MAIN_SPEC)
assert MAIN_SPEC.loader is not None
MAIN_SPEC.loader.exec_module(lesson10_main)
if str(PROJECT) in sys.path:
    sys.path.remove(str(PROJECT))


class ContractTests(unittest.TestCase):
    def test_json_rpc_round_trip_is_json_safe(self):
        request = JsonRpcRequest(id="r-1", method="tools/list", params={})
        restored = decode_request(json.loads(json.dumps(request.to_dict())))
        response = JsonRpcResponse.success(request.id, {"ok": True})

        self.assertEqual(request, restored)
        self.assertEqual(response.to_dict(), json.loads(encode_response(response)))

    def test_contracts_expose_no_callable_or_secret_fields(self):
        tool = ToolDefinition(
            name="add",
            description="加法",
            input_schema={"type": "object"},
            handler=lambda arguments: arguments,
            required_scopes={"math:use"},
        )
        resource = ResourceDefinition(
            uri="lesson://10/intro",
            description="课程简介",
            content="MCP 与 A2A",
        )

        payload = json.dumps({"tool": tool.to_dict(), "resource": resource.to_dict()})

        self.assertNotIn("handler", payload)
        self.assertIn("lesson://10/intro", payload)

    def test_error_codes_are_stable_and_json_safe(self):
        error = ProtocolError(ErrorCode.FORBIDDEN, "需要 math:use")

        self.assertEqual(
            {"code": -32003, "message": "需要 math:use"},
            error.to_dict(),
        )

    def test_version_negotiation_requires_server_support(self):
        self.assertEqual("1.0", negotiate_version("1.0", ["1.0", "1.1"]))
        with self.assertRaises(ProtocolError) as context:
            negotiate_version("2.0", ["1.0"])
        self.assertEqual(ErrorCode.VERSION_MISMATCH, context.exception.code)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.server = build_demo_server()

    def request(self, method, params=None, request_id="request-1", token="demo-token"):
        return self.server.handle(
            JsonRpcRequest(id=request_id, method=method, params=params or {}),
            token=token,
        )

    def test_tools_list_and_call(self):
        listed = self.request("tools/list")
        called = self.request(
            "tools/call",
            {"name": "add_numbers", "arguments": {"a": 2, "b": 3}},
            request_id="call-1",
        )

        self.assertEqual("add_numbers", listed.result["tools"][0]["name"])
        self.assertEqual(5, called.result["content"][0]["structuredContent"])

    def test_tool_schema_and_permission_errors_are_protocol_errors(self):
        bad_arguments = self.request(
            "tools/call",
            {"name": "add_numbers", "arguments": {"a": "2", "b": 3}},
            request_id="bad-args",
        )
        forbidden = self.request(
            "tools/call",
            {"name": "add_numbers", "arguments": {"a": 2, "b": 3}},
            request_id="forbidden",
            token="read-only-token",
        )

        self.assertEqual(ErrorCode.INVALID_PARAMS, bad_arguments.error["code"])
        self.assertEqual(ErrorCode.FORBIDDEN, forbidden.error["code"])

    def test_resource_read_is_limited_to_registered_allowlist(self):
        found = self.request("resources/read", {"uri": "lesson://10/intro"}, "resource-1")
        missing = self.request("resources/read", {"uri": "file:///etc/passwd"}, "resource-2")

        self.assertIn("MCP", found.result["contents"][0]["text"])
        self.assertEqual(ErrorCode.RESOURCE_NOT_FOUND, missing.error["code"])

    def test_version_mismatch_is_rejected(self):
        response = self.request(
            "tools/list",
            {"_meta": {"protocol_version": "9.9"}},
            request_id="version-1",
        )

        self.assertEqual(ErrorCode.VERSION_MISMATCH, response.error["code"])

    def test_unknown_method_and_invalid_token_return_stable_errors(self):
        unknown = self.request("unknown/method", request_id="unknown-1")
        invalid_token = self.request("tools/call", {"name": "add_numbers", "arguments": {"a": 1, "b": 2}}, "auth-1", "not-a-real-token")

        self.assertEqual(ErrorCode.METHOD_NOT_FOUND, unknown.error["code"])
        self.assertEqual(ErrorCode.AUTH_REQUIRED, invalid_token.error["code"])

    def test_idempotency_returns_first_response_and_conflict_is_rejected(self):
        first = self.request(
            "tools/call",
            {
                "name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
                "_meta": {"idempotency_key": "same-call"},
            },
            request_id="idempotent-1",
        )
        repeated = self.request(
            "tools/call",
            {
                "name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
                "_meta": {"idempotency_key": "same-call"},
            },
            request_id="idempotent-2",
        )
        conflict = self.request(
            "tools/call",
            {
                "name": "add_numbers",
                "arguments": {"a": 4, "b": 3},
                "_meta": {"idempotency_key": "same-call"},
            },
            request_id="idempotent-3",
        )

        self.assertEqual(first.to_dict(), repeated.to_dict())
        self.assertEqual(ErrorCode.IDEMPOTENCY_CONFLICT, conflict.error["code"])

    def test_idempotency_cache_is_not_read_before_authentication(self):
        first = self.request(
            "tools/call",
            {
                "name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
                "_meta": {"idempotency_key": "protected-call"},
            },
            request_id="protected-1",
        )
        unauthorized = self.request(
            "tools/call",
            {
                "name": "add_numbers",
                "arguments": {"a": 2, "b": 3},
                "_meta": {"idempotency_key": "protected-call"},
            },
            request_id="protected-2",
            token="read-only-token",
        )

        self.assertIsNone(first.error)
        self.assertEqual(ErrorCode.FORBIDDEN, unauthorized.error["code"])

    def test_request_id_replay_is_rejected_without_idempotency_key(self):
        first = self.request("tools/list", request_id="replay-1")
        repeated = self.request("tools/list", request_id="replay-1")

        self.assertIsNone(first.error)
        self.assertEqual(ErrorCode.REPLAY_DETECTED, repeated.error["code"])


class TaskTests(unittest.TestCase):
    def test_a2a_task_lifecycle_and_invalid_transition(self):
        manager = TaskManager()
        task = manager.submit("summarize", {"text": "hello"}, task_id="task-1")

        manager.transition(task.task_id, TaskState.WORKING)
        manager.transition(task.task_id, TaskState.COMPLETED, result={"summary": "hello"})
        completed = manager.get(task.task_id)

        self.assertEqual(TaskState.COMPLETED, completed.status)
        self.assertEqual({"summary": "hello"}, completed.result)
        with self.assertRaises(ProtocolError) as context:
            manager.transition(task.task_id, TaskState.WORKING)
        self.assertEqual(ErrorCode.INVALID_STATE, context.exception.code)

    def test_timeout_marks_task_expired(self):
        manager = TaskManager()
        task = manager.submit("slow", {}, task_id="slow-1")

        result = manager.run(task.task_id, lambda _: time.sleep(0.05), timeout_seconds=0.001)

        self.assertEqual(TaskState.EXPIRED, result.status)
        self.assertEqual(ErrorCode.TIMEOUT, result.error["code"])

    def test_cancel_marks_submitted_task_cancelled(self):
        manager = TaskManager()
        task = manager.submit("summarize", {}, task_id="cancel-1")

        cancelled = manager.cancel(task.task_id)

        self.assertEqual(TaskState.CANCELLED, cancelled.status)
        self.assertEqual(ErrorCode.CANCELLED, cancelled.error["code"])

    def test_cancelled_working_task_does_not_become_completed_after_handler_returns(self):
        manager = TaskManager()
        task = manager.submit("slow", {}, task_id="working-cancel-1")
        manager.transition(task.task_id, TaskState.WORKING)
        cancelled = manager.cancel(task.task_id)

        result = manager.run(task.task_id, lambda _: "late-result", timeout_seconds=1)

        self.assertEqual(TaskState.CANCELLED, cancelled.status)
        self.assertEqual(TaskState.CANCELLED, result.status)

    def test_a2a_client_uses_task_envelopes(self):
        client = A2AClient(build_demo_server(), token="demo-token")

        submitted = client.submit("summarize", {"text": "协议"}, task_id="a2a-1")
        fetched = client.get("a2a-1")

        self.assertEqual(TaskState.SUBMITTED, submitted.status)
        self.assertEqual(submitted.to_dict(), fetched.to_dict())


class IntegrationTests(unittest.TestCase):
    def test_offline_demo_contains_mcp_and_a2a_evidence(self):
        result = run_demo()

        self.assertEqual(5, result["mcp"]["call"]["result"]["content"][0]["structuredContent"])
        self.assertEqual(TaskState.COMPLETED.value, result["a2a"]["status"])
        self.assertEqual("a2a-demo", lesson10_main.make_task()["protocol"])

    def test_custom_request_can_be_dispatched_as_json(self):
        response = lesson10_main.dispatch_request(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": "cli-1",
                    "method": "tools/list",
                    "params": {},
                }
            ),
            token="demo-token",
        )

        self.assertEqual("2.0", response["jsonrpc"])
        self.assertTrue(response["result"]["tools"])

    def test_malformed_request_is_returned_as_json_rpc_error(self):
        response = lesson10_main.dispatch_request("not-json")

        self.assertEqual(-32700, response["error"]["code"])

    def test_official_mcp_factory_is_optional_and_does_not_run_on_import(self):
        from mcp_adapter import build_official_mcp_server

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server = build_official_mcp_server()
        self.assertIsNotNone(server)


if __name__ == "__main__":
    unittest.main()
