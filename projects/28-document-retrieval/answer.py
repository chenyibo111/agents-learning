"""Demo and OpenAI-compatible answerers for retrieved context."""

from __future__ import annotations

import json
import os
from typing import Any, Sequence

from retrievers import SearchResult


def format_context(results: Sequence[SearchResult]) -> str:
    return "\n\n".join(
        f"[{index}] {item['source']}#{item['chunk_id']}\n{item['text']}"
        for index, item in enumerate(results, start=1)
    )


class DemoAnswerer:
    def answer(self, query: str, results: Sequence[SearchResult]) -> str:
        if not results:
            return "没有检索到相关资料，暂时无法回答。"
        lines = [f"问题：{query}", "", "根据检索到的资料："]
        lines.extend(
            f"- {item['text']} [{index}]"
            for index, item in enumerate(results, start=1)
        )
        lines.extend(
            [
                "",
                "来源：",
                *[
                    f"[{index}] {item['source']}#{item['chunk_id']}"
                    for index, item in enumerate(results, start=1)
                ],
            ]
        )
        return "\n".join(lines)


class LLMAnswerer:
    def __init__(self, client: Any, model_id: str, temperature: float = 0.2):
        self.client = client
        self.model_id = model_id
        self.temperature = temperature

    def answer(self, query: str, results: Sequence[SearchResult]) -> str:
        if not results:
            return "没有检索到相关资料，无法基于知识库回答。"
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个基于本地知识库回答问题的助手。只能依据给定资料回答，"
                        "不要补充资料中没有的事实，并在相关句子后使用 [1]、[2] 格式引用。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"问题：{query}\n\n资料：\n{format_context(results)}\n\n"
                        "如果资料不足，请明确说明。"
                    ),
                },
            ],
            temperature=self.temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("模型返回了空回答")
        return content


def validate_llm_config(
    api_key: str | None,
    model_id: str | None,
    base_url: str | None,
) -> None:
    if not api_key or api_key.startswith(("replace-", "你的")):
        raise ValueError("OPENAI_API_KEY 未配置或仍是占位符")
    if not model_id:
        raise ValueError("OPENAI_MODEL 未配置")
    if base_url is not None and not base_url.startswith(("http://", "https://")):
        raise ValueError("OPENAI_BASE_URL 必须是 http:// 或 https:// 地址")


def build_llm_answerer_from_env() -> LLMAnswerer:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("请先安装 python-dotenv") from error

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    model_id = os.getenv("OPENAI_MODEL", "")
    base_url = os.getenv("OPENAI_BASE_URL")
    validate_llm_config(api_key, model_id, base_url)

    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError("请先安装 openai") from error

    return LLMAnswerer(
        client=OpenAI(api_key=api_key, base_url=base_url),
        model_id=model_id,
    )
