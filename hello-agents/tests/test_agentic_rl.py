import importlib.util
from pathlib import Path
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "11-agentic-rl"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "hello_agents_agentic_rl",
        PROJECT / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AgenticRLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rl = load_module()

    def test_reward_versions_distinguish_shortcut_from_tool_policy(self):
        task = self.rl.EVAL_TASKS[0]
        shortcut_v0 = self.rl.generate_trajectory("shortcut", task, split="eval", reward_version="v0")
        tool_v0 = self.rl.generate_trajectory("tool_first", task, split="eval", reward_version="v0")
        shortcut_v1 = self.rl.generate_trajectory("shortcut", task, split="eval", reward_version="v1")
        tool_v1 = self.rl.generate_trajectory("tool_first", task, split="eval", reward_version="v1")
        self.assertGreater(shortcut_v0.total_reward, tool_v0.total_reward)
        self.assertGreater(tool_v1.total_reward, shortcut_v1.total_reward)
        self.assertTrue(shortcut_v1.unsafe)

    def test_relative_advantage_is_grouped_by_task(self):
        trajectories = self.rl.sample_trajectories(
            ("tool_first", "shortcut"),
            self.rl.EVAL_TASKS,
            split="eval",
            reward_version="v1",
        )
        advantages = self.rl.relative_advantages(trajectories)
        self.assertEqual(4, len(advantages))
        self.assertEqual({"eval-01", "eval-02"}, {item["task_id"] for item in advantages})
        self.assertAlmostEqual(0.0, sum(item["relative_advantage"] for item in advantages), places=4)

    def test_safety_gate_rejects_unsafe_policy(self):
        report = self.rl.experiment_report(reward_version="v1")
        self.assertTrue(report["safety_gate"]["tool_first"]["passed"])
        self.assertFalse(report["safety_gate"]["shortcut"]["passed"])

    def test_trajectory_store_round_trips_jsonl(self):
        trajectories = self.rl.sample_trajectories(
            ("tool_first",),
            self.rl.TRAIN_TASKS,
            split="train",
            reward_version="v1",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trajectories.jsonl"
            self.rl.TrajectoryStore.save(path, trajectories)
            loaded = self.rl.TrajectoryStore.load(path)
        self.assertEqual(trajectories, loaded)

    def test_preference_comparison_prioritizes_safety(self):
        task = self.rl.EVAL_TASKS[0]
        shortcut = self.rl.generate_trajectory("shortcut", task, split="eval", reward_version="v0")
        tool_first = self.rl.generate_trajectory("tool_first", task, split="eval", reward_version="v0")
        self.assertEqual("tool_first", self.rl.preferred_trajectory(shortcut, tool_first).policy)

    def test_invalid_reward_version_is_rejected(self):
        with self.assertRaises(ValueError):
            self.rl.get_reward_config("v9")


if __name__ == "__main__":
    unittest.main()
