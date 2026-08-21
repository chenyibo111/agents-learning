import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "29-research-task-workflow"
)
sys.path.insert(0, str(PROJECT_DIR))

for module_name in ("state", "runtime", "workflow", "retrieval_source"):
    sys.modules.pop(module_name, None)

from runtime import DemoRuntime, LLMRuntime  # noqa: E402
from retrieval_source import build_retriever  # noqa: E402
from state import ResearchState  # noqa: E402
import workflow  # noqa: E402


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def search(self, query, top_k=3):
        self.calls.append((query, top_k))
        return [
            {
                "source": "memory.md",
                "chunk_id": "memory-1",
                "text": "状态可以在节点之间流转。",
                "score": 0.9,
                "retriever": "keyword",
            }
        ]


class FakeCompletions:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=next(self.responses)))
            ]
        )


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(completions=FakeCompletions(responses))


class RuntimeContractTests(unittest.TestCase):
    def test_demo_runtime_extracts_and_verifies_retrieved_chunks(self):
        runtime = DemoRuntime()
        chunks = FakeRetriever().search("状态")

        plan = runtime.plan("工作流状态")
        evidence = runtime.extract_evidence("工作流状态", chunks)
        verified = runtime.verify_evidence("工作流状态", evidence)

        self.assertTrue(plan)
        self.assertEqual(evidence[0]["source"], "memory.md")
        self.assertTrue(verified[0]["verified"])
        self.assertEqual(verified[0]["chunk_id"], "memory-1")

    def test_llm_runtime_validates_structured_responses(self):
        client = FakeClient(
            [
                '["定义问题", "检索资料", "核验结论"]',
                '[{"claim":"状态在节点之间流转","source":"memory.md","chunk_id":"memory-1","quote":"状态可以在节点之间流转。"}]',
                '[{"claim":"状态在节点之间流转","source":"memory.md","chunk_id":"memory-1","quote":"状态可以在节点之间流转。","verified":true,"note":"证据与资料一致"}]',
            ]
        )
        runtime = LLMRuntime(client=client, model_id="test-model")

        plan = runtime.plan("工作流状态")
        evidence = runtime.extract_evidence(
            "工作流状态",
            [
                {
                    "source": "memory.md",
                    "chunk_id": "memory-1",
                    "text": "状态可以在节点之间流转。",
                }
            ],
        )
        verified = runtime.verify_evidence("工作流状态", evidence)

        self.assertEqual(plan[0], "定义问题")
        self.assertEqual(verified[0]["chunk_id"], "memory-1")
        self.assertTrue(verified[0]["verified"])
        self.assertEqual(len(client.chat.completions.calls), 3)

    def test_llm_runtime_rejects_evidence_from_unretrieved_chunk(self):
        client = FakeClient(
            [
                '[{"claim":"未检索到的事实","source":"unknown.md","chunk_id":"unknown-1","quote":"不存在的资料"}]'
            ]
        )
        runtime = LLMRuntime(client=client, model_id="test-model")

        with self.assertRaisesRegex(ValueError, "不在检索结果中"):
            runtime.extract_evidence(
                "工作流状态",
                [
                    {
                        "source": "memory.md",
                        "chunk_id": "memory-1",
                        "text": "状态可以在节点之间流转。",
                    }
                ],
            )

    def test_llm_runtime_rejects_verification_from_unknown_chunk(self):
        client = FakeClient(
            [
                '[{"claim":"被替换的事实","source":"unknown.md","chunk_id":"unknown-1","quote":"不存在的资料","verified":true,"note":"错误来源"}]'
            ]
        )
        runtime = LLMRuntime(client=client, model_id="test-model")

        with self.assertRaisesRegex(ValueError, "不在待核验证据中"):
            runtime.verify_evidence(
                "工作流状态",
                [
                    {
                        "claim": "状态可以在节点之间流转",
                        "source": "memory.md",
                        "chunk_id": "memory-1",
                        "quote": "状态可以在节点之间流转。",
                    }
                ],
            )


class WorkflowContractTests(unittest.TestCase):
    def test_nodes_update_state_in_research_order(self):
        runtime = DemoRuntime()
        retriever = FakeRetriever()
        state: ResearchState = {"topic": "工作流状态", "events": []}

        state = {**state, **workflow.plan_node(state, runtime)}
        state = {**state, **workflow.retrieve_node(state, retriever, top_k=2)}
        state = {**state, **workflow.extract_node(state, runtime)}
        state = {**state, **workflow.verify_node(state, runtime)}

        self.assertEqual(state["status"], "completed")
        self.assertTrue(state["verified_evidence"])
        self.assertEqual(retriever.calls, [("工作流状态", 2)])
        self.assertEqual(
            state["events"],
            [
                "plan 完成",
                "retrieve 完成",
                "extract 完成",
                "verify 完成",
            ],
        )

    def test_graph_runs_with_demo_runtime_and_fake_retriever(self):
        if not workflow.LANGGRAPH_AVAILABLE:
            self.skipTest("LangGraph 未安装")

        graph = workflow.build_graph(DemoRuntime(), FakeRetriever(), top_k=1)
        result = graph.invoke(
            {"topic": "图工作流", "events": []},
            {"configurable": {"thread_id": "lesson-29-test"}},
        )

        self.assertEqual(result["status"], "completed")
        self.assertIn("verify 完成", result["events"])
        self.assertEqual(result["verified_evidence"][0]["chunk_id"], "memory-1")


class RetrievalAdapterTests(unittest.TestCase):
    def test_keyword_mode_reuses_lesson_28_ingestion_and_retriever(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "notes.md").write_text(
                "# 笔记\n\n状态可以恢复工作流。", encoding="utf-8"
            )
            retriever = build_retriever("keyword", knowledge_dir=root)

            results = retriever.search("恢复工作流")

        self.assertEqual(results[0]["source"], "notes.md")
        self.assertEqual(results[0]["chunk_id"], "notes-1")


if __name__ == "__main__":
    unittest.main()
