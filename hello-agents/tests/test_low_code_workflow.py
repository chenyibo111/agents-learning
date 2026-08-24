import tempfile
from pathlib import Path
import sys
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "05-low-code-platforms"


def load_module():
    import importlib.util
    import sys

    sys.path.insert(0, str(PROJECT))
    spec = importlib.util.spec_from_file_location("low_code_workflow", PROJECT / "workflow.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LowCodeWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = load_module()

    def test_low_risk_workflow_flows_through_nodes(self):
        runner = self.workflow.build_workflow()
        state = runner.run("如何配置 Agent？")

        self.assertEqual("completed", state.status)
        self.assertEqual(["normalize", "route", "answer"], [event["node"] for event in state.events])
        self.assertIn("如何配置 Agent？", state.answer)

    def test_high_risk_workflow_pauses_for_approval_and_persists(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = self.workflow.SQLiteStateStore(path)
            runner = self.workflow.build_workflow(store=store)
            paused = runner.run("请发送邮件给客户")

            self.assertEqual("waiting_approval", paused.status)
            self.assertIsNotNone(paused.approval_id)
            self.assertEqual(paused.workflow_id, store.load(workflow_id=paused.workflow_id).workflow_id)

    def test_approval_resume_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.workflow.SQLiteStateStore(Path(directory) / "state.sqlite3")
            runner = self.workflow.build_workflow(store=store)
            paused = runner.run("请发送邮件给客户")
            completed = runner.resume(paused.approval_id, approved=True)
            repeated = runner.resume(paused.approval_id, approved=True)

            self.assertEqual("completed", completed.status)
            self.assertEqual(completed.answer, repeated.answer)
            answer_events = [event for event in repeated.events if event["node"] == "answer"]
            self.assertEqual(1, len(answer_events))

    def test_persisted_approval_can_resume_with_a_new_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.workflow.SQLiteStateStore(Path(directory) / "state.sqlite3")
            paused = self.workflow.build_workflow(store=store).run("请发送邮件给客户")
            resumed = self.workflow.build_workflow(store=store).resume(paused.approval_id, approved=True)

            self.assertEqual("completed", resumed.status)
            self.assertEqual("completed", store.load(workflow_id=paused.workflow_id).status)

    def test_rejected_approval_does_not_execute_action(self):
        runner = self.workflow.build_workflow()
        paused = runner.run("请发送邮件给客户")
        rejected = runner.resume(paused.approval_id, approved=False)

        self.assertEqual("rejected", rejected.status)
        self.assertIn("拒绝", rejected.answer)
        self.assertFalse(any(event["node"] == "answer" for event in rejected.events))

    def test_node_input_schema_rejects_missing_state(self):
        runner = self.workflow.build_workflow()
        failed = runner.run_state(self.workflow.WorkflowState(question=""), start="route")

        self.assertEqual("failed", failed.status)
        self.assertIn("缺少输入", failed.failure)

    def test_chat_route_completes_without_knowledge_lookup(self):
        state = self.workflow.build_workflow().run("你好，介绍一下你自己")

        self.assertEqual("chat", state.route)
        self.assertEqual("completed", state.status)
        self.assertIn("你好", state.answer)

    def test_node_events_include_execution_duration(self):
        state = self.workflow.build_workflow().run("如何配置 Agent？")

        self.assertTrue(all("duration_ms" in event for event in state.events))
        self.assertTrue(all(event["duration_ms"] >= 0 for event in state.events))

    def test_approval_timeout_marks_workflow_failed(self):
        now = [100.0]
        runner = self.workflow.build_workflow(approval_timeout_seconds=5, clock=lambda: now[0])
        paused = runner.run("请发送邮件给客户")
        now[0] = 106.0

        failed = runner.resume(paused.approval_id, approved=True)

        self.assertEqual("failed", failed.status)
        self.assertIn("审批已超时", failed.failure)

    def test_approved_tool_writes_one_idempotent_outbox_record(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.workflow.SQLiteStateStore(Path(directory) / "state.sqlite3")
            runner = self.workflow.build_workflow(store=store)
            paused = runner.run("请发送邮件给客户")
            completed = runner.resume(paused.approval_id, approved=True)
            repeated = runner.resume(paused.approval_id, approved=True)

            self.assertEqual("completed", completed.status)
            self.assertIn("outbox", completed.tool_result)
            self.assertEqual(1, store.count_outbox())
            self.assertEqual(completed.answer, repeated.answer)

    def test_tool_node_requires_permission(self):
        runner = self.workflow.build_workflow()
        state = self.workflow.WorkflowState(
            question="请发送邮件给客户",
            normalized="请发送邮件给客户",
            route="approval",
        )

        failed = runner.run_state(state, start="tool")

        self.assertEqual("failed", failed.status)
        self.assertIn("权限", failed.failure)


if __name__ == "__main__":
    unittest.main()
