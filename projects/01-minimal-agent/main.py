import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def add_numbers(a: float, b: float) -> float:
    """返回两个数字的和。"""
    return a + b

def mul_numbers(a: float, b: float) -> float:
    """返回两个数字的乘积。"""
    return a * b


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_numbers",
            "description": "计算两个数字的和。",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个数字"},
                    "b": {"type": "number", "description": "第二个数字"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mul_numbers",
            "description": "计算两个数字的乘积。",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number", "description": "第一个数字"},
                    "b": {"type": "number", "description": "第二个数字"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
        },
    }
]


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    if name == "add_numbers":
        return str(add_numbers(float(arguments["a"]), float(arguments["b"])))
    if name == "mul_numbers":
        return str(mul_numbers(float(arguments["a"]), float(arguments["b"])))
    raise ValueError(f"未知工具: {name}")


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None

    if not api_key or api_key == "replace-me":
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model == "replace-with-your-model":
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": "你是一个学习用 Agent。需要计算时优先调用工具，不要自己心算。",
        },
        {"role": "user", "content": "请计算 23 加 19，并说明你调用了什么工具。"},
        {"role": "user", "content": "请计算 23 乘以 19，并说明你调用了什么工具。"},
        # {"role": "user", "content": "今天上海天气怎么样，并说明你调用了什么工具。"},
    ]

    for step in range(3):
        print(f"\n--- step {step + 1} ---")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))

        if not message.tool_calls:
            print(message.content or "没有返回文本。")
            return

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"调用工具: {name}({arguments})")
            result = call_tool(name, arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )

    raise RuntimeError("超过最大步数，Agent 可能陷入循环。")


if __name__ == "__main__":
    main()

