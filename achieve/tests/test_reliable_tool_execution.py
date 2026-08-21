import importlib.util
import time
import unittest
from pathlib import Path


SOURCE_FILE = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "19-reliable-tool-execution"
    / "main.py"
)
SPEC = importlib.util.spec_from_file_location("reliable_tools", SOURCE_FILE)
assert SPEC and SPEC.loader
reliable_tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(reliable_tools)


def number_tool(handler):
    return reliable_tools.ToolSpec(
        name="add_numbers",
        description="计算两个数字的和",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
        handler=handler,
        max_attempts=3,
        base_delay=1.0,
    )


class ReliableToolExecutionTests(unittest.TestCase):
    def test_rejects_invalid_arguments_before_calling_tool(self) -> None:
        calls = 0

        def handler(_: dict[str, object]) -> int:
            nonlocal calls
            calls += 1
            return 0

        executor = reliable_tools.ToolExecutor({"add_numbers": number_tool(handler)})
        result = executor.execute("add_numbers", {"a": "not-a-number", "b": 2})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "validation_error")
        self.assertEqual(result["attempts"], 0)
        self.assertEqual(calls, 0)

    def test_retries_transient_error_and_then_succeeds(self) -> None:
        attempts = 0
        delays: list[float] = []

        def handler(arguments: dict[str, object]) -> float:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise reliable_tools.TransientToolError("temporary failure")
            return float(arguments["a"]) + float(arguments["b"])

        executor = reliable_tools.ToolExecutor(
            {"add_numbers": number_tool(handler)},
            sleep=delays.append,
        )
        result = executor.execute("add_numbers", {"a": 2, "b": 3})

        self.assertTrue(result["ok"])
        self.assertEqual(result["result"], 5.0)
        self.assertEqual(result["attempts"], 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_does_not_retry_non_retryable_error(self) -> None:
        calls = 0

        def handler(_: dict[str, object]) -> None:
            nonlocal calls
            calls += 1
            raise ValueError("invalid business operation")

        executor = reliable_tools.ToolExecutor(
            {"add_numbers": number_tool(handler)},
            sleep=lambda _: self.fail("普通业务错误不应该重试"),
        )
        result = executor.execute("add_numbers", {"a": 2, "b": 3})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "tool_error")
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(calls, 1)

    def test_timeout_returns_timeout_error_without_retry(self) -> None:
        def handler(_: dict[str, object]) -> None:
            time.sleep(0.05)

        executor = reliable_tools.ToolExecutor(
            {
                "slow_tool": reliable_tools.ToolSpec(
                    name="slow_tool",
                    description="一个故意执行很慢的工具",
                    parameters={"type": "object", "properties": {}},
                    handler=handler,
                    timeout_seconds=0.001,
                )
            }
        )
        result = executor.execute("slow_tool", {})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "timeout")
        self.assertEqual(result["attempts"], 1)

    def test_idempotency_key_prevents_duplicate_side_effect(self) -> None:
        calls = 0

        def handler(_: dict[str, object]) -> str:
            nonlocal calls
            calls += 1
            return f"record-{calls}"

        executor = reliable_tools.ToolExecutor(
            {
                "write_record": reliable_tools.ToolSpec(
                    name="write_record",
                    description="写入一条记录",
                    parameters={
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                        "additionalProperties": False,
                    },
                    handler=handler,
                )
            }
        )

        first = executor.execute(
            "write_record", {"value": "hello"}, idempotency_key="request-1"
        )
        second = executor.execute(
            "write_record", {"value": "hello"}, idempotency_key="request-1"
        )

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
