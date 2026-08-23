import importlib.util
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "02-agent-history"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "hello_agents_agent_history",
        PROJECT / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AgentHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = load_module()

    def test_timeline_is_chronological_and_complete(self):
        stages = self.history.STAGES
        self.assertGreaterEqual(len(stages), 8)
        self.assertEqual(
            sorted(stage.year for stage in stages),
            [stage.year for stage in stages],
        )
        names = {stage.name for stage in stages}
        self.assertIn("符号主义与规则", names)
        self.assertIn("搜索与规划", names)
        self.assertIn("强化学习", names)
        self.assertIn("Transformer", names)
        self.assertIn("LLM Agent", names)

    def test_every_stage_explains_representation_feedback_limit_and_failure(self):
        for stage in self.history.STAGES:
            self.assertTrue(stage.representation, stage.name)
            self.assertTrue(stage.feedback, stage.name)
            self.assertTrue(stage.limitation, stage.name)
            self.assertTrue(stage.failure_case, stage.name)

    def test_rendered_views_contain_the_comparison_fields(self):
        timeline = self.history.render_timeline()
        failures = self.history.render_failures()
        self.assertIn("表示=", timeline)
        self.assertIn("反馈=", timeline)
        self.assertIn("限制=", timeline)
        self.assertIn("失败案例=", self.history.render_timeline(include_failures=True))
        self.assertIn("错误工具或参数", failures)

    def test_timeline_data_is_json_serializable(self):
        data = self.history.timeline_data()
        self.assertEqual(len(self.history.STAGES), len(data))
        self.assertIsInstance(data[0]["year"], int)
        self.assertIn("failure_case", data[0])


if __name__ == "__main__":
    unittest.main()
