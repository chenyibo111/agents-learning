import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")


def tokenize(text: str) -> set[str]:
    """用简单的中英文分词方式生成关键词集合。"""
    return set(re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower()))


def load_documents() -> list[dict[str, str]]:
    documents = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        documents.append(
            {
                "source": path.name,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return documents


DOCUMENTS = load_documents()


def search_knowledge_base(query: str) -> str:
    """从本地知识库中返回与问题最相关的文档片段。"""
    query_tokens = tokenize(query)
    scored_documents = []

    for document in DOCUMENTS:
        document_tokens = tokenize(document["content"])
        score = len(query_tokens & document_tokens)
        scored_documents.append((score, document))

    scored_documents.sort(key=lambda item: item[0], reverse=True)
    matches = [item for item in scored_documents if item[0] > 0][:2]

    if not matches:
        return "知识库中没有找到相关内容。"

    result_parts = []
    for score, document in matches:
        result_parts.append(
            f"来源：{document['source']}\n相关度：{score}\n内容：\n{document['content']}"
        )
    return "\n\n---\n\n".join(result_parts)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "搜索本地 Agent 学习知识库，返回与问题相关的资料片段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的知识问题或关键词",
                    }
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    }
]


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "search_knowledge_base":
        return search_knowledge_base(arguments["query"])
    raise ValueError(f"未知工具: {name}")


def run_agent(client: OpenAI, model: str, user_task: str) -> None:
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是一个学习 RAG 的 Agent。回答 Agent 学习问题前，"
                "必须先搜索本地知识库。只能依据检索到的内容回答；"
                "如果知识库没有足够信息，要明确说明资料不足。"
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

    if not DOCUMENTS:
        raise RuntimeError(f"知识库为空：{KNOWLEDGE_DIR}")

    client = OpenAI(api_key=api_key, base_url=base_url)
    print(f"已加载 {len(DOCUMENTS)} 篇本地文档。")
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

