import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "07-build-agent-framework"
MAIN = PROJECT / "main.py"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from mini_agent.contracts import (
    Action,
    AgentEvent,
    Message,
    ModelResponse,
    RunResult,
    ToolCall,
)
from mini_agent.errors import InvalidActionError
from mini_agent.tools import ToolRegistry, ToolSpec
from mini_agent.errors import (
    PermissionDeniedError,
    ToolNotFoundError,
    ToolValidationError,
)
from mini_agent.memory import Memory, SQLiteCheckpointStore
from mini_agent.model import RuleModel
from mini_agent.policy import Policy
from mini_agent.runner import Runner
from mini_agent.errors import RetryableToolError, ToolExecutionError

# Keep this test module's import path from shadowing other lesson ``main.py`` files.
if str(PROJECT) in sys.path:
    sys.path.remove(str(PROJECT))


class ContractTests(unittest.TestCase):
    def test_contracts_round_trip_as_json(self):
        message = Message(role="user", content="计算 4 + 5")
        response = ModelResponse(
            action=Action(
                kind="tool_call",
                tool_call=ToolCall(name="add", arguments={"a": 4, "b": 5}),
            ),
            usage_tokens=7,
        )
        result = RunResult(
            status="completed",
            answer="9",
            steps=2,
            messages=[message],
        )
        event = AgentEvent(
            run_id="run-1",
            step=1,
            phase="tool_completed",
            metadata={"tool": "add"},
        )

        payload = {
            "message": message.to_dict(),
            "response": response.to_dict(),
            "result": result.to_dict(),
            "event": event.to_dict(),
        }

        json.dumps(payload, ensure_ascii=False)
        self.assertEqual("tool_call", payload["response"]["action"]["kind"])
        self.assertEqual("completed", payload["result"]["status"])
        self.assertEqual("tool_completed", payload["event"]["phase"])

    def test_action_requires_exactly_one_result_shape(self):
        final = Action(kind="final", content="完成")
        tool_call = Action(
            kind="tool_call",
            tool_call=ToolCall(name="add", arguments={"a": 1, "b": 2}),
        )

        self.assertEqual("完成", final.content)
        self.assertEqual("add", tool_call.tool_call.name)
        with self.assertRaises(InvalidActionError):
            Action(kind="final")


class ToolRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        self.registry.register(
            ToolSpec(
                name="add",
                description="计算两个整数之和",
                input_schema={
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
                handler=lambda a, b: a + b,
                permission="calculator",
            )
        )

    def test_registry_validates_arguments_before_execution(self):
        self.assertEqual(9, self.registry.execute("add", {"a": 4, "b": 5}, {"calculator"}))

        with self.assertRaises(ToolValidationError):
            self.registry.execute("add", {"a": 4}, {"calculator"})
        with self.assertRaises(ToolValidationError):
            self.registry.execute("add", {"a": "4", "b": 5}, {"calculator"})

    def test_registry_rejects_unknown_and_unauthorized_tools(self):
        with self.assertRaises(ToolNotFoundError):
            self.registry.execute("missing", {}, {"calculator"})
        with self.assertRaises(PermissionDeniedError):
            self.registry.execute("add", {"a": 1, "b": 2}, set())


class MemoryTests(unittest.TestCase):
    def test_memory_records_messages_and_round_trips(self):
        memory = Memory(run_id="run-1", task="计算 4 + 5")
        memory.add_message(Message(role="user", content="计算 4 + 5"))
        memory.add_message(Message(role="tool", content="9", name="add"))
        memory.status = "completed"
        memory.step = 2

        restored = Memory.from_dict(memory.to_dict())

        self.assertEqual("completed", restored.status)
        self.assertEqual(2, restored.step)
        self.assertEqual(["user", "tool"], [m.role for m in restored.messages])
        self.assertEqual("9", restored.messages[1].content)

    def test_sqlite_checkpoint_persists_and_loads_memory(self):
        store = SQLiteCheckpointStore(":memory:")
        memory = Memory(run_id="run-2", task="测试 checkpoint")
        memory.add_message(Message(role="user", content="测试"))
        memory.status = "paused"
        store.save(memory)

        restored = store.load("run-2")

        self.assertEqual("run-2", restored.run_id)
        self.assertEqual("paused", restored.status)
        self.assertEqual("测试", restored.messages[0].content)


class ModelAndPolicyTests(unittest.TestCase):
    def test_rule_model_moves_from_tool_call_to_final_answer(self):
        model = RuleModel()
        tools = [{"name": "add", "input_schema": {}}]
        messages = [Message(role="user", content="计算 4 + 5")]

        first = model.generate(messages, tools)
        self.assertEqual("tool_call", first.action.kind)
        self.assertEqual({"a": 4, "b": 5}, first.action.tool_call.arguments)

        messages.append(Message(role="tool", name="add", content="9"))
        second = model.generate(messages, tools)
        self.assertEqual("final", second.action.kind)
        self.assertIn("9", second.action.content)

    def test_policy_parses_json_and_rejects_invalid_model_output(self):
        policy = Policy()
        action = policy.parse(
            '{"type":"tool_call","tool":"add","arguments":{"a":1,"b":2}}'
        )
        self.assertEqual("add", action.tool_call.name)

        final = policy.parse('{"type":"final","content":"完成"}')
        self.assertEqual("完成", final.content)

        with self.assertRaises(InvalidActionError):
            policy.parse("不是 JSON")
        with self.assertRaises(InvalidActionError):
            policy.parse('{"type":"unknown"}')


def build_add_registry(handler=None, *, retryable=False):
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="add",
            description="计算两个整数之和",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
            },
            handler=handler or (lambda a, b: a + b),
            permission="calculator",
            retryable=retryable,
        )
    )
    return registry


class SequenceModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate(self, messages, tools):
        self.calls += 1
        return self.responses.pop(0)


class RunnerTests(unittest.TestCase):
    def test_runner_puts_user_task_into_memory_before_model_call(self):
        runner = Runner(
            model=RuleModel(),
            tools=build_add_registry(),
            permissions={"calculator"},
        )

        result = runner.run("计算 4 + 5")

        self.assertEqual("completed", result.status)
        self.assertIn("9", result.answer)
        self.assertEqual(2, result.steps)

    def test_runner_executes_tool_then_returns_final_answer(self):
        model = SequenceModel(
            [
                ModelResponse(
                    action=Action(
                        kind="tool_call",
                        tool_call=ToolCall(name="add", arguments={"a": 4, "b": 5}),
                    ),
                    usage_tokens=3,
                ),
                ModelResponse(
                    action=Action(kind="final", content="最终结果是 9"),
                    usage_tokens=2,
                ),
            ]
        )
        runner = Runner(model=model, tools=build_add_registry(), permissions={"calculator"})

        result = runner.run("计算 4 + 5")

        self.assertEqual("completed", result.status)
        self.assertEqual("最终结果是 9", result.answer)
        self.assertEqual(2, result.steps)
        self.assertEqual(5, result.total_usage_tokens)
        self.assertEqual(
            ["run_started", "tool_completed", "run_completed"],
            [event.phase for event in result.events if event.phase in {
                "run_started", "tool_completed", "run_completed"
            }],
        )

    def test_runner_stops_at_max_steps_with_diagnostic_status(self):
        tool_call = ModelResponse(
            action=Action(
                kind="tool_call",
                tool_call=ToolCall(name="add", arguments={"a": 1, "b": 2}),
            )
        )
        runner = Runner(
            model=SequenceModel([tool_call, tool_call, tool_call]),
            tools=build_add_registry(),
            permissions={"calculator"},
            max_steps=2,
        )

        result = runner.run("持续计算")

        self.assertEqual("max_steps", result.status)
        self.assertEqual(2, result.steps)
        self.assertIn("最大步数", result.error)

    def test_runner_retries_only_retryable_tool_errors(self):
        attempts = []

        def flaky_add(a, b):
            attempts.append(1)
            if len(attempts) == 1:
                raise RetryableToolError("临时失败")
            return a + b

        tool_call = ModelResponse(
            action=Action(
                kind="tool_call",
                tool_call=ToolCall(name="add", arguments={"a": 1, "b": 2}),
            )
        )
        model = SequenceModel([
            tool_call,
            ModelResponse(action=Action(kind="final", content="3")),
        ])
        runner = Runner(
            model=model,
            tools=build_add_registry(flaky_add, retryable=True),
            permissions={"calculator"},
            tool_max_attempts=2,
        )

        result = runner.run("计算")

        self.assertEqual("completed", result.status)
        self.assertEqual(2, len(attempts))
        self.assertTrue(any(event.phase == "retry_scheduled" for event in result.events))

    def test_non_retryable_tool_does_not_retry_even_for_transient_error(self):
        attempts = []

        def side_effect_tool(a, b):
            attempts.append(1)
            raise RetryableToolError("临时失败但工具有副作用")

        model = SequenceModel([
            ModelResponse(
                action=Action(
                    kind="tool_call",
                    tool_call=ToolCall(name="add", arguments={"a": 1, "b": 2}),
                )
            )
        ])
        runner = Runner(
            model=model,
            tools=build_add_registry(side_effect_tool),
            permissions={"calculator"},
            tool_max_attempts=3,
        )

        result = runner.run("执行副作用工具")

        self.assertEqual("failed", result.status)
        self.assertEqual(1, len(attempts))

    def test_runner_marks_unclassified_tool_error_as_tool_execution_failure(self):
        def broken_add(a, b):
            raise RuntimeError("下游服务不可用")

        model = SequenceModel([
            ModelResponse(
                action=Action(
                    kind="tool_call",
                    tool_call=ToolCall(name="add", arguments={"a": 1, "b": 2}),
                )
            )
        ])
        runner = Runner(
            model=model,
            tools=build_add_registry(broken_add),
            permissions={"calculator"},
        )

        result = runner.run("计算")

        self.assertEqual("failed", result.status)
        self.assertIn("工具 add 执行失败", result.error)

    def test_runner_resumes_checkpoint_without_repeating_completed_tool(self):
        store = SQLiteCheckpointStore(":memory:")
        memory = Memory(run_id="resume-1", task="继续任务", status="paused", step=1)
        memory.add_message(Message(role="user", content="继续任务"))
        memory.add_message(Message(role="tool", name="add", content="3"))
        store.save(memory)
        model = SequenceModel([
            ModelResponse(action=Action(kind="final", content="恢复完成")),
        ])
        runner = Runner(
            model=model,
            tools=build_add_registry(),
            permissions={"calculator"},
            checkpoint_store=store,
        )

        result = runner.resume("resume-1")

        self.assertEqual("completed", result.status)
        self.assertEqual("恢复完成", result.answer)
        self.assertEqual(1, model.calls)

    def test_runner_can_pause_after_a_checkpoint_and_resume(self):
        tool_call = ModelResponse(
            action=Action(
                kind="tool_call",
                tool_call=ToolCall(name="add", arguments={"a": 1, "b": 2}),
            )
        )
        model = SequenceModel([
            tool_call,
            ModelResponse(action=Action(kind="final", content="恢复后的答案")),
        ])
        runner = Runner(
            model=model,
            tools=build_add_registry(),
            permissions={"calculator"},
            pause_after_step=1,
        )

        paused = runner.run("暂停任务")
        resumed = runner.resume(paused.run_id)

        self.assertEqual("paused", paused.status)
        self.assertEqual("completed", resumed.status)
        self.assertEqual("恢复后的答案", resumed.answer)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(MAIN), *args],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_legacy_demo_still_runs(self):
        completed = self.run_cli("--demo")

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("MiniFramework", completed.stdout)

    def test_framework_demo_runs_offline_and_returns_structured_result(self):
        completed = self.run_cli(
            "--framework-demo",
            "--query",
            "计算 4 + 5",
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual("completed", payload["status"])
        self.assertIn("9", payload["answer"])
        self.assertTrue(payload["events"])

    def test_framework_demo_can_pause_and_resume_from_sqlite_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = str(Path(directory) / "lesson07.sqlite3")
            paused = self.run_cli(
                "--framework-demo",
                "--pause-after-step",
                "1",
                "--checkpoint",
                checkpoint,
            )
            self.assertEqual(0, paused.returncode, paused.stderr)
            paused_payload = json.loads(paused.stdout)
            self.assertEqual("paused", paused_payload["status"])

            resumed = self.run_cli(
                "--framework-demo",
                "--resume",
                "--run-id",
                paused_payload["run_id"],
                "--checkpoint",
                checkpoint,
            )
            self.assertEqual(0, resumed.returncode, resumed.stderr)
            self.assertEqual("completed", json.loads(resumed.stdout)["status"])

    def test_llm_agent_can_use_injected_text_model_without_network(self):
        from mini_agent.model import OpenAITextModel

        model = OpenAITextModel(
            ask=lambda prompt, system: '{"type":"final","content":"离线回答"}'
        )
        response = model.generate([], [])

        self.assertIn("离线回答", response)


if __name__ == "__main__":
    unittest.main()
