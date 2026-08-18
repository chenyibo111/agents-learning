import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = (
    Path(__file__).resolve().parents[1] / "projects" / "24-smolagents-agent"
)


def load_project_module(module_name: str):
    source_file = PROJECT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


tools = load_project_module("tools")
runner = load_project_module("agent_runner")
main = load_project_module("main")


class SmolagentsToolsTests(unittest.TestCase):
    def test_tools_expose_framework_metadata_when_available(self) -> None:
        if not tools.SMOLAGENTS_AVAILABLE:
            self.skipTest("smolagents 未安装，本测试只验证框架工具元数据")

        tool_names = [item.name for item in tools.all_tools()]

        self.assertEqual(
            tool_names,
            ["add_numbers", "mul_numbers", "search_notes", "read_resource"],
        )

    def test_add_numbers_returns_sum(self) -> None:
        self.assertEqual(tools.add_numbers(2, 3), 5)

    def test_mul_numbers_returns_product(self) -> None:
        self.assertEqual(tools.mul_numbers(6, 7), 42)

    def test_search_notes_returns_matching_notes(self) -> None:
        results = tools.search_notes("工具 协议")

        self.assertTrue(any(item["name"] == "协议边界" for item in results))

    def test_read_resource_allows_registered_uri_only(self) -> None:
        content = tools.read_resource("note://agent-basics")

        self.assertIn("Agent 通常通过模型", content)
        with self.assertRaises(ValueError):
            tools.read_resource("file:///etc/passwd")


class SmolagentsAdapterTests(unittest.TestCase):
    def test_model_uses_auto_tool_choice_for_compatibility(self) -> None:
        if not runner.smolagents_available():
            self.skipTest("smolagents 未安装，本测试只验证模型参数")

        with patch("smolagents.OpenAIServerModel") as model_class:
            runner.build_model(
                api_key="real-looking-test-key",
                model_id="test-model",
                api_base="https://example.com/v1",
            )

        self.assertEqual(model_class.call_args.kwargs["tool_choice"], "auto")

    def test_missing_dependency_message_is_actionable(self) -> None:
        if runner.smolagents_available():
            self.skipTest("smolagents 已安装，本测试只验证缺失依赖分支")

        with self.assertRaises(RuntimeError) as context:
            runner.require_smolagents()

        self.assertIn("pip install -r", str(context.exception))

    def test_model_configuration_rejects_placeholder_key(self) -> None:
        with self.assertRaises(ValueError):
            runner.validate_model_config(
                api_key="replace-with-a-key",
                model_id="test-model",
                api_base="https://example.com/v1",
            )


class SmolagentsDemoTests(unittest.TestCase):
    def test_offline_demo_executes_tools_without_framework_runtime(self) -> None:
        outputs = []

        main.run_demo(output_fn=outputs.append)

        self.assertTrue(any("add_numbers" in output for output in outputs))
        self.assertTrue(any("42" in output for output in outputs))




if __name__ == "__main__":
    unittest.main()
