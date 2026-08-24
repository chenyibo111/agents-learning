import sys
from pathlib import Path
import tempfile
import unittest
import importlib.util


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "08-memory-and-rag"
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from rag_memory.contracts import Document, RetrievalHit
from rag_memory.cache import RetrievalCache
from rag_memory.citations import (
    build_evidence,
    evidence_sufficient,
    validate_citations,
)
from rag_memory.evaluation import evaluate_retriever


MAIN_SPEC = importlib.util.spec_from_file_location("lesson08_main", PROJECT / "main.py")
lesson08_main = importlib.util.module_from_spec(MAIN_SPEC)
assert MAIN_SPEC.loader is not None
MAIN_SPEC.loader.exec_module(lesson08_main)
# Do not leave lesson 08's directory first on sys.path: other course tests
# intentionally import their own lesson-level ``main`` module by name.
if str(PROJECT) in sys.path:
    sys.path.remove(str(PROJECT))
from rag_memory.documents import default_documents
from rag_memory.memory import ShortTermMemory, SQLiteMemoryStore
from rag_memory.retrievers import (
    HybridRetriever,
    KeywordRetriever,
    VectorRetriever,
)


class ContractTests(unittest.TestCase):
    def test_document_and_hit_round_trip_to_json_safe_dict(self):
        document = Document(
            id="doc-1",
            source="memory.md",
            chunk_id="memory-1",
            text="长期记忆保存稳定偏好。",
            tenant_id="tenant-a",
        )
        hit = RetrievalHit(document=document, score=0.75, rank=1)

        self.assertEqual("doc-1", document.to_dict()["id"])
        self.assertEqual("tenant-a", document.to_dict()["tenant_id"])
        self.assertEqual(0.75, hit.to_dict()["score"])
        self.assertEqual("memory-1", hit.to_dict()["chunk_id"])

    def test_default_documents_have_stable_sources_and_requested_tenant(self):
        documents = default_documents(tenant_id="tenant-a")

        self.assertEqual(3, len(documents))
        self.assertEqual(["doc-1", "doc-2", "doc-3"], [doc.id for doc in documents])
        self.assertTrue(all(doc.tenant_id == "tenant-a" for doc in documents))
        self.assertTrue(all(doc.source and doc.chunk_id for doc in documents))


