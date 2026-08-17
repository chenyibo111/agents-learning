import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError as error:
    raise RuntimeError(
        "缺少本课依赖，请先执行：\n"
        "pip install -r .\\projects\\13-rag-evaluation\\requirements.txt"
    ) from error


KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
VECTOR_STORE_DIR = Path(__file__).with_name("vector_store")
COLLECTION_NAME = "rag_evaluation"
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)


EVAL_CASES = [
    ("Agent 如何感知环境并采取行动？", {"agent-basics.md"}),
    ("如何让模型使用外部能力？", {"tool-calling.md"}),
    ("程序重新启动后如何找回之前的信息？", {"memory.md"}),
    ("资料不足时 Agent 应该怎么做？", {"grounding.md"}),
    ("工具执行失败后应该如何处理？", {"tool-calling.md"}),
    ("如何保存对话历史？", {"memory.md"}),
]


def load_chunks() -> list[dict[str, Any]]:
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", content)
            if paragraph.strip()
        ]
        for index, paragraph in enumerate(paragraphs, start=1):
            chunks.append(
                {
                    "source": path.name,
                    "chunk_id": f"{path.stem}-{index}",
                    "text": paragraph,
                }
            )
    return chunks


def create_or_load_collection(
    embedding_model: SentenceTransformer,
    chunks: list[dict[str, Any]],
) -> Any:
    client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))

    if "--rebuild" in sys.argv:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("已删除旧评测索引，准备重建。")
        except Exception:
            pass

    collection = client.get_or_create_collection(name=COLLECTION_NAME)
    if collection.count() == 0:
        embeddings = embedding_model.encode(
            [chunk["text"] for chunk in chunks],
            normalize_embeddings=True,
            show_progress_bar=True,
        )
        collection.upsert(
            ids=[chunk["chunk_id"] for chunk in chunks],
            embeddings=embeddings.tolist(),
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[
                {
                    "source": chunk["source"],
                    "chunk_id": chunk["chunk_id"],
                }
                for chunk in chunks
            ],
        )
        print(f"已写入 {collection.count()} 条评测向量记录。")
    else:
        print(f"已加载本地评测索引，共 {collection.count()} 条记录。")
    return collection


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower()))


def retrieve_vector_only(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    top_k: int,
) -> list[dict[str, Any]]:
    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True,
    )[0]
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {
            "document": document,
            "metadata": metadata,
            "distance": float(distance),
        }
        for document, metadata, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def retrieve_with_rerank(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    top_k: int,
) -> list[dict[str, Any]]:
    candidate_k = min(max(top_k * 3, 5), 15)
    candidates = retrieve_vector_only(
        query=query,
        embedding_model=embedding_model,
        collection=collection,
        top_k=candidate_k,
    )

    query_tokens = tokenize(query)
    for candidate in candidates:
        document_tokens = tokenize(candidate["document"])
        keyword_score = (
            len(query_tokens & document_tokens) / len(query_tokens)
            if query_tokens
            else 0.0
        )
        semantic_score = 1 / (1 + candidate["distance"])
        candidate["rerank_score"] = (
            0.7 * semantic_score + 0.3 * keyword_score
        )

    return sorted(
        candidates,
        key=lambda candidate: candidate["rerank_score"],
        reverse=True,
    )[:top_k]


def source_names(results: list[dict[str, Any]]) -> list[str]:
    return [item["metadata"]["source"] for item in results]


def reciprocal_rank(
    results: list[dict[str, Any]],
    expected_sources: set[str],
) -> float:
    for rank, result in enumerate(results, start=1):
        if result["metadata"]["source"] in expected_sources:
            return 1 / rank
    return 0.0


def case_metrics(
    results: list[dict[str, Any]],
    expected_sources: set[str],
) -> dict[str, float]:
    retrieved_sources = set(source_names(results))
    relevant_count = len(retrieved_sources & expected_sources)
    precision = relevant_count / len(results) if results else 0.0
    recall = relevant_count / len(expected_sources) if expected_sources else 0.0
    return {
        "hit": float(relevant_count > 0),
        "precision": precision,
        "recall": recall,
        "mrr": reciprocal_rank(results, expected_sources),
    }


def evaluate(
    embedding_model: SentenceTransformer,
    collection: Any,
    use_rerank: bool,
    top_k: int = 3,
) -> None:
    mode_name = "向量检索 + Rerank" if use_rerank else "仅向量检索"
    print(f"\n评测模式：{mode_name}，Top-K={top_k}")

    totals = {"hit": 0.0, "precision": 0.0, "recall": 0.0, "mrr": 0.0}
    for index, (query, expected_sources) in enumerate(EVAL_CASES, start=1):
        if use_rerank:
            results = retrieve_with_rerank(
                query=query,
                embedding_model=embedding_model,
                collection=collection,
                top_k=top_k,
            )
        else:
            results = retrieve_vector_only(
                query=query,
                embedding_model=embedding_model,
                collection=collection,
                top_k=top_k,
            )

        metrics = case_metrics(results, expected_sources)
        for key in totals:
            totals[key] += metrics[key]

        print(f"\n[{index}] 问题：{query}")
        print(f"期望来源：{sorted(expected_sources)}")
        print(f"实际来源：{source_names(results)}")
        print(
            "本题指标："
            f"Hit@{top_k}={metrics['hit']:.0f}, "
            f"Precision@{top_k}={metrics['precision']:.3f}, "
            f"Recall@{top_k}={metrics['recall']:.3f}, "
            f"MRR={metrics['mrr']:.3f}"
        )

    count = len(EVAL_CASES)
    print("\n平均指标：")
    print(f"Hit@{top_k}:       {totals['hit'] / count:.3f}")
    print(f"Precision@{top_k}: {totals['precision'] / count:.3f}")
    print(f"Recall@{top_k}:    {totals['recall'] / count:.3f}")
    print(f"MRR:              {totals['mrr'] / count:.3f}")


def main() -> None:
    chunks = load_chunks()
    if not chunks:
        raise RuntimeError(f"知识库为空：{KNOWLEDGE_DIR}")

    print(f"正在加载 Embedding 模型：{EMBEDDING_MODEL_NAME}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    collection = create_or_load_collection(embedding_model, chunks)

    evaluate(
        embedding_model=embedding_model,
        collection=collection,
        use_rerank="--vector-only" not in sys.argv,
    )


if __name__ == "__main__":
    main()

