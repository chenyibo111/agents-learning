import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "06-agent-frameworks"


def load_module():
    sys.path.insert(0, str(PROJECT))
    spec = importlib.util.spec_from_file_location("agent_frameworks", PROJECT / "frameworks.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgentFrameworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frameworks = load_module()

    def test_adapters_share_a_structured_message_contract(self):
        for adapter in self.frameworks.build_adapters():
            message = adapter.respond("research", "总结 Agent")
            self.assertEqual("assistant", message.role)
            self.assertTrue(message.content)
            self.assertGreater(message.usage_tokens, 0)

    def test_serial_workflow_routes_research_to_writing(self):
        result = self.frameworks.AgentRuntime(self.frameworks.build_adapters()[0]).run_serial("总结 Agent")

        self.assertEqual("completed", result.status)
        self.assertEqual(["research", "writing"], result.completed_nodes)
        self.assertIn("draft", result.results)

    def test_parallel_fan_out_and_fan_in(self):
        runtime = self.frameworks.AgentRuntime(self.frameworks.build_adapters()[0])
        result = runtime.run_parallel("总结 Agent")

        self.assertEqual("completed", result.status)
        self.assertTrue({"research", "critic", "draft"}.issubset(result.results))
        self.assertIn("writing", result.completed_nodes)
        self.assertGreaterEqual(len(result.events), 2)

    def test_failure_is_saved_as_a_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.frameworks.SQLiteCheckpointStore(Path(directory) / "checkpoints.sqlite3")
            runtime = self.frameworks.AgentRuntime(
                self.frameworks.ScriptedAdapter(fail_on="research"),
                checkpoint_store=store,
            )
            failed = runtime.run_serial("总结 Agent")
            restored = store.load(failed.run_id)

            self.assertEqual("failed", failed.status)
            self.assertIn("research", failed.error)
            self.assertEqual("failed", restored.status)

    def test_resume_uses_checkpoint_without_repeating_completed_node(self):
        with tempfile.TemporaryDirectory() as directory:
            store = self.frameworks.SQLiteCheckpointStore(Path(directory) / "checkpoints.sqlite3")
            runtime = self.frameworks.AgentRuntime(
                self.frameworks.ScriptedAdapter(),
                checkpoint_store=store,
            )
            first = runtime.run_serial("总结 Agent", stop_after="research")
            resumed = runtime.resume(first.run_id)

            self.assertEqual("completed", resumed.status)
            self.assertEqual(1, resumed.completed_nodes.count("research"))
            self.assertIn("writing", resumed.completed_nodes)

    def test_timeout_and_cost_are_recorded(self):
        runtime = self.frameworks.AgentRuntime(
            self.frameworks.ScriptedAdapter(delay_seconds=0.02),
            timeout_seconds=0.001,
        )
        failed = runtime.run_serial("总结 Agent")

        self.assertEqual("failed", failed.status)
        self.assertIn("超时", failed.error)
        self.assertTrue(all("duration_ms" in event for event in failed.events))
        self.assertGreaterEqual(failed.total_usage_tokens, 0)


if __name__ == "__main__":
    unittest.main()
