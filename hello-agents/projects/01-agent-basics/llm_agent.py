"""第一课的真实 OpenAI-compatible tool-calling Agent。"""

import json
import time
from typing import Any

from common import LLMConfigurationError, load_config
from agent import AgentResult, TOOLS, execute_tool_safely


def run_llm(task: str, *, max_steps: int = 5) -> AgentResult:
    """执行真实模型循环；模型只建议工具，Python 负责验证和执行。"""
    if max_steps < 1:
        raise ValueError("max_steps 必须大于 0")
    config = load_config()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise LLMConfigurationError("真实 LLM 模式需要安装 openai 依赖。") from exc

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "你是学习用 Agent。所有算术运算必须调用工具，不要自行心算。"},
        {"role": "user", "content": task},
    ]
    tool_names: list[str] = []
    events: list[dict[str, Any]] = []
    for step in range(1, max_steps + 1):
        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        dumped = message.model_dump(exclude_none=True) if hasattr(message, "model_dump") else {
            "role": "assistant", "content": message.content, "tool_calls": message.tool_calls,
        }
        messages.append(dumped)
        if not message.tool_calls:
            return AgentResult(
                answer=message.content or "没有返回文本。",
                steps=step,
                tool_names=tool_names,
                messages=messages,
                events=events,
            )
        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            started_at = time.perf_counter()
            observation = execute_tool_safely(name, arguments)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
            tool_names.append(name)
            events.append(
                {
                    "step": len(events) + 1,
                    "tool": name,
                    "arguments": dict(arguments),
                    "observation": observation,
                    "duration_ms": duration_ms,
                }
            )
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": observation})
    raise RuntimeError(f"超过最大步数 {max_steps}，Agent 可能陷入循环。")
