import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "11-agentic-rl"


def load_module():
    spec = importlib.util.spec_from_file_location("hello_agents_agentic_rl_engineering", PROJECT / "main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AgenticRLEngineeringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rl = load_module()

    def test_run_has_manifest_train_eval_split_and_audit(self):
        manifest, trajectories, report = self.rl.run_experiment()
        self.assertEqual("1.0", manifest.schema_version)
        self.assertEqual(12, len(trajectories))
        self.assertEqual({"train", "eval"}, {item.split for item in trajectories})
        self.assertTrue(report["reward_audit"]["shortcut_ranked_first_in_v0"])
        self.assertTrue(report["reward_audit"]["safe_policy_ranked_first_in_v1"])

    def test_artifact_store_writes_roundtrippable_run(self):
        manifest, trajectories, report = self.rl.run_experiment()
        with tempfile.TemporaryDirectory() as directory:
            artifacts = self.rl.ArtifactStore(directory).save_run(manifest, trajectories, report)
            self.assertTrue(Path(artifacts["manifest"]).exists())
            self.assertTrue(Path(artifacts["report"]).exists())
            loaded = self.rl.TrajectoryStore.load(artifacts["trajectories"])
            self.assertEqual(trajectories, loaded)
            saved_manifest = json.loads(Path(artifacts["manifest"]).read_text(encoding="utf-8"))
            self.assertEqual(manifest.run_id, saved_manifest["run_id"])

    def test_artifact_store_rejects_sensitive_fields(self):
        manifest, trajectories, report = self.rl.run_experiment()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.rl.ArtifactStore(directory).save_run(
                    manifest, trajectories, {**report, "api_key": "should-not-be-saved"}
                )

    def test_invalid_split_is_rejected(self):
        with self.assertRaises(ValueError):
            self.rl.generate_trajectory(
                "tool_first", self.rl.TRAIN_TASKS[0], split="production"
            )

    def test_step_rewards_reconcile_with_breakdown_total(self):
        trajectory = self.rl.generate_trajectory(
            "illegal_tool", self.rl.EVAL_TASKS[0], split="eval", reward_version="v1"
        )
        self.assertAlmostEqual(
            trajectory.total_reward,
            sum(step.reward for step in trajectory.steps),
            places=4,
        )


if __name__ == "__main__":
    unittest.main()
