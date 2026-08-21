import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

try:
    import chromadb
    from rank_bm25 import BM25Okapi
    from sentence_transformers import SentenceTransformer
except ImportError as error:
    raise RuntimeError(
        "缺少本课依赖，请先执行：\n"
        "pip install -r .\\projects\\15-query-rewriting\\requirements.txt"
    ) from error


load_dotenv()

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
VECTOR_STORE_DIR = Path(__file__).with_name("vector_store")
COLLECTION_NAME = "query_rewriting"
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
RRF_K = 60


EVAL_CASES = [
    (
        "程序重启后如何找回信息？",
        {"memory.md"},
        [
            "程序重新启动后如何恢复历史消息？",
            "Agent 如何实现持久化记忆？",
        ],
    ),
    (
        "模型怎么使用外部能力？",
        {"tool-calling.md"},
        [
            "LLM 如何发起函数调用？",
            "Python 如何执行模型请求的工具？",
        ],
    ),
    (
        "资料不够时应该怎么办？",
        {"grounding.md"},
        [
            "RAG 找不到充分证据时如何回答？",
            "Agent 什么时候应该拒答？",
        ],
    ),
    (
        "Agent 是怎样完成任务的？",
        {"agent-basics.md"},
        [
            "Agent 如何感知环境并采取行动？",
            "LLM 和 Python 程序在 Agent 中分别负责什么？",
        ],
    ),
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
                    "id": f"{path.stem}-{index}",
                    "source": path.name,
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
            print("已删除旧查询改写索引，准备重建。")
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
            ids=[chunk["id"] for chunk in chunks],
            embeddings=embeddings.tolist(),
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[
                {
                    "source": chunk["source"],
                    "chunk_id": chunk["id"],
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
    return [
        {
            "id": chunks[index]["id"],
            "document": chunks[index]["text"],
            "metadata": {
                "source": chunks[index]["source"],
                "chunk_id": chunks[index]["id"],
            },
            "bm25_score": float(scores[index]),
        }
        for index in ranked_indexes
    ]


def rrf_fuse(
    ranked_lists: list[list[dict[str, Any]]],
    top_k: int,
) -> list[dict[str, Any]]:
    fused: dict[str, dict[str, Any]] = {}
    for list_index, ranked_list in enumerate(ranked_lists, start=1):
        for rank, result in enumerate(ranked_list, start=1):
            item = fused.setdefault(result["id"], result.copy())
            item["rrf_score"] = item.get("rrf_score", 0.0) + 1 / (
                RRF_K + rank
            )
            item.setdefault("appearances", []).append(
                f"list-{list_index}#{rank}"
            )

    return sorted(
        fused.values(),
        key=lambda item: item["rrf_score"],
        reverse=True,
    )[:top_k]


def hybrid_for_query(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    bm25: BM25Okapi,
    chunks: list[dict[str, Any]],
    top_k: int,
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
    return rrf_fuse([vector_results, bm25_results], top_k)


def multi_query_retrieve(
    queries: list[str],
    embedding_model: SentenceTransformer,
    collection: Any,
    bm25: BM25Okapi,
    chunks: list[dict[str, Any]],
    top_k: int = 3,
) -> list[dict[str, Any]]:
    query_result_lists = [
        hybrid_for_query(
            query=query,
            embedding_model=embedding_model,
            collection=collection,
            bm25=bm25,
            chunks=chunks,
            top_k=top_k * 3,
        )
        for query in queries
    ]
    return rrf_fuse(query_result_lists, top_k)


def parse_query_variants(content: str, original: str) -> list[str]:
    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            variants = [str(item).strip() for item in parsed if str(item).strip()]
            return [original, *variants[:3]]
    except json.JSONDecodeError:
        pass

    lines = [
        re.sub(r"^[-*\d.、)]+\s*", "", line).strip()
        for line in cleaned.splitlines()
        if line.strip()
    ]
    return [original, *[line for line in lines[:3] if line != original]]


def rewrite_query(client: OpenAI, model: str, original: str) -> list[str]:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是检索查询改写器。将用户问题改写成最多 3 个适合知识库搜索的中文查询。"
                    "保留专业名词，覆盖同义表达和可能的技术术语。"
                    "只返回 JSON 字符串数组，不要解释。"
                ),
            },
            {"role": "user", "content": original},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or "[]"
    return parse_query_variants(content, original)


def answer_with_evidence(
    client: OpenAI,
    model: str,
    question: str,
    queries: list[str],
    results: list[dict[str, Any]],
) -> str:
    evidence = []
    for index, result in enumerate(results, start=1):
        metadata = result["metadata"]
        evidence.append(
            f"[M{index}] 来源：{metadata['source']}#{metadata['chunk_id']}\n"
            f"证据：{result['document']}"
        )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个基于证据回答问题的 RAG Agent。"
                    "只能使用提供的证据回答，不要补充证据之外的事实。"
                    "每个重要结论后面引用对应的 [M编号]。"
                    "证据不足时请明确说明。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"原始问题：{question}\n"
                    f"搜索表达：{queries}\n\n"
                    f"检索证据：\n{chr(10).join(evidence)}"
                ),
            },
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or "没有返回答案。"


