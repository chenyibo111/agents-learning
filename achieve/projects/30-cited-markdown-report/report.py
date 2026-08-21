"""Citation mapping and Markdown report writers for lesson 30."""

from __future__ import annotations

import re
from typing import Any, Protocol, Sequence, TypedDict


class EvidenceRecord(TypedDict, total=False):
    claim: str
    source: str
    chunk_id: str
    quote: str
    verified: bool
    note: str


class Citation(TypedDict):
    number: int
    source: str
    chunk_id: str
    quote: str


class ReportWriter(Protocol):
    def write_report(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> str: ...


def _require_verified(evidence: Sequence[EvidenceRecord]) -> None:
    if any(item.get("verified") is not True for item in evidence):
        raise ValueError("报告只能使用 verified=True 的已核验证据")


def build_citations(evidence: Sequence[EvidenceRecord]) -> list[Citation]:
    """Create stable citation numbers by first-seen source and chunk ID."""
    citations: list[Citation] = []
    seen: set[tuple[str, str]] = set()
    for item in evidence:
        source = item.get("source", "")
        chunk_id = item.get("chunk_id", "")
        quote = item.get("quote", "")
        if not source or not chunk_id or not quote:
            raise ValueError("证据缺少 source、chunk_id 或 quote")
        key = (source, chunk_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "number": len(citations) + 1,
                "source": source,
                "chunk_id": chunk_id,
                "quote": quote,
            }
        )
    return citations


def _citation_number(item: EvidenceRecord, citations: Sequence[Citation]) -> int:
    for citation in citations:
        if (
            citation["source"] == item["source"]
            and citation["chunk_id"] == item["chunk_id"]
        ):
            return citation["number"]
    raise ValueError("证据没有对应的引用编号")


def validate_report_citations(
    report: str, citations: Sequence[Citation]
) -> str:
    """Reject empty reports and citation markers outside the generated catalog."""
    cleaned = report.strip()
    if not cleaned:
        raise ValueError("报告不能为空")
    references = {int(value) for value in re.findall(r"(?<!\w)\[(\d+)\]", cleaned)}
    allowed = {citation["number"] for citation in citations}
    unknown = references - allowed
    if unknown:
        numbers = ", ".join(str(number) for number in sorted(unknown))
        raise ValueError(f"报告包含不存在的引用编号：{numbers}")
    if citations and not references:
        raise ValueError("报告有证据时必须至少包含一个引用")
    return cleaned


class DemoReportWriter:
    """Render a deterministic Markdown report without an LLM or network."""

    def write_report(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> str:
        _require_verified(evidence)
        citations = build_citations(evidence)
        lines = [f"# {topic}：研究报告", "", "## 结论", ""]
        if not evidence:
            lines.append("当前没有可用于生成结论的已核验证据。")
        else:
            for item in evidence:
                number = _citation_number(item, citations)
                lines.append(f"{item['claim']}[{number}]")

        lines.extend(["", "## 来源", ""])
        if not citations:
            lines.append("暂无来源。")
        else:
            for citation in citations:
                lines.extend(
                    [
                        f"[{citation['number']}] "
                        f"{citation['source']}#{citation['chunk_id']}",
                        f"> {citation['quote']}",
                        "",
                    ]
                )
        return validate_report_citations("\n".join(lines), citations)


class LLMReportWriter:
    """Ask an injected model to organize only the supplied cited evidence."""

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
                        "你是研究报告编辑。只能使用提供的已核验证据，"
                        "必须使用提供的引用编号，不得创造来源或编号。"
                    ),
                },
                {"role": "user", "content": instruction},
            ],
            temperature=self.temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("模型返回了空报告")
        return content

    def write_report(
        self, topic: str, evidence: Sequence[EvidenceRecord]
    ) -> str:
        _require_verified(evidence)
        citations = build_citations(evidence)
        citation_context = "\n".join(
            f"[{item['number']}] {item['source']}#{item['chunk_id']}\n"
            f"原文：{item['quote']}"
            for item in citations
        )
        evidence_context = "\n".join(
            f"事实：{item['claim']}\n"
            f"来源：{item['source']}#{item['chunk_id']}"
            for item in evidence
        )
        report = self._complete(
            "请生成一份 Markdown 研究报告，包含标题、结论和来源说明；"
            "每个重要结论都使用 [1]、[2] 形式的引用。只能使用以下事实和引用目录。\n"
            f"主题：{topic}\n"
            f"已核验证据：\n{evidence_context or '无'}\n"
            f"引用目录：\n{citation_context or '无'}"
        )
        return validate_report_citations(report, citations)
