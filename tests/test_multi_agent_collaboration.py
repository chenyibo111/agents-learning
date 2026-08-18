import importlib.util
import sys
import unittest
from pathlib import Path


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "26-multi-agent-collaboration"
)
def load_project_module():
    module_name = "lesson26_workflow"
    source_file = PROJECT_DIR / "workflow.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


workflow = load_project_module()


class MultiAgentNodeTests(unittest.TestCase):
    def test_coordinator_assigns_complementary_roles(self) -> None:
        result = workflow.coordinator({"task": "测试", "events": []})

        self.assertEqual(
            result["assignments"],
            ["researcher", "critic"],
        )
        self.assertEqual(result["status"], "delegated")

    def test_synthesizer_combines_specialist_outputs(self) -> None:
        result = workflow.synthesizer(
            {
                "task": "测试",
                "research": ["研究结论"],
                "critiques": ["审查意见"],
                "events": [],
            }
        )

        self.assertIn("研究结论", result["final_answer"])
        self.assertIn("审查意见", result["final_answer"])
        self.assertEqual(result["status"], "completed")

    def test_parallel_graph_fans_out_and_fans_in(self) -> None:
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        graph = workflow.build_graph(workflow.InMemorySaver())
        result = graph.invoke(
            {"task": "测试多 Agent", "events": []},
            {"configurable": {"thread_id": "test-thread-26"}},
        )

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["research"])
        self.assertTrue(result["critiques"])
        self.assertIn("synthesizer 完成结果汇总", result["events"])


if __name__ == "__main__":
    unittest.main()
