import importlib.util
import unittest
from pathlib import Path


SOURCE_FILE = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "22-observability-cost-control"
    / "main.py"
)
SPEC = importlib.util.spec_from_file_location("observability_cost", SOURCE_FILE)
assert SPEC and SPEC.loader
observability_cost = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observability_cost)


class ObservabilityCostTests(unittest.TestCase):
    def test_estimates_tokens_and_cost(self) -> None:
        pricing = observability_cost.ModelPricing(
            input_per_million=1.0,
            output_per_million=2.0,
        )

        self.assertEqual(observability_cost.estimate_tokens("abcdefgh"), 2)
        self.assertEqual(
            observability_cost.calculate_cost(1_000_000, 2_000_000, pricing),
            5.0,
        )

    def test_records_parent_child_spans_and_duration(self) -> None:
        ticks = iter([0.0, 0.1, 0.2, 0.5])
        recorder = observability_cost.TraceRecorder(clock=lambda: next(ticks))

        root = recorder.start_span("workflow")
        child = recorder.start_span("planner", parent_id=root.span_id, kind="llm")
        recorder.finish_span(child.span_id)
        recorder.finish_span(root.span_id)

        self.assertEqual(len(recorder.spans), 2)
        self.assertEqual(child.parent_id, root.span_id)
        self.assertAlmostEqual(child.duration_ms, 100.0)
        self.assertAlmostEqual(root.duration_ms, 500.0)

    def test_budget_blocks_over_limit_model_call(self) -> None:
        recorder = observability_cost.TraceRecorder(budget_usd=0.001)
        pricing = observability_cost.ModelPricing(
            input_per_million=10.0,
            output_per_million=10.0,
        )
        span = recorder.start_span("planner", kind="llm")

        with self.assertRaises(observability_cost.BudgetExceededError):
            recorder.record_model_call(
                span.span_id,
                "a" * 1000,
                "b" * 1000,
                pricing,
            )

        recorder.finish_span(span.span_id, status="budget_exceeded")
        self.assertEqual(recorder.budget.spent_usd, 0.0)
        self.assertEqual(recorder.spans[0].status, "budget_exceeded")

    def test_report_contains_failures_and_slowest_span(self) -> None:
        ticks = iter([0.0, 0.1, 0.2, 0.8, 0.9, 1.0])
        recorder = observability_cost.TraceRecorder(clock=lambda: next(ticks))

        fast = recorder.start_span("fast")
        recorder.finish_span(fast.span_id)
        slow = recorder.start_span("slow")
        recorder.finish_span(slow.span_id)
        failed = recorder.start_span("failed")
        recorder.finish_span(failed.span_id, status="error", error="boom")

        report = recorder.report()

        self.assertEqual(report["failed_spans"], ["failed"])
        self.assertEqual(report["slowest_span"], "slow")
        self.assertEqual(report["total_spans"], 3)

    def test_report_uses_child_span_for_slowest_node(self) -> None:
        ticks = iter([0.0, 0.1, 0.8, 0.9])
        recorder = observability_cost.TraceRecorder(clock=lambda: next(ticks))

        root = recorder.start_span("workflow", kind="workflow")
        child = recorder.start_span("retrieval", parent_id=root.span_id)
        recorder.finish_span(child.span_id)
        recorder.finish_span(root.span_id)

        report = recorder.report()

        self.assertEqual(report["slowest_span"], "retrieval")


if __name__ == "__main__":
    unittest.main()
