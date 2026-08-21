import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "31-task-history-approval"
)
def load_project_module(module_name, filename):
    spec = importlib.util.spec_from_file_location(
        module_name,
        PROJECT_DIR / filename,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Earlier lesson tests also load a top-level module named ``workflow``.
# Load lesson 31 under unique names so its TypedDict and LangGraph schema
# stay resolvable without polluting the other lessons' imports.
store_module = load_project_module("lesson31_store", "store.py")
sys.modules["store"] = store_module
workflow_module = load_project_module("lesson31_workflow", "workflow.py")
sys.modules.pop("store", None)

from langgraph.types import Command  # noqa: E402

TaskStore = store_module.TaskStore
InMemorySaver = workflow_module.InMemorySaver
build_graph = workflow_module.build_graph


class TaskStoreTests(unittest.TestCase):
    def test_task_and_approval_history_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "tasks.sqlite3"
            store = TaskStore(database)
            store.create_task("task-1", "测试任务")
            store.update_task("task-1", status="awaiting_approval", report="# 草稿")
            store.record_approval("task-1", "approved", "检查通过")

            record = store.get_task("task-1")

            self.assertEqual(record["status"], "awaiting_approval")
            self.assertEqual(record["report"], "# 草稿")
            self.assertEqual(record["approvals"][0]["decision"], "approved")
            self.assertEqual(record["approvals"][0]["comment"], "检查通过")
            store.close()


class ApprovalWorkflowTests(unittest.TestCase):
    def _run_until_pause(self, decision):
        database = Path(tempfile.mkdtemp()) / "tasks.sqlite3"
        store = TaskStore(database)
        task_id = f"task-{decision}"
        store.create_task(task_id, "测试审批流程")
        graph = build_graph(store, InMemorySaver())
        config = {"configurable": {"thread_id": task_id}}

        paused = graph.invoke(
            {"task_id": task_id, "query": "测试审批流程", "events": []},
            config,
        )
        return store, graph, config, task_id, paused

    def test_workflow_pauses_before_publish_and_approved_resume_publishes(self):
        store, graph, config, task_id, paused = self._run_until_pause("approved")

        self.assertIn("__interrupt__", paused)
        self.assertEqual(store.get_task(task_id)["status"], "awaiting_approval")

        finished = graph.invoke(
            Command(resume={"decision": "approved", "comment": "同意"}),
            config,
        )

        self.assertEqual(finished["status"], "published")
        self.assertEqual(store.get_task(task_id)["status"], "published")
        store.close()

    def test_rejected_resume_does_not_publish(self):
        store, graph, config, task_id, paused = self._run_until_pause("rejected")

        self.assertIn("__interrupt__", paused)
        finished = graph.invoke(
            Command(resume={"decision": "rejected", "comment": "需要修改"}),
            config,
        )

        self.assertEqual(finished["status"], "rejected")
        self.assertEqual(store.get_task(task_id)["status"], "rejected")
        self.assertNotEqual(store.get_task(task_id)["status"], "published")
        store.close()


if __name__ == "__main__":
    unittest.main()
