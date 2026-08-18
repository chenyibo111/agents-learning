import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1] / "projects" / "23-agent-protocol"


def load_project_module(module_name: str):
    source_file = PROJECT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


protocol = load_project_module("protocol")
registry = load_project_module("registry")
business = load_project_module("business")
server = load_project_module("server")
agent = load_project_module("agent")
main = load_project_module("main")


class LocalRuleAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = agent.LocalRuleAgent(
            server.ProtocolServer(business.build_registry())
        )

    def test_calculation_input_routes_to_add_numbers(self) -> None:
        answer = self.agent.run("计算 12 加 30")

        self.assertIn("42", answer)

    def test_multiplication_input_routes_to_registered_tool(self) -> None:
        answer = self.agent.run("计算 6 乘 7")

        self.assertIn("42", answer)

    def test_search_input_routes_to_search_tool(self) -> None:
        answer = self.agent.run("搜索 工具 协议")

        self.assertIn("协议边界", answer)

    def test_resource_input_routes_to_registered_uri(self) -> None:
        answer = self.agent.run("读取 Agent 基础")

        self.assertIn("Agent 通常通过模型", answer)

    def test_unsupported_input_returns_capability_hint(self) -> None:
        action = self.agent.plan("给我播放一首歌")
        answer = self.agent.run("给我播放一首歌")

        self.assertEqual(action["type"], "answer")
        self.assertIn("支持", answer)

    def test_interactive_local_mode_reads_until_exit(self) -> None:
        inputs = iter(["计算 1 加 2", "退出"])
        outputs = []

        main.run_interactive(
            agent_name="local",
            server=self.agent.server,
            input_fn=lambda _: next(inputs),
            output_fn=outputs.append,
        )

        self.assertTrue(any("3" in output for output in outputs))


if __name__ == "__main__":
    unittest.main()
