"""Turn model output into a validated internal Action."""

from __future__ import annotations

import json
from typing import Any

from .contracts import Action, ModelResponse, ToolCall
from .errors import InvalidActionError


class Policy:
    """Strictly parse final/tool_call responses from any Model."""

    def parse(self, output: str | dict[str, Any] | ModelResponse) -> Action:
        if isinstance(output, ModelResponse):
            return output.action
        if isinstance(output, str):
            try:
                payload = json.loads(output)
            except json.JSONDecodeError as exc:
                raise InvalidActionError("模型输出不是合法 JSON") from exc
        elif isinstance(output, dict):
            payload = output
        else:
            raise InvalidActionError("模型输出类型不受支持")

        if not isinstance(payload, dict):
            raise InvalidActionError("模型输出必须是 JSON object")
        kind = payload.get("type", payload.get("kind"))
        if kind == "final":
            content = payload.get("content")
            if not isinstance(content, str):
                raise InvalidActionError("final action 的 content 必须是 string")
            return Action(kind="final", content=content)
        if kind == "tool_call":
            name = payload.get("tool") or payload.get("name")
            arguments = payload.get("arguments", {})
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise InvalidActionError("tool_call 缺少合法的 tool 或 arguments")
            return Action(
                kind="tool_call",
                tool_call=ToolCall(name=name, arguments=arguments),
            )
        raise InvalidActionError(f"未知 action 类型：{kind}")
