import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SOURCE_FILE = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "17-agent-state"
    / "main.py"
)
SPEC = importlib.util.spec_from_file_location("agent_state", SOURCE_FILE)
assert SPEC and SPEC.loader
agent_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(agent_state)


class StatusError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code


class RetryTests(unittest.TestCase):
    def test_retries_transient_error_with_exponential_backoff(self) -> None:
        attempts = 0
        delays: list[float] = []

        def operation() -> str:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise StatusError(503)
            return "success"

        with patch("time.sleep", side_effect=delays.append):
            result = agent_state.retry_with_backoff(
                operation,
                "测试操作",
                max_attempts=3,
                base_delay=1.0,
            )

        self.assertEqual(result, "success")
        self.assertEqual(attempts, 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_does_not_retry_authentication_error(self) -> None:
        attempts = 0
        delays: list[float] = []

        def operation() -> None:
            nonlocal attempts
            attempts += 1
            raise StatusError(401)

        with patch("time.sleep", side_effect=delays.append):
            with self.assertRaises(StatusError):
                agent_state.retry_with_backoff(operation, "认证操作")

        self.assertEqual(attempts, 1)
        self.assertEqual(delays, [])

    def test_raises_after_max_attempts(self) -> None:
        attempts = 0
        delays: list[float] = []

        def operation() -> None:
            nonlocal attempts
            attempts += 1
            raise StatusError(503)

        with patch("time.sleep", side_effect=delays.append):
            with self.assertRaises(StatusError):
                agent_state.retry_with_backoff(
                    operation,
                    "测试操作",
                    max_attempts=3,
                    base_delay=1.0,
                )

        self.assertEqual(attempts, 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_create_plan_retries_model_request(self) -> None:
        attempts = 0

        def create(**_: object) -> SimpleNamespace:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise StatusError(503)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='["完成一步"]')
                    )
                ]
            )

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch("time.sleep"):
            result = agent_state.create_plan(client, "test-model", "测试任务")

        self.assertEqual(result, ["完成一步"])
        self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
