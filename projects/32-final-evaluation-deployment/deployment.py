"""Deployment configuration validation with secret-safe health summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class DeploymentConfig:
    mode: str
    ready: bool
    api_key_configured: bool
    model: str
    base_url: str
    problems: tuple[str, ...]

    def health_summary(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ready": self.ready,
            "api_key_configured": self.api_key_configured,
            "model": self.model,
            "base_url": self.base_url,
            "problems": list(self.problems),
        }


def validate_config(
    environment: Mapping[str, str],
    mode: str = "demo",
) -> DeploymentConfig:
    if mode not in {"demo", "llm"}:
        raise ValueError("mode 必须是 demo 或 llm")

    api_key = environment.get("OPENAI_API_KEY", "")
    model = environment.get("OPENAI_MODEL", "")
    base_url = environment.get("OPENAI_BASE_URL", "")
    api_key_configured = bool(api_key)
    problems: list[str] = []

    if mode == "llm":
        if not api_key or api_key.startswith(("replace-", "你的")):
            problems.append("OPENAI_API_KEY 未配置或仍是占位符")
        if not model:
            problems.append("OPENAI_MODEL 未配置")
        if not base_url.startswith(("http://", "https://")):
            problems.append("OPENAI_BASE_URL 必须是 http:// 或 https:// 地址")

    return DeploymentConfig(
        mode=mode,
        ready=not problems,
        api_key_configured=api_key_configured,
        model=model,
        base_url=base_url,
        problems=tuple(problems),
    )
