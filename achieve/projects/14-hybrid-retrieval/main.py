import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import chromadb
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer
except ImportError as error:
    raise RuntimeError(
        "缺少本课依赖，请先执行：\n"
        "pip install -r .\\projects\\14-hybrid-retrieval\\requirements.txt"
    ) from error


KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
VECTOR_STORE_DIR = Path(__file__).with_name("vector_store")
COLLECTION_NAME = "hybrid_retrieval"
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
RRF_K = 60


EVAL_CASES = [
    ("Agent 如何感知环境并采取行动？", {"agent-basics.md"}),
    ("如何让模型使用外部能力？", {"tool-calling.md"}),
    ("程序重新启动后如何找回之前的信息？", {"memory.md"}),
    ("资料不足时 Agent 应该怎么做？", {"grounding.md"}),
    ("工具执行失败后应该如何处理？", {"tool-calling.md"}),
    ("如何保存对话历史？", {"memory.md"}),
    ("tool_call_id 参数执行失败后怎么办？", {"tool-calling.md"})
]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())


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
            print("已删除旧混合检索索引，准备重建。")
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
        print(f"已写入 {collection.count()} 条向量记录。")
    else:
        print(f"已加载本地向量索引，共 {collection.count()} 条记录。")
    return collection


def retrieve_vector(
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
            "id": metadata["chunk_id"],
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


def build_bm25(chunks: list[dict[str, Any]]) -> BM25Okapi:
    tokenized_documents = [tokenize(chunk["text"]) for chunk in chunks]
    return BM25Okapi(tokenized_documents)


def retrieve_bm25(
    query: str,
    bm25: BM25Okapi,
    chunks: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    scores = bm25.get_scores(tokenize(query))
    ranked_indexes = sorted(
        range(len(scores)),
        key=lambda index: scores[index],
        reverse=True,
    )[:top_k]

    results = []
    for index in ranked_indexes:
        chunk = chunks[index]
        results.append(
            {
                "id": chunk["chunk_id"],
                "document": chunk["text"],
                "metadata": {
                    "source": chunk["source"],
                    "chunk_id": chunk["chunk_id"],
                },
                "bm25_score": float(scores[index]),
            }
        )
    return results


def fuse_with_rrf(
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}

    for rank, result in enumerate(vector_results, start=1):
        item = fused.setdefault(result["id"], result.copy())
        item["vector_rank"] = rank
        item["rrf_score"] = item.get("rrf_score", 0.0) + 1 / (RRF_K + rank)

    for rank, result in enumerate(bm25_results, start=1):
        item = fused.setdefault(result["id"], result.copy())
        item["bm25_rank"] = rank
        item["rrf_score"] = item.get("rrf_score", 0.0) + 1 / (RRF_K + rank)

    return sorted(
        fused.values(),
        key=lambda item: item["rrf_score"],
        reverse=True,
    )[:top_k]


def retrieve(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    bm25: BM25Okapi,
    chunks: list[dict[str, Any]],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    candidate_k = min(max(top_k * 3, 5), 15)
    vector_results = retrieve_vector(
        query=query,
        embedding_model=embedding_model,
        collection=collection,
        top_k=candidate_k,
    )
    bm25_results = retrieve_bm25(
        query=query,
        bm25=bm25,
        chunks=chunks,
        top_k=candidate_k,
    )

    if "--vector-only" in sys.argv:
        return vector_results[:top_k]
    if "--bm25-only" in sys.argv:
        return bm25_results[:top_k]
    return fuse_with_rrf(vector_results, bm25_results, top_k)


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
    return {
        "hit": float(relevant_count > 0),
        "precision": relevant_count / len(results) if results else 0.0,
        "recall": (
            relevant_count / len(expected_sources)
            if expected_sources
            else 0.0
        ),
        "mrr": reciprocal_rank(results, expected_sources),
    }


def evaluate(
    embedding_model: SentenceTransformer,
    collection: Any,
    bm25: BM25Okapi,
    chunks: list[dict[str, Any]],
    top_k: int = 3,
) -> None:
    if "--vector-only" in sys.argv:
        mode_name = "仅向量检索"
    elif "--bm25-only" in sys.argv:
        mode_name = "仅 BM25 关键词检索"
    else:
        mode_name = "混合检索（RRF）"

    print(f"\n评测模式：{mode_name}，Top-K={top_k}")
    totals = {"hit": 0.0, "precision": 0.0, "recall": 0.0, "mrr": 0.0}

    for index, (query, expected_sources) in enumerate(EVAL_CASES, start=1):
        results = retrieve(
            query=query,
            embedding_model=embedding_model,
            collection=collection,
            bm25=bm25,
            chunks=chunks,
            top_k=top_k,
        )
        metrics = case_metrics(results, expected_sources)
        for key in totals:
            totals[key] += metrics[key]

        print(f"\n[{index}] 问题：{query}")
        print(f"期望来源：{sorted(expected_sources)}")
        print(f"实际来源：{source_names(results)}")
        for rank, result in enumerate(results, start=1):
            print(
                f"  #{rank} {result['metadata']['source']}#"
                f"{result['metadata']['chunk_id']} "
                f"RRF={result.get('rrf_score', 0.0):.5f} "
                f"向量排名={result.get('vector_rank', '-')} "
                f"BM25排名={result.get('bm25_rank', '-')}"
            )
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
    bm25 = build_bm25(chunks)
    evaluate(
        embedding_model=embedding_model,
        collection=collection,
        bm25=bm25,
        chunks=chunks,
    )


if __name__ == "__main__":
    main()

