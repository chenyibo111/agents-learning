import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace


PROJECT_DIR = (
    Path(__file__).resolve().parents[1] / "projects" / "28-document-retrieval"
)
sys.path.insert(0, str(PROJECT_DIR))

from answer import DemoAnswerer, LLMAnswerer, validate_llm_config  # noqa: E402
from ingest import load_chunks  # noqa: E402
from retrievers import KeywordRetriever, VectorRetriever  # noqa: E402


class FakeEmbeddingModel:
    def encode(self, texts, normalize_embeddings=True):
        return [[float(len(text)), 1.0] for text in texts]


class FakeCollection:
    def query(self, **kwargs):
        return {
            "documents": [["状态可以在节点之间流转。"]],
            "metadatas": [[{"source": "state.md", "chunk_id": "state-1"}]],
            "distances": [[0.2]],
        }


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


class DocumentIngestionTests(unittest.TestCase):
    def test_load_chunks_preserves_source_and_chunk_id(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "memory.md").write_text(
                "# 记忆\n\nAgent 可以保存状态。\n\n状态应该可恢复。",
                encoding="utf-8",
            )

            chunks = load_chunks(root)

        self.assertEqual([chunk["chunk_id"] for chunk in chunks], ["memory-1", "memory-2"])
        self.assertEqual(chunks[0]["source"], "memory.md")
        self.assertIn("状态", chunks[0]["text"])


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {
                "source": "memory.md",
                "chunk_id": "memory-1",
                "text": "Agent 可以保存对话状态和短期记忆。",
            },
            {
                "source": "workflow.md",
                "chunk_id": "workflow-1",
                "text": "工作流节点按照边的方向依次执行。",
            },
        ]

    def test_keyword_retriever_returns_common_result_shape(self):
        results = KeywordRetriever(self.chunks).search("对话 记忆", top_k=1)

        self.assertEqual(results[0]["source"], "memory.md")
        self.assertEqual(results[0]["chunk_id"], "memory-1")
        self.assertIn("score", results[0])
        self.assertIn("text", results[0])

    def test_vector_retriever_returns_common_result_shape(self):
        retriever = VectorRetriever(
            self.chunks,
            embedding_model=FakeEmbeddingModel(),
            collection=FakeCollection(),
        )

        results = retriever.search("状态", top_k=1)

        self.assertEqual(results[0]["source"], "state.md")
        self.assertEqual(results[0]["chunk_id"], "state-1")
        self.assertEqual(results[0]["retriever"], "vector")


class AnswererTests(unittest.TestCase):
    def test_demo_answer_includes_source_ids(self):
        answer = DemoAnswerer().answer(
            "状态是什么？",
            [
                {
                    "source": "state.md",
                    "chunk_id": "state-1",
                    "text": "状态在节点之间流转。",
                    "score": 1.0,
                }
            ],
        )

        self.assertIn("state.md#state-1", answer)
        self.assertIn("状态在节点之间流转", answer)

    def test_llm_answerer_sends_retrieved_context_to_fake_client(self):
        client = FakeClient("根据资料，状态可以在节点之间流转。[1]")
        answerer = LLMAnswerer(client=client, model_id="test-model")

        answer = answerer.answer(
            "状态是什么？",
            [
                {
                    "source": "state.md",
                    "chunk_id": "state-1",
                    "text": "状态在节点之间流转。",
                    "score": 1.0,
                }
            ],
        )

        self.assertIn("[1]", answer)
        self.assertIn("state.md#state-1", client.chat.completions.calls[0]["messages"][1]["content"])

    def test_placeholder_llm_key_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_llm_config("你的 API Key", "test-model", "https://example.com/v1")


if __name__ == "__main__":
    unittest.main()
