"""Optional OpenAI-compatible model adapter with safe configuration errors."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any


class LLMConfigurationError(RuntimeError):
    """Raised when a real-model run has no complete configuration."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str


def load_config() -> LLMConfig:
    """Load configuration without printing or exposing the API key."""
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    except ImportError:
        pass
    values = {
        "base_url": os.getenv("OPENAI_BASE_URL", "").strip(),
        "api_key": os.getenv("OPENAI_API_KEY", "").strip(),
        "model": os.getenv("OPENAI_MODEL", "").strip(),
    }
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise LLMConfigurationError(
            "真实 LLM 模式缺少配置：" + ", ".join(missing) +
            "；请复制 .env.example 为 .env 后填写，API Key 不要提交。"
        )
    return LLMConfig(**values)


def ask_llm(prompt: str, *, system: str = "你是一个严谨的 Agent 课程助手。") -> str:
    """Call an OpenAI-compatible chat endpoint; imports SDK only on demand."""
    config = load_config()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigurationError("真实 LLM 模式需要安装 openai 依赖。") from exc
    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    response: Any = client.chat.completions.create(
        model=config.model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        temperature=0,
    )
    return response.choices[0].message.content or ""
