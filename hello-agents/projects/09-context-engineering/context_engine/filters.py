"""Sensitive-data redaction and prompt-injection signal detection."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any


@dataclass(frozen=True)
class RedactionResult:
    text: str
    fields: list[str] = field(default_factory=list)


class SensitiveDataFilter:
    """Replace secret values while retaining only safe field names."""

    _patterns = (
        ("api_key", re.compile(r"(?i)(api[_-]?key)(\s*[:=]\s*)([^\s,;]+)")),
        ("authorization", re.compile(r"(?i)(authorization)(\s*[:=]\s*)([^\s,;]+(?:\s+[^\s,;]+)?)")),
        ("cookie", re.compile(r"(?i)(cookie)(\s*[:=]\s*)([^\s,;]+)")),
        ("password", re.compile(r"(?i)(password|passwd)(\s*[:=]\s*)([^\s,;]+)")),
        ("token", re.compile(r"(?i)(token)(\s*[:=]\s*)([^\s,;]+)")),
    )

    def redact(self, text: str) -> RedactionResult:
        fields: list[str] = []
        redacted = text
        for field_name, pattern in self._patterns:
            if pattern.search(redacted):
                fields.append(field_name)
                redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        return RedactionResult(
            text=redacted,
            fields=list(dict.fromkeys(fields)),
        )

    def redact_metadata(self, metadata: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        fields: list[str] = []

        def visit(value: Any, key: str = "") -> Any:
            normalized = key.lower().replace("-", "_")
            if normalized in {
                "api_key",
                "apikey",
                "authorization",
                "cookie",
                "password",
                "passwd",
                "token",
                "access_token",
                "refresh_token",
            }:
                fields.append(normalized)
                return "[REDACTED]"
            if isinstance(value, dict):
                return {str(child_key): visit(child_value, str(child_key)) for child_key, child_value in value.items()}
            if isinstance(value, list):
                return [visit(child_value, key) for child_value in value]
            if isinstance(value, str):
                result = self.redact(value)
                fields.extend(result.fields)
                return result.text
            return value

        safe = visit(metadata)
        return safe, list(dict.fromkeys(fields))


class PromptInjectionDetector:
    """Detect common instruction-like phrases in untrusted external text."""

    _patterns = (
        ("ignore_instructions", re.compile(r"(?i)ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|system)?\s*instructions?")),
        ("ignore_instructions", re.compile(r"忽略(?:之前|先前|所有)?的?指令")),
        ("reveal_system_prompt", re.compile(r"(?i)(reveal|show|leak).{0,30}system\s+prompt")),
        ("reveal_system_prompt", re.compile(r"泄露.{0,20}系统提示")),
        ("override_policy", re.compile(r"(?i)override.{0,30}(policy|instructions?)")),
        ("override_policy", re.compile(r"覆盖.{0,20}(策略|规则|指令)")),
    )

    def detect(self, text: str) -> list[str]:
        warnings = [name for name, pattern in self._patterns if pattern.search(text)]
        return list(dict.fromkeys(warnings))
