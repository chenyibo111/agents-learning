import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "15-cyber-town"
sys.path.insert(0, str(PROJECT))

from cyber_town.engine import SimulationEngine
from cyber_town.evaluation import evaluate_simulation
from cyber_town.policies import MerchantPolicy
from cyber_town.schemas import Action
from cyber_town.visibility import observation_for
from cyber_town.world import apply_action, initial_world


class CyberTownTests(unittest.TestCase):
    def test_initial_world_has_three_roles_and_private_memory(self):
        world = initial_world(seed=7)
        self.assertEqual(3, len(world.agents))
        self.assertEqual({"merchant", "researcher", "courier"}, {a.agent_id for a in world.agents})
        self.assertTrue(all(agent.private_memory for agent in world.agents))
        self.assertEqual(7, world.public_facts["seed"])

    def test_observation_hides_other_agents_private_memory(self):
        world = initial_world(seed=7)
        observation = observation_for(world, "merchant", ())
        self.assertIn("private_memory", observation.own_state)
        self.assertNotIn("private_memory", json.dumps(observation.to_dict()["public_facts"]))
        self.assertNotIn("researcher-secret", json.dumps(observation.to_dict()))

    def test_one_tick_executes_trade_and_dialogue(self):
        state = SimulationEngine(seed=7).run(ticks=1)
        event_types = [event.event_type for event in state.events]
        self.assertIn("offer", event_types)
        self.assertIn("trade_completed", event_types)
        self.assertIn("message", event_types)
        self.assertEqual(25, sum(agent.balance for agent in state.world.agents))

    def test_invalid_trade_is_rejected_by_environment_rule(self):
        world = initial_world(seed=7)
        action = Action(
            agent_id="researcher",
            action_type="offer",
            target_id="merchant",
            item="map",
            quantity=99,
            price=1,
        )
        next_world, event = apply_action(world, action, tick=0)
        self.assertEqual(world, next_world)
        self.assertEqual("action_rejected", event.event_type)
        self.assertEqual("insufficient_inventory", event.rule)

    def test_same_seed_produces_same_simulation(self):
        first = SimulationEngine(seed=19).run(ticks=3)
        second = SimulationEngine(seed=19).run(ticks=3)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_checkpoint_resume_matches_uninterrupted_run(self):
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            interrupted = SimulationEngine(seed=7).run(
                ticks=3, interrupt_after_tick=1, checkpoint_path=checkpoint
            )
            resumed = SimulationEngine.resume(checkpoint, ticks=2)
        continuous = SimulationEngine(seed=7).run(ticks=3)
        self.assertEqual("INTERRUPTED", interrupted.status)
        self.assertEqual(continuous.to_dict(), resumed.to_dict())

    def test_evaluation_reports_events_and_conservation(self):
        state = SimulationEngine(seed=7).run(ticks=2)
        report = evaluate_simulation(state)
        self.assertEqual(2, report["ticks"])
        self.assertGreaterEqual(report["trade_count"], 1)
        self.assertTrue(report["resource_conservation"]["passed"])
        self.assertTrue(report["privacy_audit"]["passed"])

    def test_public_events_do_not_leak_private_memory(self):
        state = SimulationEngine(seed=7).run(ticks=2)
        for event in state.events:
            if event.public:
                self.assertNotIn("private_memory", json.dumps(event.to_dict()))
                self.assertNotIn("researcher-secret", json.dumps(event.to_dict()))

    def test_cli_json_and_output_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--demo",
                    "--json",
                    "--ticks",
                    "1",
                    "--output-dir",
                    directory,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(result.stdout)
            self.assertEqual("COMPLETED", payload["state"]["status"])
            self.assertTrue((Path(directory) / "checkpoint.json").exists())
            self.assertTrue((Path(directory) / "events.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
