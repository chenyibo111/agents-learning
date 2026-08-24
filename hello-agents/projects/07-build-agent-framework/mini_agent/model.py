"""Model boundaries: deterministic offline model and real text model."""

from __future__ import annotations

import re
import json
from typing import Any, Callable, Protocol

from .contracts import Action, Message, ModelResponse, ToolCall


class Model(Protocol):
    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> str | ModelResponse:
        """Generate either a structured response or JSON text."""


class RuleModel:
    """Deterministic model used by offline tests and the course demo."""

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> ModelResponse:
        for message in reversed(messages):
            if message.role == "tool":
                return ModelResponse(
                    action=Action(
                        kind="final",
                        content=f"工具 {message.name} 返回结果：{message.content}",
                    ),
                    usage_tokens=1,
                    metadata={"model": "rule"},
                )

        prompt = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        numbers = re.findall(r"-?\d+", prompt)
        if len(numbers) >= 2 and any(tool.get("name") == "add" for tool in tools):
            arguments = {"a": int(numbers[0]), "b": int(numbers[1])}
            return ModelResponse(
                action=Action(
                    kind="tool_call",
                    tool_call=ToolCall(name="add", arguments=arguments),
                ),
                usage_tokens=2,
                metadata={"model": "rule"},
            )

        return ModelResponse(
            action=Action(kind="final", content="规则模型无法找到可用的 add 工具。"),
            usage_tokens=1,
            metadata={"model": "rule"},
        )


class OpenAITextModel:
    """Use the repository's OpenAI-compatible helper and return JSON text."""

    def __init__(
        self,
        *,
        ask: Callable[..., str] | None = None,
        system: str = (
            "你是一个 Agent 决策模型。只输出 JSON："
            "工具调用格式为 {\"type\":\"tool_call\",\"tool\":\"工具名\","
            "\"arguments\":{...}}；最终回答格式为 "
            "{\"type\":\"final\",\"content\":\"...\"}。"
        ),
    ):
        if ask is None:
            from common import ask_llm

            ask = ask_llm
        self.ask = ask
        self.system = system

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]],
    ) -> str:
        prompt = {
            "messages": [message.to_dict() for message in messages],
            "tools": tools,
        }
        return self.ask(json.dumps(prompt, ensure_ascii=False), system=self.system)
