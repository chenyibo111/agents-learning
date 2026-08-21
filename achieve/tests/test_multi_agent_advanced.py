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
    module_name = "lesson26_advanced_workflow"
    source_file = PROJECT_DIR / "advanced_workflow.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


workflow = load_project_module()


class AdvancedMultiAgentTests(unittest.TestCase):
    def test_role_selection_adds_fact_checker_for_risky_tasks(self) -> None:
        result = workflow.choose_roles(
            {"task": "评估生产上线风险", "events": []}
        )

        self.assertEqual(
            result["requested_roles"],
            ["researcher", "critic", "fact_checker"],
        )

    def test_generic_task_uses_two_roles(self) -> None:
        result = workflow.choose_roles(
            {"task": "总结 Agent 基础", "events": []}
        )

        self.assertEqual(
            result["requested_roles"],
            ["researcher", "critic"],
        )

    def test_failed_worker_is_returned_as_warning(self) -> None:
        result = workflow.specialist_worker(
            {
                "task": "生产风险",
                "role": "fact_checker",
                "simulate_failure": True,
            }
        )

        self.assertEqual(result["failures"][0]["role"], "fact_checker")
        self.assertIn("超时", result["failures"][0]["error"])

    def test_dynamic_graph_aggregates_roles(self) -> None:
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        graph = workflow.build_advanced_graph(workflow.InMemorySaver())
        result = graph.invoke(
            {
                "task": "评估生产上线风险",
                "events": [],
                "worker_results": [],
                "failures": [],
            },
            {"configurable": {"thread_id": "test-thread-26-advanced"}},
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(result["worker_results"]), 3)

    def test_dynamic_graph_can_complete_with_warning(self) -> None:
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        graph = workflow.build_advanced_graph(workflow.InMemorySaver())
        result = graph.invoke(
            {
                "task": "普通任务",
                "simulate_failure": True,
                "events": [],
                "worker_results": [],
                "failures": [],
            },
            {"configurable": {"thread_id": "test-thread-26-failure"}},
        )

        self.assertEqual(result["status"], "completed_with_warnings")
        self.assertTrue(result["failures"])


if __name__ == "__main__":
    unittest.main()

