import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "12-agent-evaluation"
sys.path.insert(0, str(PROJECT))

from agent_evaluation.comparison import compare_strategies, pareto_frontier
from agent_evaluation.dataset import EVAL_DATASET_VERSION, evaluation_cases, get_case
from agent_evaluation.experiment import run_experiment
from agent_evaluation.gate import evaluate_release_gate
from agent_evaluation.judges import calibrate_judges, judge_run
from agent_evaluation.metrics import compute_metrics
from agent_evaluation.runner import replay_run, run_case, run_dataset
from agent_evaluation.storage import ArtifactStore


class AgentEvaluationTests(unittest.TestCase):
    def test_dataset_is_versioned_and_covers_required_scenarios(self):
        cases = evaluation_cases()
        self.assertEqual("agent-eval-v1", EVAL_DATASET_VERSION)
        self.assertGreaterEqual(len(cases), 5)
        self.assertTrue({case.scenario for case in cases} >= {
            "normal", "boundary", "tool_failure", "prompt_injection", "evidence_missing"
        })
        for case in cases:
            self.assertTrue(case.case_id)
            self.assertIn(case.split, {"train", "eval"})

    def test_unknown_case_is_rejected(self):
        with self.assertRaises(ValueError):
            get_case("missing-case")

    def test_guarded_strategy_records_replayable_trace(self):
        run = run_case("guarded", get_case("normal-01"))
        self.assertTrue(run.success)
        self.assertGreaterEqual(len(run.trace), 1)
        self.assertEqual(list(run.trace), replay_run(run))
        self.assertEqual(EVAL_DATASET_VERSION, run.dataset_version)

    def test_unsafe_strategy_is_detected_on_prompt_injection(self):
        run = run_case("unsafe", get_case("injection-01"))
        self.assertFalse(run.success)
        self.assertTrue(run.safety_violations)

    def test_metrics_are_hard_rule_metrics(self):
        runs = run_dataset("guarded")
        report = compute_metrics("guarded", runs)
        self.assertEqual(len(runs), report.count)
        self.assertEqual(1.0, report.success_rate)
        self.assertEqual(0.0, report.safety_violation_rate)
        self.assertGreater(report.avg_cost_usd, 0.0)
        self.assertEqual((), report.failed_case_ids)

    def test_judge_is_separate_and_calibration_does_not_change_hard_metrics(self):
        run = run_case("guarded", get_case("evidence-01"))
        result = judge_run(run)
        self.assertIn("evidence", result.rubric)
        self.assertIsNone(result.human_label)
        calibrated = calibrate_judges([result], {result.run_id: 1.0})
        self.assertEqual(1, calibrated["calibrated_count"])
        self.assertEqual(1.0, calibrated["mean_human_score"])
        self.assertTrue(run.success)

    def test_comparison_and_pareto_frontier(self):
        reports = {
            strategy: compute_metrics(strategy, run_dataset(strategy))
            for strategy in ("guarded", "fast", "unsafe")
        }
        comparison = compare_strategies(reports)
        self.assertIn("guarded", comparison)
        frontier = pareto_frontier(reports)
        self.assertIn("guarded", frontier)
        self.assertNotIn("unsafe", frontier)

    def test_release_gate_reports_failed_metric_and_case(self):
        report = compute_metrics("unsafe", run_dataset("unsafe"))
        gate = evaluate_release_gate(report)
        self.assertFalse(gate.passed)
        self.assertIn("safety_violation_rate", gate.failed_metrics)
        self.assertIn("injection-01", gate.failed_case_ids)

    def test_artifacts_round_trip(self):
        result = run_experiment()
        with tempfile.TemporaryDirectory() as directory:
            artifacts = ArtifactStore(directory).save_run(**result)
            loaded = ArtifactStore(directory).load_run(artifacts["run_id"])
        self.assertEqual(result["manifest"], loaded["manifest"])
        self.assertEqual(len(result["runs"]), len(loaded["runs"]))
        self.assertEqual(result["report"]["gate"], loaded["report"]["gate"])

    def test_cli_generates_json_and_supports_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            command = [
                sys.executable,
                str(PROJECT / "main.py"),
                "--demo",
                "--json",
                "--output-dir",
                directory,
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=True)
            report = json.loads(completed.stdout)
            self.assertEqual(EVAL_DATASET_VERSION, report["dataset_version"])
            self.assertTrue(Path(report["artifacts"]["report"]).exists())

            replay = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT / "main.py"),
                    "--replay-case",
                    "injection-01",
                    "--strategy",
                    "guarded",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertIn("injection-01", replay.stdout)


if __name__ == "__main__":
    unittest.main()
