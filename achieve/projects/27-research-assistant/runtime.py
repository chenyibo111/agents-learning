"""Offline and OpenAI-compatible runtimes for the research workflow."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, Sequence

from state import EvidenceRecord, SourceRecord


class ResearchRuntime(Protocol):
    """The contract shared by the deterministic and LLM implementations."""

    def plan(self, topic: str) -> list[str]: ...

    def collect_sources(
        self, topic: str, plan: Sequence[str]
    ) -> list[SourceRecord]: ...

    def extract_evidence(
        self, topic: str, sources: Sequence[SourceRecord]
    ) -> list[EvidenceRecord]: ...

    def verify_evidence(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> list[EvidenceRecord]: ...

    def write_report(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> str: ...


class DemoRuntime:
    """Return deterministic records without reading credentials or using a network."""

    def plan(self, topic: str) -> list[str]:
        return [
            f"定义“{topic}”的研究问题",
            "比较主要方案和适用边界",
            "整理风险、证据和待核验项",
        ]

    def collect_sources(
        self, topic: str, plan: Sequence[str]
    ) -> list[SourceRecord]:
        return [
            {
                "title": "Agent 架构设计笔记",
                "url": "demo://agent-architecture",
                "summary": f"围绕“{topic}”整理状态、工具和工作流边界。",
            },
            {
                "title": "可靠工作流实验记录",
                "url": "demo://reliable-workflow",
                "summary": "记录重试、人工确认、持久化和失败恢复的设计要点。",
            },
        ]

    def extract_evidence(
        self, topic: str, sources: Sequence[SourceRecord]
    ) -> list[EvidenceRecord]:
        return [
            {
                "claim": "研究流程应把状态、工具和模型调用边界分开。",
                "source_url": sources[0]["url"],
            },
            {
                "claim": "包含外部副作用的节点需要幂等、重试和人工确认设计。",
                "source_url": sources[1]["url"],
            },
        ]

    def verify_evidence(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> list[EvidenceRecord]:
        return [
            {
                **item,
                "verified": True,
                "note": "Demo 资料已通过确定性校验，真实系统仍需独立来源复核。",
            }
            for item in evidence
        ]

    def write_report(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> str:
        lines = [f"# {topic}：研究报告", "", "## 结论", ""]
        lines.append("本 Demo 展示了从研究计划到证据核验的完整流程。")
        lines.extend(
            [
                "",
                "## 关键证据",
                *[
                    f"- {item['claim']} [{index}]"
                    for index, item in enumerate(evidence, start=1)
                ],
                "",
                "## 来源",
                *[
                    f"[{index}] {item['source_url']}"
                    for index, item in enumerate(evidence, start=1)
                ],
            ]
        )
        return "\n".join(lines)


class LLMRuntime:
    """Use an injected OpenAI-compatible client for real model execution."""

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

    def collect_sources(
        self, topic: str, plan: Sequence[str]
    ) -> list[SourceRecord]:
        result = self._parse_json(
            self._complete(
                "请为研究主题列出候选资料，只返回 JSON 数组；"
                '每项包含 title、url、summary 字段。\n'
                f"主题：{topic}\n计划：{json.dumps(list(plan), ensure_ascii=False)}"
            ),
            list,
        )
        return [self._source_record(item) for item in result]

    def extract_evidence(
        self, topic: str, sources: Sequence[SourceRecord]
    ) -> list[EvidenceRecord]:
        result = self._parse_json(
            self._complete(
                "请从候选资料中提取可验证事实，只返回 JSON 数组；"
                '每项包含 claim、source_url 字段。\n'
                f"主题：{topic}\n资料：{json.dumps(list(sources), ensure_ascii=False)}"
            ),
            list,
        )
        return [self._evidence_record(item) for item in result]

    def verify_evidence(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> list[EvidenceRecord]:
        result = self._parse_json(
            self._complete(
                "请核验以下事实并返回 JSON 数组；每项保留 claim、source_url，"
                "并增加 verified 布尔值和 note 字段。\n"
                f"主题：{topic}\n事实：{json.dumps(list(evidence), ensure_ascii=False)}"
            ),
            list,
        )
        return [self._evidence_record(item, require_verified=True) for item in result]

    def write_report(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> str:
        return self._complete(
            "请根据已核验事实生成 Markdown 研究报告，保留 [1]、[2] 这样的来源引用，"
            "并明确不确定性。\n"
            f"主题：{topic}\n事实：{json.dumps(list(evidence), ensure_ascii=False)}"
        )

    @staticmethod
    def _source_record(value: Any) -> SourceRecord:
        if not isinstance(value, dict):
            raise ValueError("资料记录必须是 JSON 对象")
        required = ("title", "url", "summary")
        if not all(isinstance(value.get(key), str) for key in required):
            raise ValueError("资料记录缺少 title、url 或 summary")
        return {key: value[key] for key in required}

    @staticmethod
    def _evidence_record(
        value: Any, require_verified: bool = False
    ) -> EvidenceRecord:
        if not isinstance(value, dict):
            raise ValueError("证据记录必须是 JSON 对象")
        required = ("claim", "source_url")
        if not all(isinstance(value.get(key), str) for key in required):
            raise ValueError("证据记录缺少 claim 或 source_url")
        record: EvidenceRecord = {
            "claim": value["claim"],
            "source_url": value["source_url"],
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