class MemoryTests(unittest.TestCase):
    def test_short_term_memory_preserves_message_order_and_can_clear(self):
        memory = ShortTermMemory()

        memory.add("user", "我喜欢简洁回答")
        memory.add("assistant", "好的")

        self.assertEqual(
            ["user", "assistant"],
            [message["role"] for message in memory.messages],
        )
        memory.clear()
        self.assertEqual([], memory.messages)

    def test_sqlite_memory_round_trips_across_store_instances(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "memory.sqlite3"
            first = SQLiteMemoryStore(database)
            item = first.add("tenant-a", "user-1", "喜欢中文回答", kind="preference")
            first.close()

            second = SQLiteMemoryStore(database)
            restored = second.search("tenant-a", "user-1", "中文")
            second.close()

        self.assertEqual(item.id, restored[0].id)
        self.assertEqual("喜欢中文回答", restored[0].content)

    def test_sqlite_memory_enforces_tenant_and_user_isolation(self):
        store = SQLiteMemoryStore(":memory:")
        item = store.add("tenant-a", "user-1", "只属于 A")
        store.add("tenant-b", "user-1", "只属于 B")

        self.assertEqual([], store.search("tenant-b", "user-1", "A"))
        self.assertEqual([], store.search("tenant-a", "user-2", "A"))
        self.assertFalse(store.delete(item.id, "tenant-b", "user-1"))
        self.assertEqual(1, len(store.search("tenant-a", "user-1", "A")))

    def test_sqlite_memory_delete_is_scoped_to_owner(self):
        store = SQLiteMemoryStore(":memory:")
        item = store.add("tenant-a", "user-1", "待删除")

        self.assertTrue(store.delete(item.id, "tenant-a", "user-1"))
        self.assertFalse(store.delete(item.id, "tenant-a", "user-1"))
        self.assertEqual([], store.search("tenant-a", "user-1", "待删除"))

    def test_sqlite_memory_hides_expired_records(self):
        store = SQLiteMemoryStore(":memory:")
        store.add("tenant-a", "user-1", "已过期", expires_at=10)
        store.add("tenant-a", "user-1", "仍有效", expires_at=30)

        results = store.search("tenant-a", "user-1", "", now=20)

        self.assertEqual(["仍有效"], [item.content for item in results])


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.documents = default_documents(tenant_id="tenant-a")

    def test_keyword_retriever_returns_top_k_hits_and_filters_tenant(self):
        retriever = KeywordRetriever(self.documents)

        hits = retriever.search("长期记忆", tenant_id="tenant-a", top_k=1)

        self.assertEqual(1, len(hits))
        self.assertEqual("doc-2", hits[0].id)
        self.assertGreater(hits[0].score, 0)
        self.assertEqual([], retriever.search("长期记忆", tenant_id="tenant-b", top_k=2))

    def test_vector_retriever_is_deterministic_for_semantically_related_words(self):
        retriever = VectorRetriever(self.documents)

        first = retriever.search("跨会话稳定偏好", tenant_id="tenant-a", top_k=2)
        second = retriever.search("跨会话稳定偏好", tenant_id="tenant-a", top_k=2)

        self.assertEqual([hit.id for hit in first], [hit.id for hit in second])
        self.assertEqual("doc-2", first[0].id)
        self.assertGreater(first[0].score, 0)

    def test_hybrid_retriever_fuses_keyword_and_vector_rankings(self):
        retriever = HybridRetriever(self.documents)

        hits = retriever.search("记忆", tenant_id="tenant-a", top_k=2)

        self.assertEqual("doc-1", hits[0].id)
        self.assertEqual([1, 2], [hit.rank for hit in hits])
        self.assertGreaterEqual(hits[0].score, hits[1].score)

    def test_retriever_version_changes_when_documents_change(self):
        retriever = KeywordRetriever(self.documents)
        original_version = retriever.version
        extra = self.documents[0]

        retriever.delete(extra.id, tenant_id="tenant-a")

        self.assertGreater(retriever.version, original_version)
        self.assertNotIn(
            "doc-1",
            [hit.id for hit in retriever.search("短期记忆", tenant_id="tenant-a")],
        )


class CacheAndCitationTests(unittest.TestCase):
    def setUp(self):
        self.retriever = KeywordRetriever(default_documents(tenant_id="tenant-a"))

    def test_retrieval_cache_reports_hit_and_misses_after_retriever_version_changes(self):
        cache = RetrievalCache(max_entries=2)

        first, first_cached = cache.search(
            self.retriever, "长期记忆", tenant_id="tenant-a", top_k=2
        )
        second, second_cached = cache.search(
            self.retriever, "长期记忆", tenant_id="tenant-a", top_k=2
        )
        self.retriever.add(
            Document(
                id="doc-new",
                source="new.md",
                chunk_id="new-1",
                text="长期记忆的新资料。",
                tenant_id="tenant-a",
            )
        )
        third, third_cached = cache.search(
            self.retriever, "长期记忆", tenant_id="tenant-a", top_k=2
        )

        self.assertFalse(first_cached)
        self.assertTrue(second_cached)
        self.assertFalse(third_cached)
        self.assertEqual([hit.id for hit in first], [hit.id for hit in second])
        self.assertIn("doc-new", [hit.id for hit in third])

    def test_citation_formatter_and_validator_accept_only_current_evidence(self):
        hits = self.retriever.search("长期记忆", tenant_id="tenant-a", top_k=2)

        evidence = build_evidence(hits)
        valid = validate_citations("长期记忆可以跨会话保存。[S1]", hits)
        forged = validate_citations("这是资料中的结论。[S9]", hits)

        self.assertIn("[S1]", evidence)
        self.assertIn(hits[0].document.source, evidence)
        self.assertTrue(valid.valid)
        self.assertFalse(forged.valid)
        self.assertEqual(["S9"], forged.unknown_labels)

    def test_evidence_sufficiency_requires_a_positive_hit(self):
        hits = self.retriever.search("zzzz", tenant_id="tenant-a", top_k=2)

        self.assertFalse(evidence_sufficient(hits))
        self.assertTrue(
            evidence_sufficient(
                self.retriever.search("长期记忆", tenant_id="tenant-a", top_k=2)
            )
        )


class EvaluationTests(unittest.TestCase):
    def test_evaluate_retriever_returns_hit_precision_recall_and_mrr(self):
        retriever = KeywordRetriever(default_documents(tenant_id="tenant-a"))
        cases = [
            {"query": "长期记忆", "relevant_ids": ["doc-2"]},
            {"query": "RAG", "relevant_ids": ["doc-3"]},
        ]

        metrics = evaluate_retriever(
            retriever,
            cases,
            tenant_id="tenant-a",
            top_k=2,
        )

        self.assertEqual(1.0, metrics["hit_at_k"])
        self.assertEqual(0.5, metrics["precision_at_k"])
        self.assertEqual(1.0, metrics["recall_at_k"])
        self.assertEqual(1.0, metrics["mrr"])


class IntegrationTests(unittest.TestCase):
    def test_run_query_supports_hybrid_retrieval_and_reports_cache_state(self):
        cache = lesson08_main.RetrievalCache(max_entries=4)

        first = lesson08_main.run_query(
            "长期记忆和 RAG",
            retriever_name="both",
            top_k=2,
            tenant_id="tenant-a",
            cache=cache,
        )
        second = lesson08_main.run_query(
            "长期记忆和 RAG",
            retriever_name="both",
            top_k=2,
            tenant_id="tenant-a",
            cache=cache,
        )

        self.assertEqual("both", first["retriever"])
        self.assertEqual("tenant-a", first["tenant_id"])
        self.assertFalse(first["cache_hit"])
        self.assertTrue(second["cache_hit"])
        self.assertTrue(first["hits"])
        self.assertTrue(first["evidence_sufficient"])

    def test_llm_mode_stops_before_model_when_evidence_is_insufficient(self):
        calls = []

        def fake_ask(prompt, *, system):
            calls.append((prompt, system))
            return "不应该被调用"

        result = lesson08_main.answer_with_llm(
            "zzzz",
            retriever_name="keyword",
            top_k=2,
            tenant_id="tenant-a",
            asker=fake_ask,
        )

        self.assertFalse(result["evidence_sufficient"])
        self.assertFalse(result["llm_called"])
        self.assertEqual([], calls)
        self.assertIn("证据不足", result["answer"])

    def test_llm_prompt_contains_only_current_evidence_and_validates_citation(self):
        calls = []

        def fake_ask(prompt, *, system):
            calls.append(prompt)
            return "长期记忆可以保存稳定偏好。[S1]"

        result = lesson08_main.answer_with_llm(
            "长期记忆",
            retriever_name="keyword",
            top_k=1,
            tenant_id="tenant-a",
            asker=fake_ask,
        )

        self.assertTrue(result["llm_called"])
        self.assertTrue(result["citation_valid"])
        self.assertEqual(1, len(calls))
        self.assertIn("[S1]", calls[0])
        self.assertIn("长期记忆保存", calls[0])


if __name__ == "__main__":
    unittest.main()
