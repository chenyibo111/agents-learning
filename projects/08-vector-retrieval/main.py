import json
import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
DEFAULT_TOP_K = 3


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

        for chunk_index, paragraph in enumerate(paragraphs, start=1):
            chunks.append(
                {
                    "source": path.name,
                    "chunk_id": f"{path.stem}-{chunk_index}",
                    "text": paragraph,
                    "tokens": tokenize(paragraph),
                }
            )
    return chunks


def build_idf(chunks: list[dict[str, Any]]) -> dict[str, float]:
    document_frequency = Counter()
    for chunk in chunks:
        document_frequency.update(set(chunk["tokens"]))

    document_count = len(chunks)
    return {
        token: math.log((document_count + 1) / (frequency + 1)) + 1
        for token, frequency in document_frequency.items()
    }


def vectorize(
    tokens: list[str],
    idf: dict[str, float],
) -> dict[str, float]:
    counts = Counter(tokens)
    total = len(tokens) or 1
    return {
        token: (count / total) * idf.get(token, 0.0)
        for token, count in counts.items()
        if token in idf
    }


def cosine_similarity(
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    common_tokens = set(left) & set(right)
    dot_product = sum(left[token] * right[token] for token in common_tokens)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


CHUNKS = load_chunks()
IDF = build_idf(CHUNKS)
for chunk in CHUNKS:
    chunk["vector"] = vectorize(chunk["tokens"], IDF)


def search_knowledge_base(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    query_vector = vectorize(tokenize(query), IDF)
    if not query_vector:
        return "搜索问题中没有可识别的关键词。"

    top_k = max(1, min(int(top_k), 5))
    scored_chunks = [
        (cosine_similarity(query_vector, chunk["vector"]), chunk)
        for chunk in CHUNKS
    ]
    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    matches = [item for item in scored_chunks if item[0] > 0][:top_k]

    if not matches:
        return "知识库中没有找到相关内容。"

    result_parts = []
    for score, chunk in matches:
        result_parts.append(
            f"来源：{chunk['source']}#{chunk['chunk_id']}\n"
            f"余弦相似度：{score:.3f}\n"
            f"片段：\n{chunk['text']}"
        )
    return "\n\n---\n\n".join(result_parts)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "使用向量相似度搜索本地 Agent 学习知识库。",
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


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "search_knowledge_base":
        return search_knowledge_base(
            query=arguments["query"],
            top_k=arguments.get("top_k", DEFAULT_TOP_K),
        )
    raise ValueError(f"未知工具: {name}")


def run_agent(client: OpenAI, model: str, user_task: str) -> None:
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是一个学习向量检索的 Agent。回答问题前必须先搜索知识库。"
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
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(f"Agent：{message.content or '没有返回文本。'}")
            return

        print(f"本轮工具调用数量：{len(message.tool_calls)}")
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"调用工具: {name}({arguments})")
            result = call_tool(name, arguments)
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
    if not CHUNKS:
        raise RuntimeError(f"知识库为空：{KNOWLEDGE_DIR}")

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f"已加载 {len(CHUNKS)} 个文档片段。")
    print("输入 exit 退出。")

    while True:
        user_task = input("\n你：").strip()
        if user_task.lower() in {"exit", "quit"}:
            print("对话结束。")
            return
        if not user_task:
            print("请输入问题。")
            continue
        run_agent(client, model, user_task)


if __name__ == "__main__":
    main()

