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
        self.assertEqual({"add_numbers", "multiply_numbers", "divide_numbers"}, names)
        for item in self.agent.TOOLS:
            function = item["function"]
            self.assertTrue(function["description"])
            self.assertEqual(["a", "b"], function["parameters"]["required"])

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
