"""Compile candidate information into a safe, budgeted model context."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .contracts import ContextBuildResult, ContextItem, DroppedContext, SelectedContext
from .filters import PromptInjectionDetector, SensitiveDataFilter
from .tokenizer import TokenCounter


class ContextBudgetError(ValueError):
    """Raised when required context cannot fit within the input budget."""


class ContextBuilder:
    """Apply trust boundaries and deterministic priority selection."""

    def __init__(
        self,
        *,
        token_counter: TokenCounter | None = None,
        sensitive_filter: SensitiveDataFilter | None = None,
        injection_detector: PromptInjectionDetector | None = None,
    ):
        self.token_counter = token_counter or TokenCounter()
        self.sensitive_filter = sensitive_filter or SensitiveDataFilter()
        self.injection_detector = injection_detector or PromptInjectionDetector()

    def build(
        self,
        items: Iterable[ContextItem],
        *,
        token_budget: int,
    ) -> ContextBuildResult:
        if token_budget < 1:
            raise ValueError("token_budget 必须大于 0")

        prepared = []
        redacted_fields: list[str] = []
        injection_warnings: list[str] = []
        for item in items:
            redaction = self.sensitive_filter.redact(item.text)
            safe_metadata, metadata_fields = self.sensitive_filter.redact_metadata(
                item.metadata
            )
            warnings = self.injection_detector.detect(item.text)
            safe_text = redaction.text
            if warnings:
                safe_text = "[UNTRUSTED_EXTERNAL_DATA]\n" + safe_text
                injection_warnings.extend(
                    f"{item.id}:{warning}" for warning in warnings
                )
            redacted_fields.extend(redaction.fields)
            redacted_fields.extend(metadata_fields)
            safe_item = replace(item, text=safe_text, metadata=safe_metadata)
            prepared.append(
                (
                    safe_item,
                    self.token_counter.count(safe_text),
                )
            )

        selected: list[SelectedContext] = []
        dropped: list[DroppedContext] = []
        used = 0

        required = [(item, cost) for item, cost in prepared if item.required]
        optional = [(item, cost) for item, cost in prepared if not item.required]
        for item, cost in required:
            if used + cost > token_budget:
                raise ContextBudgetError(
                    f"必选上下文 {item.id} 超出预算：需要 {used + cost}，预算 {token_budget}"
                )
            selected.append(
                SelectedContext(item=item, text=item.text, token_count=cost)
            )
            used += cost

        optional.sort(
            key=lambda pair: (
                -pair[0].priority,
                -pair[0].relevance,
                -pair[0].recency,
                pair[0].id,
            )
        )
        for item, cost in optional:
            if used + cost <= token_budget:
                selected.append(
                    SelectedContext(item=item, text=item.text, token_count=cost)
                )
                used += cost
            else:
                dropped.append(DroppedContext(item_id=item.id, reason="预算不足"))

        rendered = "\n\n".join(
            f"[{selection.item.kind}] source={selection.item.source or 'unknown'}\n"
            f"{selection.text}"
            for selection in selected
        )
        return ContextBuildResult(
            selected=selected,
            dropped=dropped,
            rendered=rendered,
            token_count=used,
            tokenizer_mode=self.token_counter.mode,
            redacted_fields=list(dict.fromkeys(redacted_fields)),
            injection_warnings=list(dict.fromkeys(injection_warnings)),
        )
