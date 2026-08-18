import sys
import unittest
from pathlib import Path


PROJECT_DIR = (
    Path(__file__).resolve().parents[1] / "projects" / "25-langgraph-state"
)
sys.path.insert(0, str(PROJECT_DIR))

import workflow  # noqa: E402


class LangGraphNodeTests(unittest.TestCase):
    def test_collect_and_draft_nodes_update_state(self) -> None:
        state = {"topic": "状态管理", "events": []}
        collected = workflow.collect_notes(state)
        drafted = workflow.draft_summary({**state, **collected})

        self.assertEqual(collected["status"], "collected")
        self.assertIn("状态管理", drafted["draft"])
        self.assertEqual(drafted["status"], "drafted")

    def test_review_router(self) -> None:
        self.assertEqual(
            workflow.route_after_review({"approved": True}),
            "publish",
        )
        self.assertEqual(
            workflow.route_after_review({"approved": False}),
            "revise",
        )

    def test_graph_pauses_and_resumes_same_thread(self) -> None:
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        graph = workflow.build_graph(workflow.InMemorySaver())
        config = {"configurable": {"thread_id": "test-thread"}}
        paused = graph.invoke(
            {"topic": "测试主题", "events": []},
            config,
        )
        self.assertTrue(paused.get("__interrupt__"))

        completed = graph.invoke(
            workflow.Command(resume={"approved": True}),
            config,
        )
        self.assertEqual(completed["status"], "completed")
        self.assertIn("publish 完成", completed["events"])


if __name__ == "__main__":
    unittest.main()

