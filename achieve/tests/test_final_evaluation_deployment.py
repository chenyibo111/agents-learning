import sys
import unittest
from pathlib import Path


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "32-final-evaluation-deployment"
)
sys.path.insert(0, str(PROJECT_DIR))

from evaluation import EvalCase, Evaluator  # noqa: E402
from monitoring import (  # noqa: E402
    BudgetExceededError,
    Monitor,
    ModelPricing,
    calculate_cost,
    estimate_tokens,
)
from deployment import validate_config  # noqa: E402


class FakeApp:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.queries = []

    def run(self, query):
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.result


class EvaluationTests(unittest.TestCase):
    def test_evaluator_passes_when_sources_status_and_citations_match(self):
        app = FakeApp(
            {
                "status": "completed",
                "sources": ["agent-state.md#agent-state-2"],
                "report": "状态可以恢复。[1]\n[1] agent-state.md#agent-state-2",
            }
        )
        case = EvalCase(
            case_id="state",
            query="如何恢复状态？",
            expected_sources=("agent-state.md",),
            require_citation=True,
        )

        result = Evaluator((case,)).evaluate(app)["results"][0]

        self.assertTrue(result["passed"])
        self.assertEqual(app.queries, ["如何恢复状态？"])

    def test_evaluator_reports_failed_source_and_citation_checks(self):
        app = FakeApp(
            {
                "status": "completed",
                "sources": ["other.md#other-1"],
                "report": "没有引用",
            }
        )
        case = EvalCase(
            case_id="grounding",
            query="资料不足怎么办？",
            expected_sources=("grounding.md",),
            require_citation=True,
        )

        result = Evaluator((case,)).evaluate(app)["results"][0]

        self.assertFalse(result["passed"])
        self.assertFalse(result["source_hit"])
        self.assertFalse(result["citation_ok"])

    def test_evaluator_captures_app_errors_and_summary(self):
        app = FakeApp(error=RuntimeError("模型不可用"))
        cases = (
            EvalCase(
                case_id="error-case",
                query="测试失败",
                expected_sources=(),
                require_citation=False,
            ),
        )

        summary = Evaluator(cases).evaluate(app)

        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["passed"], 0)
        self.assertEqual(summary["pass_rate"], 0.0)
        self.assertIn("模型不可用", summary["results"][0]["error"])


class MonitoringTests(unittest.TestCase):
    def test_monitor_records_spans_tokens_cost_and_slowest_span(self):
        ticks = iter([0.0, 0.01, 0.01, 0.04])
        monitor = Monitor(budget_usd=1.0, clock=lambda: next(ticks))
        fast = monitor.start_span("fast")
        monitor.finish_span(fast.span_id)
        slow = monitor.start_span("slow")
        monitor.record_model_call(
            slow.span_id,
            "输入文本",
            "输出文本",
            ModelPricing(input_per_million=1.0, output_per_million=2.0),
        )
        monitor.finish_span(slow.span_id)

        report = monitor.report()

        self.assertEqual(report["total_spans"], 2)
        self.assertEqual(report["slowest_span"], "slow")
        self.assertGreater(report["total_input_tokens"], 0)
        self.assertGreater(report["total_cost_usd"], 0)

    def test_monitor_rejects_call_over_budget(self):
        monitor = Monitor(budget_usd=0.000001)
        span = monitor.start_span("llm")

        with self.assertRaises(BudgetExceededError):
            monitor.record_model_call(
                span.span_id,
                "x" * 1000,
                "y" * 1000,
                ModelPricing(input_per_million=10.0, output_per_million=10.0),
            )

    def test_token_and_cost_helpers_are_deterministic(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertEqual(
            calculate_cost(1_000_000, 500_000, ModelPricing(1.0, 2.0)),
            2.0,
        )


class DeploymentTests(unittest.TestCase):
    def test_demo_mode_is_ready_without_llm_credentials(self):
        config = validate_config({}, mode="demo")

        self.assertTrue(config.ready)
        self.assertFalse(config.api_key_configured)

    def test_llm_mode_reports_missing_and_placeholder_config(self):
        config = validate_config(
            {
                "OPENAI_API_KEY": "你的 API Key",
                "OPENAI_MODEL": "",
                "OPENAI_BASE_URL": "not-a-url",
            },
            mode="llm",
        )

        self.assertFalse(config.ready)
        self.assertGreaterEqual(len(config.problems), 3)

    def test_health_summary_never_contains_api_key(self):
        config = validate_config(
            {
                "OPENAI_API_KEY": "real-looking-secret",
                "OPENAI_MODEL": "test-model",
                "OPENAI_BASE_URL": "https://example.com/v1",
            },
            mode="llm",
        )

        summary = config.health_summary()

        self.assertNotIn("real-looking-secret", str(summary))
        self.assertTrue(summary["api_key_configured"])
        self.assertEqual(summary["model"], "test-model")


if __name__ == "__main__":
    unittest.main()
