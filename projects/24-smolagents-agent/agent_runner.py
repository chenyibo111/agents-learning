"""smolagents adapter and OpenAI-compatible model configuration."""

import importlib.util
import os
from typing import Any, Optional

from tools import all_tools


def smolagents_available() -> bool:
    return importlib.util.find_spec("smolagents") is not None


def require_smolagents() -> None:
    if not smolagents_available():
        raise RuntimeError(
            "本课需要 smolagents，请先运行："
            "python3 -m pip install -r projects/24-smolagents-agent/requirements.txt"
        )


def validate_model_config(
    api_key: Optional[str],
    model_id: Optional[str],
    api_base: Optional[str],
) -> None:
    if not api_key or api_key.startswith("replace-") or api_key.startswith("你的"):
        raise ValueError("OPENAI_API_KEY 未配置或仍是占位符")
    if not model_id:
        raise ValueError("OPENAI_MODEL 未配置")
    if api_base is not None and not api_base.startswith(("http://", "https://")):
        raise ValueError("OPENAI_BASE_URL 必须是 http:// 或 https:// 地址")


def build_model(
    api_key: str,
    model_id: str,
    api_base: Optional[str] = None,
    tool_choice: str = "auto",
) -> Any:
    require_smolagents()
    validate_model_config(api_key, model_id, api_base)
    from smolagents import OpenAIServerModel

    kwargs = {
        "model_id": model_id,
        "api_key": api_key,
        "tool_choice": tool_choice,
    }
    if api_base:
        kwargs["api_base"] = api_base
    return OpenAIServerModel(**kwargs)


def build_agent(
    api_key: str,
    model_id: str,
    api_base: Optional[str] = None,
    max_steps: int = 6,
    tool_choice: str = "auto",
) -> Any:
    if max_steps < 1:
        raise ValueError("max_steps 必须至少为 1")
    require_smolagents()
    model = build_model(api_key, model_id, api_base, tool_choice)
    from smolagents import ToolCallingAgent

    return ToolCallingAgent(
        tools=all_tools(),
        model=model,
        max_steps=max_steps,
    )


def build_agent_from_env(max_steps: int = 6) -> Any:
    try:
        from dotenv import load_dotenv
    except ImportError as error:
        raise RuntimeError("请先安装 python-dotenv") from error

    load_dotenv()
    return build_agent(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        model_id=os.getenv("OPENAI_MODEL", ""),
        api_base=os.getenv("OPENAI_BASE_URL"),
        tool_choice=os.getenv("OPENAI_TOOL_CHOICE", "auto"),
        max_steps=max_steps,
    )
