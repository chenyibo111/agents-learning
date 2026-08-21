import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


try:
    from sentence_transformers import SentenceTransformer
except ImportError as error:
    raise RuntimeError(
        "缺少 sentence-transformers，请先执行：\n"
        "pip install -r .\\projects\\09-embedding-retrieval\\requirements.txt"
    ) from error


load_dotenv()

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
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


def search_knowledge_base(
    query: str,
    model: SentenceTransformer,
    chunks: list[dict[str, Any]],
    chunk_embeddings: Any,
    top_k: int = DEFAULT_TOP_K,
) -> str:
    top_k = max(1, min(int(top_k), 5))
    query_embedding = model.encode(
        [query],
        normalize_embeddings=True,
    )[0]

    # 归一化后，向量点积就是余弦相似度。
    scores = chunk_embeddings @ query_embedding
    ranked_indices = sorted(
        range(len(chunks)),
        key=lambda index: float(scores[index]),
        reverse=True,
    )
    matches = [
        (float(scores[index]), chunks[index])
        for index in ranked_indices[:top_k]
    ]

    result_parts = []
    for score, chunk in matches:
        result_parts.append(
            f"来源：{chunk['source']}#{chunk['chunk_id']}\n"
            f"语义相似度：{score:.3f}\n"
            f"片段：\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(result_parts)


def build_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "search_knowledge_base",
                "description": "使用神经网络 Embedding 搜索本地 Agent 学习知识库。",
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
    chunks: list[dict[str, Any]],
    chunk_embeddings: Any,
) -> None:
    tools = build_tools()
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是一个学习 Embedding RAG 的 Agent。回答问题前必须搜索知识库。"
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
            tools=tools,
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
                model=embedding_model,
                chunks=chunks,
                chunk_embeddings=chunk_embeddings,
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
    print(f"正在编码 {len(chunks)} 个文档片段。")
    chunk_embeddings = embedding_model.encode(
        [chunk["text"] for chunk in chunks],
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    client = OpenAI(api_key=api_key, base_url=base_url)
    print("Embedding 检索器已准备完成。输入 exit 退出。")

    while True:
        user_task = input("\n你：").strip()
        if user_task.lower() in {"exit", "quit"}:
            print("对话结束。")
            return
        if not user_task:
            print("请输入问题。")
            continue
        run_agent(
            client,
            model,
            user_task,
            embedding_model,
            chunks,
            chunk_embeddings,
        )


if __name__ == "__main__":
    main()

