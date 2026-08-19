import sys
import unittest
import importlib.util
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "30-cited-markdown-report"
)
sys.path.insert(0, str(PROJECT_DIR))

sys.modules.pop("report", None)
from report import (  # noqa: E402
    DemoReportWriter,
    LLMReportWriter,
    build_citations,
    validate_report_citations,
)
main_spec = importlib.util.spec_from_file_location(
    "lesson30_main",
    PROJECT_DIR / "main.py",
)
lesson30_main = importlib.util.module_from_spec(main_spec)
assert main_spec.loader is not None
main_spec.loader.exec_module(lesson30_main)
run_report = lesson30_main.run_report


EVIDENCE = [
    {
        "claim": "状态可以通过检查点保存。",
        "source": "agent-state.md",
        "chunk_id": "agent-state-2",
        "quote": "状态可以通过检查点保存。",
        "verified": True,
    },
    {
        "claim": "包含副作用的节点需要幂等设计。",
        "source": "workflow.md",
        "chunk_id": "workflow-1",
        "quote": "包含副作用的节点需要幂等设计。",
        "verified": True,
    },
]


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=FakeCompletions(content))


class CitationTests(unittest.TestCase):
    def test_build_citations_deduplicates_source_and_chunk_id(self):
        citations = build_citations(
            [
                *EVIDENCE,
                {**EVIDENCE[0], "claim": "同一片段的另一条结论"},
            ]
        )

        self.assertEqual(
            [(item["number"], item["source"], item["chunk_id"]) for item in citations],
            [
                (1, "agent-state.md", "agent-state-2"),
                (2, "workflow.md", "workflow-1"),
            ],
        )

    def test_demo_report_contains_claims_citations_and_sources(self):
        report = DemoReportWriter().write_report("Agent 状态管理", EVIDENCE)

        self.assertIn("# Agent 状态管理", report)
        self.assertIn("状态可以通过检查点保存。[1]", report)
        self.assertIn("包含副作用的节点需要幂等设计。[2]", report)
        self.assertIn("agent-state.md#agent-state-2", report)
        self.assertIn("workflow.md#workflow-1", report)

    def test_validate_report_rejects_unknown_citation_number(self):
        citations = build_citations(EVIDENCE[:1])

        with self.assertRaisesRegex(ValueError, "不存在的引用编号"):
            validate_report_citations("# 报告\n\n结论。[2]", citations)

    def test_validate_report_requires_citation_when_evidence_exists(self):
        citations = build_citations(EVIDENCE[:1])

        with self.assertRaisesRegex(ValueError, "至少包含一个引用"):
            validate_report_citations("# 报告\n\n没有引用的结论。", citations)

    def test_demo_report_rejects_unverified_evidence(self):
        with self.assertRaisesRegex(ValueError, "verified=True"):
            DemoReportWriter().write_report(
                "Agent 状态管理",
                [{**EVIDENCE[0], "verified": False}],
            )


class LLMReportTests(unittest.TestCase):
    def test_llm_report_writer_forwards_citations_to_model(self):
        client = FakeClient("# 研究报告\n\n结论：状态可以恢复。[1]")
        writer = LLMReportWriter(client=client, model_id="test-model")

        report = writer.write_report("Agent 状态管理", EVIDENCE[:1])

        self.assertIn("[1]", report)
        prompt = client.chat.completions.calls[0]["messages"][1]["content"]
        self.assertIn("agent-state.md#agent-state-2", prompt)

    def test_llm_report_writer_rejects_model_citation_outside_catalog(self):
        client = FakeClient("# 研究报告\n\n结论。[9]")
        writer = LLMReportWriter(client=client, model_id="test-model")

        with self.assertRaisesRegex(ValueError, "不存在的引用编号"):
            writer.write_report("Agent 状态管理", EVIDENCE[:1])


class PipelineIntegrationTests(unittest.TestCase):
    def test_run_report_connects_lesson_29_workflow_to_report_writer(self):
        class StaticRetriever:
            def search(self, query, top_k=3):
                return [
                    {
                        "source": "agent-state.md",
                        "chunk_id": "agent-state-2",
                        "text": "状态可以通过检查点保存。",
                        "score": 1.0,
                    }
                ]

        class StaticRuntime:
            def plan(self, topic):
                return ["定义问题"]

            def extract_evidence(self, topic, chunks):
                return [
                    {
                        "claim": chunks[0]["text"],
                        "source": chunks[0]["source"],
                        "chunk_id": chunks[0]["chunk_id"],
                        "quote": chunks[0]["text"],
                    }
                ]

            def verify_evidence(self, topic, evidence):
                return [{**evidence[0], "verified": True}]

        output = []
        report = run_report(
            "状态管理",
            StaticRuntime(),
            StaticRetriever(),
            DemoReportWriter(),
            output_fn=output.append,
        )

        self.assertIn("[1]", report)
        self.assertIn('"status": "completed"', output[0])


if __name__ == "__main__":
    unittest.main()
