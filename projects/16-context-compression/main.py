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
        "pip install -r .\\projects\\16-context-compression\\requirements.txt"
    ) from error


load_dotenv()

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
VECTOR_STORE_DIR = Path(__file__).with_name("vector_store")
COLLECTION_NAME = "context_compression"
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
DEFAULT_MAX_CHARS = 1600


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
            print("已删除旧上下文压缩索引，准备重建。")
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


def retrieve(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    top_k: int = 5,
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


def retrieve_many(
    queries: list[str],
    embedding_model: SentenceTransformer,
    collection: Any,
    top_k_each: int = 5,
) -> list[dict[str, Any]]:
    results = []
    for query in queries:
        for rank, result in enumerate(
            retrieve(query, embedding_model, collection, top_k_each),
            start=1,
        ):
            item = result.copy()
            item["query"] = query
            item["rank"] = rank
            results.append(item)
    return results


def deduplicate_results(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    best_by_id: dict[str, dict[str, Any]] = {}
    for result in results:
        item = best_by_id.get(result["id"])
        if item is None or result["distance"] < item["distance"]:
            best_by_id[result["id"]] = result
    return sorted(
        best_by_id.values(),
        key=lambda result: result["distance"],
    )


def parse_max_chars() -> int:
    if "--max-chars" not in sys.argv:
        return DEFAULT_MAX_CHARS
    index = sys.argv.index("--max-chars")
    if index + 1 >= len(sys.argv):
        raise ValueError("--max-chars 后面需要一个正整数")
    value = int(sys.argv[index + 1])
    if value < 200:
        raise ValueError("上下文预算至少设置为 200 个字符")
    return value


def compress_context(
    results: list[dict[str, Any]],
    max_chars: int,
) -> tuple[str, list[str]]:
    parts = []
    references = []
    used_chars = 0

    for index, result in enumerate(results, start=1):
        metadata = result["metadata"]
        reference = f"C{index}"
        separator = "\n---\n" if parts else ""
        header = (
            f"[{reference}] 来源：{metadata['source']}#"
            f"{metadata['chunk_id']}\n"
        )
        remaining = max_chars - used_chars
        if remaining <= len(separator) + len(header) + 20:
            break

        document = result["document"]
        available_text_chars = (
            remaining - len(separator) - len(header) - 10
        )
        if len(document) > available_text_chars:
            document = document[:available_text_chars].rstrip() + "..."

        block = f"{separator}{header}证据：{document}\n"
        parts.append(block)
        references.append(reference)
        used_chars += len(block)

    return "".join(parts), references


def run_demo(
    embedding_model: SentenceTransformer,
    collection: Any,
    max_chars: int,
) -> None:
    queries = [
        "程序重启后如何找回历史信息？",
        "如何保存和恢复对话记忆？",
        "上下文太长时 Agent 应该怎么做？",
    ]
    raw_results = retrieve_many(
        queries=queries,
        embedding_model=embedding_model,
        collection=collection,
    )
    unique_results = deduplicate_results(raw_results)
    context, references = compress_context(unique_results, max_chars)

    print(f"查询数量：{len(queries)}")
    print(f"原始检索结果数量：{len(raw_results)}")
    print(f"去重后结果数量：{len(unique_results)}")
    print(f"上下文预算：{max_chars} 字符")
    print(f"保留引用：{references}")
    print(f"实际上下文长度：{len(context)} 字符")
    print("\n压缩后的上下文：\n")
    print(context or "没有足够预算保留证据。")


def answer_with_context(
    client: OpenAI,
    model: str,
    question: str,
    context: str,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一个使用压缩证据回答问题的 RAG Agent。"
                    "只能依据提供的上下文回答。"
                    "每个重要事实后面引用对应的 [C编号]。"
                    "如果上下文不足，明确说明资料不足。"
                ),
            },
            {
                "role": "user",
                "content": f"问题：{question}\n\n上下文：\n{context}",
            },
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or "没有返回答案。"


def main() -> None:
    chunks = load_chunks()
    if not chunks:
        raise RuntimeError(f"知识库为空：{KNOWLEDGE_DIR}")

    max_chars = parse_max_chars()
    print(f"正在加载 Embedding 模型：{EMBEDDING_MODEL_NAME}")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    collection = create_or_load_collection(embedding_model, chunks)

    if "--demo" in sys.argv:
        run_demo(embedding_model, collection, max_chars)
        return

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")

    client = OpenAI(api_key=api_key, base_url=base_url)
    print("上下文压缩 RAG Agent 已准备完成。输入 exit 退出。")
    while True:
        question = input("\n你：").strip()
        if question.lower() in {"exit", "quit"}:
            print("对话结束。")
            return
        if not question:
            print("请输入问题。")
            continue

        raw_results = retrieve_many(
            queries=[question],
            embedding_model=embedding_model,
            collection=collection,
        )
        unique_results = deduplicate_results(raw_results)
        context, references = compress_context(
            unique_results,
            max_chars,
        )
        print(f"保留引用：{references}")
        print(f"上下文长度：{len(context)}/{max_chars}")
        print(f"\nAgent：{answer_with_context(client, model, question, context)}")


if __name__ == "__main__":
    main()
