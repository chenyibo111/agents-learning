import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = (
    Path(__file__).resolve().parents[1] / "projects" / "27-research-assistant"
)
sys.path.insert(0, str(PROJECT_DIR))

# Earlier lessons also expose a top-level ``workflow`` module. Remove those
# cached names so this test imports the lesson 27 modules it intends to test.
for module_name in ("runtime", "state", "workflow"):
    sys.modules.pop(module_name, None)

from runtime import DemoRuntime, LLMRuntime, validate_llm_config  # noqa: E402
from state import ResearchState  # noqa: E402
import workflow  # noqa: E402


class FakeCompletions:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = next(self.responses)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class RuntimeContractTests(unittest.TestCase):
    def test_demo_runtime_returns_research_records(self):
        runtime = DemoRuntime()

        plan = runtime.plan("多 Agent 生产应用")
        sources = runtime.collect_sources("多 Agent 生产应用", plan)
        evidence = runtime.extract_evidence("多 Agent 生产应用", sources)
        verified = runtime.verify_evidence("多 Agent 生产应用", evidence)
        report = runtime.write_report("多 Agent 生产应用", verified)

        self.assertTrue(plan)
        self.assertTrue(sources)
        self.assertTrue(all(item["verified"] for item in verified))
        self.assertIn("[1]", report)

    def test_llm_runtime_uses_same_contract_without_network(self):
        client = FakeClient(
            [
                '["定义研究问题", "比较方案", "列出风险"]',
                '[{"title":"测试资料","url":"https://example.com/source","summary":"候选资料"}]',
                '[{"claim":"候选资料支持研究方向","source_url":"https://example.com/source"}]',
                '[{"claim":"候选资料支持研究方向","source_url":"https://example.com/source","verified":true,"note":"待人工复核"}]',
                "# 研究报告\n\n结论。[1]",
            ]
        )
        runtime = LLMRuntime(client=client, model_id="test-model")

        plan = runtime.plan("测试主题")
        sources = runtime.collect_sources("测试主题", plan)
        evidence = runtime.extract_evidence("测试主题", sources)
        verified = runtime.verify_evidence("测试主题", evidence)
        report = runtime.write_report("测试主题", verified)

        self.assertEqual(plan, ["定义研究问题", "比较方案", "列出风险"])
        self.assertEqual(sources[0]["url"], "https://example.com/source")
        self.assertTrue(verified[0]["verified"])
        self.assertIn("[1]", report)
        self.assertEqual(len(client.chat.completions.calls), 5)

    def test_placeholder_llm_credentials_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_llm_config(
                api_key="你的 API Key",
                model_id="test-model",
                base_url="https://example.com/v1",
            )


class WorkflowContractTests(unittest.TestCase):
    def test_nodes_share_state_and_finish_with_report(self):
        runtime = DemoRuntime()
        state: ResearchState = {"topic": "研究助手", "events": []}

        for node in (
            workflow.plan_node,
            workflow.collect_sources_node,
            workflow.extract_evidence_node,
            workflow.verify_evidence_node,
            workflow.write_report_node,
        ):
            state = {**state, **node(state, runtime)}

        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["report"])
        self.assertEqual(
            state["events"],
            [
                "plan 完成",
                "collect_sources 完成",
                "extract_evidence 完成",
                "verify_evidence 完成",
                "write_report 完成",
            ],
        )

    def test_graph_runs_with_demo_runtime_when_langgraph_is_available(self):
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        graph = workflow.build_graph(DemoRuntime())
        result = graph.invoke(
            {"topic": "图工作流", "events": []},
            {"configurable": {"thread_id": "lesson-27-test"}},
        )

        self.assertEqual(result["status"], "completed")
        self.assertIn("write_report 完成", result["events"])


if __name__ == "__main__":
    unittest.main()
