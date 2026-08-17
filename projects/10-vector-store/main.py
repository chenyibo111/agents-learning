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
        "pip install -r .\\projects\\10-vector-store\\requirements.txt"
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
        print(f"正在编码 {len(chunks)} 个文档片段。")
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


def search_knowledge_base(
    query: str,
    embedding_model: SentenceTransformer,
    collection: Any,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    top_k = max(1, min(int(top_k), 5))
    query_embedding = embedding_model.encode(
        [query],
        normalize_embeddings=True,
    )[0]

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    result_parts = []
    for document, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        result_parts.append(
            f"来源：{metadata['source']}#{metadata['chunk_id']}\n"
            f"向量距离：{float(distance):.3f}\n"
            f"片段：\n{document}"
        )

    if not result_parts:
        return "向量数据库中没有找到相关内容。"
    return "\n\n---\n\n".join(result_parts)


def build_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge_base",
                "description": "查询本地 Chroma 向量数据库中的 Agent 学习资料。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜索的知识问题或关键词",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "最多返回多少个相关片段，范围为 1 到 5",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
        }
    ]


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
                "你是一个使用向量数据库的 RAG Agent。回答问题前必须搜索知识库。"
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
            tools=build_tools(),
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(f"Agent：{message.content or '没有返回文本。'}")
            return

        print(f"本轮工具调用数量：{len(message.tool_calls)}")
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
    client = OpenAI(api_key=api_key, base_url=base_url)

    print("向量数据库已准备完成。输入 exit 退出。")
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

