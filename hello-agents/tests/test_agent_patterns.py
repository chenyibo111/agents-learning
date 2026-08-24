import importlib.util
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "04-agent-patterns"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "hello_agents_agent_patterns",
        PROJECT / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AgentPatternTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = load_module()

    def test_react_has_action_observation_and_answer(self):
        trace = self.patterns.run_react()
        self.assertEqual("ReAct", trace[0].pattern)
        self.assertEqual("act", trace[0].phase)
        self.assertTrue(trace[0].observation)
        self.assertEqual("answer", trace[-1].action)
        self.assertTrue(all("thought" not in event.__dict__ for event in trace))

    def test_react_stops_on_repeated_action(self):
        trace = self.patterns.run_react(repeat_action=True)
        self.assertEqual("guard", trace[-1].phase)
        self.assertIn("重复行动", trace[-1].error)

    def test_plan_replans_when_source_becomes_invalid(self):
        trace = self.patterns.run_plan_and_solve(invalidate_after=1)
        phases = [event.phase for event in trace]
        self.assertIn("replan", phases)
        self.assertIn("fallback", " ".join(event.action for event in trace))
        self.assertEqual("answer", trace[-1].action)

    def test_reflection_rule_check_removes_unknown_citation(self):
        trace = self.patterns.run_reflection(
            citations=["S1", "S-missing"],
            available_sources={"S1", "S2"},
        )
        self.assertEqual("critique", trace[1].phase)
        self.assertIn("引用不存在", trace[1].error)
        self.assertEqual("revise", trace[2].phase)
        self.assertEqual(["S1"], trace[-1].state["citations"])

    def test_trace_events_are_json_serializable(self):
        trace = self.patterns.run_reflection(citations=["S1"])
        serialized = [self.patterns.asdict(event) for event in trace]
        self.assertIn("pattern", serialized[0])
        self.assertIsInstance(serialized[0]["state"], dict)


if __name__ == "__main__":
    unittest.main()