def evaluate(
    embedding_model: SentenceTransformer,
    collection: Any,
    bm25: BM25Okapi,
    chunks: list[dict[str, Any]],
) -> None:
    use_rewrite = "--no-rewrite" not in sys.argv
    mode_name = "多查询融合" if use_rewrite else "单查询"
    print(f"\n评测模式：{mode_name}")
    totals = {"hit": 0.0, "precision": 0.0, "recall": 0.0, "mrr": 0.0}

    for index, (query, expected_sources, variants) in enumerate(
        EVAL_CASES,
        start=1,
    ):
        queries = [query, *variants] if use_rewrite else [query]
        results = multi_query_retrieve(
            queries=queries,
            embedding_model=embedding_model,
            collection=collection,
            bm25=bm25,
            chunks=chunks,
        )
        sources = [item["metadata"]["source"] for item in results]
        relevant = len(set(sources) & expected_sources)
        hit = float(relevant > 0)
        precision = relevant / len(results) if results else 0.0
        recall = relevant / len(expected_sources)
        mrr = next(
            (
                1 / rank
                for rank, source in enumerate(sources, start=1)
                if source in expected_sources
            ),
            0.0,
        )
        metrics = {
            "hit": hit,
            "precision": precision,
            "recall": recall,
            "mrr": mrr,
        }
        for key in totals:
            totals[key] += metrics[key]
        print(f"\n[{index}] 问题：{query}")
        print(f"使用查询：{queries}")
        print(f"期望来源：{sorted(expected_sources)}")
        print(f"实际来源：{sources}")
        print(
            "本题指标："
            f"Hit@3={hit:.0f}, Precision@3={precision:.3f}, "
            f"Recall@3={recall:.3f}, MRR={mrr:.3f}"
        )

    count = len(EVAL_CASES)
    print("\n平均指标：")
    print(f"Hit@3:       {totals['hit'] / count:.3f}")
    print(f"Precision@3: {totals['precision'] / count:.3f}")
    print(f"Recall@3:    {totals['recall'] / count:.3f}")
    print(f"MRR:         {totals['mrr'] / count:.3f}")


def main() -> None:
    chunks = load_chunks()
    if not chunks:
        raise RuntimeError(f"知识库为空：{KNOWLEDGE_DIR}")

    print(f"正在加载 Embedding 模型：{EMBEDDING_MODEL_NAME}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    collection = create_or_load_collection(embedding_model, chunks)
    bm25 = BM25Okapi([tokenize(chunk["text"]) for chunk in chunks])

    if "--eval" in sys.argv:
        evaluate(embedding_model, collection, bm25, chunks)
        return

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")

    client = OpenAI(api_key=api_key, base_url=base_url)
    print("查询改写 RAG Agent 已准备完成。输入 exit 退出。")
    while True:
        question = input("\n你：").strip()
        if question.lower() in {"exit", "quit"}:
            print("对话结束。")
            return
        if not question:
            print("请输入问题。")
            continue

        queries = [question]
        if "--no-rewrite" not in sys.argv:
            try:
                queries = rewrite_query(client, model, question)
            except Exception as error:
                print(f"查询改写失败，将使用原始问题：{error}")

        print(f"搜索表达：{queries}")
        results = multi_query_retrieve(
            queries=queries,
            embedding_model=embedding_model,
            collection=collection,
            bm25=bm25,
            chunks=chunks,
        )
        print("\n检索结果：")
        for index, result in enumerate(results, start=1):
            metadata = result["metadata"]
            print(
                f"\n[M{index}] {metadata['source']}#"
                f"{metadata['chunk_id']} "
                f"RRF={result.get('rrf_score', 0.0):.5f}\n"
                f"{result['document']}"
            )

        print("\nAgent：")
        print(answer_with_evidence(client, model, question, queries, results))


if __name__ == "__main__":
    main()

