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
    from sentence_transformers import SentenceTransformer
except ImportError as error:
    raise RuntimeError(
        "缺少本课依赖，请先执行：\n"
        "pip install -r .\\projects\\11-rag-rerank\\requirements.txt"
    ) from error


load_dotenv()

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
VECTOR_STORE_DIR = Path(__file__).with_name("vector_store")
COLLECTION_NAME = "agent_learning"
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
DEFAULT_TOP_K = 3


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower()))


def load_chunks() -> list[dict[str, Any]]:
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(r"\n\s*\n", content)
            if paragraph.strip()
        ]

        for chunk_index, paragraph in enumerate(paragraphs, start=1):
            chunks.append(
                {
                    "source": path.name,
                    "chunk_id": f"{path.stem}-{chunk_index}",
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
            print("已删除旧索引，准备重建。")
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


def retrieve_candidates(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    candidate_k: int,
) -> list[dict[str, Any]]:
    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True,
    )[0]
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=candidate_k,
        include=["documents", "metadatas", "distances"],
    )

    candidates = []
    for document, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        candidates.append(
            {
                "document": document,
                "metadata": metadata,
                "distance": float(distance),
            }
        )
    return candidates


def lexical_score(query: str, document: str) -> float:
    query_tokens = tokenize(query)
    document_tokens = tokenize(document)
    if not query_tokens:
        return 0.0
    return len(query_tokens & document_tokens) / len(query_tokens)


def rerank(query: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    for candidate in candidates:
        semantic_score = 1 / (1 + candidate["distance"])
        keyword_score = lexical_score(query, candidate["document"])
        candidate["semantic_score"] = semantic_score
        candidate["keyword_score"] = keyword_score
        candidate["rerank_score"] = 0.7 * semantic_score + 0.3 * keyword_score

    return sorted(
        candidates,
        key=lambda candidate: candidate["rerank_score"],
        reverse=True,
    )[:top_k]


def search_knowledge_base(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    top_k = max(1, min(int(top_k), 5))
    candidate_k = min(max(top_k * 3, 5), 15)
    candidates = retrieve_candidates(
        query=query,
        embedding_model=embedding_model,
        collection=collection,
        candidate_k=candidate_k,
    )
    final_matches = rerank(query, candidates, top_k)

    result_parts = []
    for candidate in final_matches:
        metadata = candidate["metadata"]
        result_parts.append(
            f"来源：{metadata['source']}#{metadata['chunk_id']}\n"
            f"重排分数：{candidate['rerank_score']:.3f}\n"
            f"语义分数：{candidate['semantic_score']:.3f}\n"
            f"关键词分数：{candidate['keyword_score']:.3f}\n"
            f"片段：\n{candidate['document']}"
        )

    if not result_parts:
        return "知识库中没有找到相关内容。"
    return "\n\n---\n\n".join(result_parts)


EVAL_CASES = [
    ("如何让模型使用外部能力？", "tool-calling.md"),
    ("程序重新启动后如何找回之前的信息？", "memory.md"),
    ("Agent 如何感知环境并采取行动？", "agent-basics.md"),
]


def evaluate_retrieval(
    embedding_model: SentenceTransformer,
    collection: Any,
) -> None:
    print("开始检索评测：")
    passed = 0
    for query, expected_source in EVAL_CASES:
        candidates = retrieve_candidates(
            query=query,
            embedding_model=embedding_model,
            collection=collection,
            candidate_k=5,
        )
        results = rerank(query, candidates, top_k=3)
        sources = [item["metadata"]["source"] for item in results]
        success = expected_source in sources
        passed += int(success)
        print(f"\n问题：{query}")
        print(f"期望来源：{expected_source}")
        print(f"实际来源：{sources}")
        print("结果：通过" if success else "结果：未通过")

    print(f"\n评测结果：{passed}/{len(EVAL_CASES)} 个问题召回了期望来源。")


def run_agent(
    client: OpenAI,
    model: str,
    user_task: str,
    embedding_model: SentenceTransformer,
    collection: Any,
) -> None:
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是一个带重排序能力的 RAG Agent。回答问题前必须搜索知识库。"
                "只能依据检索结果回答，并在答案末尾列出引用，格式为 [来源#chunk_id]。"
                "如果资料不足，要明确说明。"
            ),
        },
        {"role": "user", "content": user_task},
    ]

    for step in range(3):
        print(f"\n--- agent step {step + 1} ---")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "search_knowledge_base",
                        "description": "检索并重排序本地 Agent 学习知识库。",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "top_k": {"type": "integer"},
                            },
                            "required": ["query"],
                            "additionalProperties": False,
                        },
                    },
                }
            ],
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(f"Agent：{message.content or '没有返回文本。'}")
            return

        for tool_call in message.tool_calls:
            arguments = json.loads(tool_call.function.arguments)
            print(f"调用工具: search_knowledge_base({arguments})")
            result = search_knowledge_base(
                query=arguments["query"],
                embedding_model=embedding_model,
                collection=collection,
                top_k=arguments.get("top_k", DEFAULT_TOP_K),
            )
            print(f"检索结果：\n{result}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    print("Agent：超过最大步数，停止本次任务。")


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None

    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")

    chunks = load_chunks()
    if not chunks:
        raise RuntimeError(f"知识库为空：{KNOWLEDGE_DIR}")

    print(f"正在加载 Embedding 模型：{EMBEDDING_MODEL_NAME}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    collection = create_or_load_collection(embedding_model, chunks)

    if "--eval" in sys.argv:
        evaluate_retrieval(embedding_model, collection)
        return

    client = OpenAI(api_key=api_key, base_url=base_url)
    print("RAG 重排序系统已准备完成。输入 exit 退出。")
    while True:
        user_task = input("\n你：").strip()
        if user_task.lower() in {"exit", "quit"}:
            print("对话结束。")
            return
        if not user_task:
            print("请输入问题。")
            continue
        run_agent(client, model, user_task, embedding_model, collection)


if __name__ == "__main__":
    main()

