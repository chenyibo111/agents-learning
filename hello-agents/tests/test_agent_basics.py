import importlib.util
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "01-agent-basics"


def load_module():
    spec = importlib.util.spec_from_file_location("hello_agents_agent_basics", PROJECT / "agent.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgentBasicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = load_module()

    def test_number_tools_have_descriptions_and_required_arguments(self):
        names = {item["function"]["name"] for item in self.agent.TOOLS}
        self.assertEqual({"add_numbers", "subtract_numbers", "multiply_numbers", "divide_numbers"}, names)
        for item in self.agent.TOOLS:
            function = item["function"]
            self.assertTrue(function["description"])
            self.assertEqual(["a", "b"], function["parameters"]["required"])

    def test_subtract_tool_and_offline_parser(self):
        self.assertEqual("5.0", self.agent.call_tool("subtract_numbers", {"a": 8, "b": 3}))
        result = self.agent.run_offline("8 减 3")
        self.assertEqual("5.0", result.answer)
        self.assertEqual(["subtract_numbers"], result.tool_names)

    def test_offline_result_contains_safe_structured_events(self):
        result = self.agent.run_offline("先计算 8 加 4，再把结果乘以 3")
        self.assertEqual(2, len(result.events))

        first_event = result.events[0]
        self.assertEqual(
            {"step", "tool", "arguments", "observation", "duration_ms"},
            set(first_event),
        )
        self.assertEqual(1, first_event["step"])
        self.assertEqual("add_numbers", first_event["tool"])
        self.assertEqual("12.0", first_event["observation"])
        self.assertGreaterEqual(first_event["duration_ms"], 0)
        self.assertNotIn("api_key", str(result.events).lower())
        self.assertNotIn("authorization", str(result.events).lower())

        error_result = self.agent.run_offline("10 除以 0")
        self.assertEqual(1, len(error_result.events))
        self.assertIn("除数不能为 0", error_result.events[0]["observation"])

    def test_call_tool_validates_known_tools(self):
        self.assertEqual("5.0", self.agent.call_tool("add_numbers", {"a": 2, "b": 3}))
        with self.assertRaises(self.agent.UnknownToolError):
            self.agent.call_tool("delete_files", {"path": "/tmp"})

    def test_tool_errors_are_returned_as_observations(self):
        observation = self.agent.execute_tool_safely("divide_numbers", {"a": 10, "b": 0})
        self.assertTrue(observation.startswith("工具执行失败："))
        self.assertIn("除数不能为 0", observation)

    def test_offline_agent_completes_a_two_step_task(self):
        result = self.agent.run_offline("先计算 8 加 4，再把结果乘以 3")
        self.assertEqual("36.0", result.answer)
        self.assertEqual(["add_numbers", "multiply_numbers"], result.tool_names)
        self.assertLessEqual(result.steps, 5)

    def test_runner_stops_at_max_steps(self):
        with self.assertRaises(self.agent.MaxStepsExceeded):
            self.agent.run_actions([("add_numbers", {"a": 1, "b": 1})] * 3, max_steps=2)


if __name__ == "__main__":
    unittest.main()
