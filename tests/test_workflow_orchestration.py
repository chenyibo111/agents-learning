import importlib.util
import tempfile
import unittest
from pathlib import Path


SOURCE_FILE = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "20-workflow-orchestration"
    / "main.py"
)
SPEC = importlib.util.spec_from_file_location("workflow_orchestration", SOURCE_FILE)
assert SPEC and SPEC.loader
workflow_orchestration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow_orchestration)


class WorkflowOrchestrationTests(unittest.TestCase):
    def make_runner(self, directory: str):
        return workflow_orchestration.WorkflowRunner(
            state_file=Path(directory) / "workflow-state.json"
        )

    def test_low_risk_workflow_runs_parallel_branches_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self.make_runner(directory)
            state = workflow_orchestration.WorkflowState(
                task="整理低风险资料",
                data={"risk_level": "low"},
            )

            result = runner.run(state)

            self.assertEqual(result.status, "completed")
            self.assertEqual(result.current_node, "done")
            self.assertIn("local_notes", result.data)
            self.assertIn("catalog_items", result.data)
            self.assertEqual(
                [item["node"] for item in result.history],
                ["prepare", "collect_local", "collect_catalog", "merge", "publish"],
            )

    def test_high_risk_workflow_waits_for_approval_and_can_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self.make_runner(directory)
            state = workflow_orchestration.WorkflowState(
                task="整理高风险资料",
                data={"risk_level": "high"},
            )

            waiting = runner.run(state)
            self.assertEqual(waiting.status, "waiting_approval")
            self.assertEqual(waiting.current_node, "approval")
            self.assertNotIn("published", waiting.data)

            loaded = runner.load_state()
            completed = runner.run(loaded, decision="approve")
            self.assertEqual(completed.status, "completed")
            self.assertTrue(completed.data["published"])

    def test_high_risk_workflow_can_be_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self.make_runner(directory)
            state = workflow_orchestration.WorkflowState(
                task="拒绝高风险资料",
                data={"risk_level": "high"},
            )

            runner.run(state)
            rejected = runner.run(runner.load_state(), decision="reject")

            self.assertEqual(rejected.status, "rejected")
            self.assertFalse(rejected.data.get("published", False))
            self.assertEqual(rejected.history[-1]["node"], "approval_rejected")

    def test_state_can_be_loaded_after_workflow_pauses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runner = self.make_runner(directory)
            state = workflow_orchestration.WorkflowState(
                task="需要审批的任务",
                data={"risk_level": "high"},
            )

            runner.run(state)
            loaded = runner.load_state()

            self.assertEqual(loaded.task, "需要审批的任务")
            self.assertEqual(loaded.status, "waiting_approval")
            self.assertEqual(loaded.current_node, "approval")


if __name__ == "__main__":
    unittest.main()
