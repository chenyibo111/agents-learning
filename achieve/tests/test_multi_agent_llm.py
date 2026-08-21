import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "26-multi-agent-collaboration"
)


def load_project_module():
    module_name = "lesson26_llm_workflow"
    source_file = PROJECT_DIR / "llm_workflow.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


workflow = load_project_module()


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, *, model, messages, temperature):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
        )
        system = messages[0]["content"]
        if "协调者" in system:
            content = '["researcher", "critic", "fact_checker"]'
        elif "研究员" in system:
            content = "研究员发现：这是研究结果。"
        elif "审查员" in system:
            content = "审查员发现：这是风险提醒。"
        elif "事实核验员" in system:
            content = "事实核验员发现：需要额外来源。"
        else:
            content = "汇总 Agent：综合了专家结果。"
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=content)
                )
            ]
        )


class FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


class RealLLMMultiAgentTests(unittest.TestCase):
    def test_parse_roles_whitelists_and_deduplicates(self) -> None:
        self.assertEqual(
            workflow.parse_roles(
                '```json\n["critic", "unknown", "critic"]\n```'
            ),
            ["critic"],
        )

    def test_real_llm_roles_are_called_and_aggregated(self) -> None:
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        client = FakeClient()
        runtime = workflow.LLMCollaborationRuntime(client, "test-model")
        graph = runtime.build_graph(workflow.InMemorySaver())
        result = graph.invoke(
            {
                "task": "测试真实多 Agent",
                "events": [],
                "worker_results": [],
                "failures": [],
            },
            {"configurable": {"thread_id": "test-thread-26-llm"}},
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["worker_results"]), 3)
        self.assertIn("综合了专家结果", result["final_answer"])
        self.assertEqual(len(client.chat.completions.calls), 5)

    def test_worker_api_failure_is_isolated(self) -> None:
        class FailingRuntime(workflow.LLMCollaborationRuntime):
            def call_model(self, system, user):
                if "事实核验员" in system:
                    raise TimeoutError("模拟 API 超时")
                return super().call_model(system, user)

        client = FakeClient()
        runtime = FailingRuntime(client, "test-model")
        result = runtime.specialist_worker(
            {
                "task": "测试",
                "role": "fact_checker",
            }
        )

        self.assertEqual(result["failures"][0]["role"], "fact_checker")
        self.assertIn("模拟 API 超时", result["failures"][0]["error"])


if __name__ == "__main__":
    unittest.main()
