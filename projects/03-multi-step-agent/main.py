import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


def add_numbers(a: float, b: float) -> float:
    return a + b


def multiply_numbers(a: float, b: float) -> float:
    return a * b


def divide_numbers(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("除数不能为 0")
    return a / b


NUMBER_PARAMETERS = {
    "type": "object",
    "properties": {
        "a": {"type": "number", "description": "第一个数字"},
        "b": {"type": "number", "description": "第二个数字"},
    },
    "required": ["a", "b"],
    "additionalProperties": False,
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_numbers",
            "description": "计算两个数字的和。",
            "parameters": NUMBER_PARAMETERS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "multiply_numbers",
            "description": "计算两个数字的乘积。",
            "parameters": NUMBER_PARAMETERS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "divide_numbers",
            "description": "用第一个数字除以第二个数字。除数不能为 0。",
            "parameters": NUMBER_PARAMETERS,
        },
    },
]


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    a = float(arguments["a"])
    b = float(arguments["b"])

    if name == "add_numbers":
        result = add_numbers(a, b)
    elif name == "multiply_numbers":
        result = multiply_numbers(a, b)
    elif name == "divide_numbers":
        result = divide_numbers(a, b)
    else:
        raise ValueError(f"未知工具: {name}")

    return str(result)


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None

    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")

    user_task = input("请输入任务：").strip()
    if not user_task:
        raise ValueError("任务不能为空")

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "你是一个学习用 Agent。所有算术运算都必须调用工具。"
                "如果任务包含多个步骤，必须先完成前一步，再根据工具结果执行下一步。"
                "不要自行心算。"
            ),
        },
        {"role": "user", "content": user_task},
    ]

    max_steps = 5
    for step in range(max_steps):
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

            try:
                result = call_tool(name, arguments)
            except Exception as error:
                result = f"工具执行失败：{error}"
                print(result)
            else:
                print(f"工具结果: {result}")

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

