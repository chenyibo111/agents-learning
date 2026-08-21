"""Offline and OpenAI-compatible runtimes for the research workflow."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, Sequence

from state import EvidenceRecord, SearchResult


class ResearchRuntime(Protocol):
    """Model-side behavior shared by DemoRuntime and LLMRuntime."""

    def plan(self, topic: str) -> list[str]: ...

    def extract_evidence(
        self, topic: str, chunks: Sequence[SearchResult]
    ) -> list[EvidenceRecord]: ...

    def verify_evidence(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> list[EvidenceRecord]: ...


class DemoRuntime:
    """Deterministic runtime that does not use credentials or a network."""

    def plan(self, topic: str) -> list[str]:
        return [
            f"定义“{topic}”的研究问题",
            "检索相关资料并保留来源标识",
            "提取事实并核验事实与资料是否一致",
        ]

    def extract_evidence(
        self, topic: str, chunks: Sequence[SearchResult]
    ) -> list[EvidenceRecord]:
        return [
            {
                "claim": chunk["text"],
                "source": chunk["source"],
                "chunk_id": chunk["chunk_id"],
                "quote": chunk["text"],
            }
            for chunk in chunks
        ]

    def verify_evidence(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> list[EvidenceRecord]:
        return [
            {
                **item,
                "verified": True,
                "note": "Demo 使用检索片段原文作为证据，已通过确定性校验。",
            }
            for item in evidence
        ]


class LLMRuntime:
    """Use an injected OpenAI-compatible client with strict JSON validation."""

    def __init__(self, client: Any, model_id: str, temperature: float = 0.2):
        self.client = client
        self.model_id = model_id
        self.temperature = temperature

    def _complete(self, instruction: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是研究助手。只根据当前任务作答；需要 JSON 时只返回合法 JSON，"
                        "不要输出 Markdown 代码围栏。"
                    ),
                },
                {"role": "user", "content": instruction},
            ],
            temperature=self.temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("模型返回了空内容")
        return content

    @staticmethod
    def _parse_json(content: str, expected_type: type) -> Any:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(lines[1:-1]).strip()
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as error:
            raise ValueError("模型没有返回合法 JSON") from error
        if not isinstance(value, expected_type):
            raise ValueError(f"模型 JSON 类型错误，期望 {expected_type.__name__}")
        return value

    def plan(self, topic: str) -> list[str]:
        result = self._parse_json(
            self._complete(
                f"请为以下研究主题设计 3 到 5 个步骤，只返回字符串数组：{topic}"
            ),
            list,
        )
        if not all(isinstance(item, str) and item.strip() for item in result):
            raise ValueError("研究计划必须是非空字符串数组")
        return result

    def extract_evidence(
        self, topic: str, chunks: Sequence[SearchResult]
    ) -> list[EvidenceRecord]:
        result = self._parse_json(
            self._complete(
                "请严格根据检索片段提取可验证事实，只返回 JSON 数组；"
                "每项包含 claim、source、chunk_id、quote 字段。不得创造检索片段中不存在的来源。\n"
                f"主题：{topic}\n检索片段：{json.dumps(list(chunks), ensure_ascii=False)}"
            ),
            list,
        )
        records = [self._evidence_record(item) for item in result]
        allowed_sources = {
            (chunk["source"], chunk["chunk_id"]) for chunk in chunks
        }
        for record in records:
            source_key = (record["source"], record["chunk_id"])
            if source_key not in allowed_sources:
                raise ValueError(
                    f"证据来源 {record['source']}#{record['chunk_id']} 不在检索结果中"
                )
        return records

    def verify_evidence(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> list[EvidenceRecord]:
        result = self._parse_json(
            self._complete(
                "请核验以下事实并返回 JSON 数组；每项保留 claim、source、chunk_id、quote，"
                "并增加 verified 布尔值和 note 字段。\n"
                f"主题：{topic}\n事实：{json.dumps(list(evidence), ensure_ascii=False)}"
            ),
            list,
        )
        records = [self._evidence_record(item, require_verified=True) for item in result]
        allowed_sources = {
            (item["source"], item["chunk_id"]) for item in evidence
        }
        for record in records:
            source_key = (record["source"], record["chunk_id"])
            if source_key not in allowed_sources:
                raise ValueError(
                    f"核验来源 {record['source']}#{record['chunk_id']} 不在待核验证据中"
                )
        return records

    @staticmethod
    def _evidence_record(
        value: Any, require_verified: bool = False
    ) -> EvidenceRecord:
        if not isinstance(value, dict):
            raise ValueError("证据记录必须是 JSON 对象")
        required = ("claim", "source", "chunk_id", "quote")
        if not all(isinstance(value.get(key), str) and value[key].strip() for key in required):
            raise ValueError("证据记录缺少 claim、source、chunk_id 或 quote")
        record: EvidenceRecord = {
            key: value[key] for key in required
        }
        if require_verified:
            if not isinstance(value.get("verified"), bool):
                raise ValueError("核验结果缺少 verified 布尔值")
            record["verified"] = value["verified"]
            record["note"] = str(value.get("note", ""))
        return record


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


def build_llm_runtime_from_env() -> LLMRuntime:
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

    return LLMRuntime(
        client=OpenAI(api_key=api_key, base_url=base_url),
        model_id=model_id,
    )
