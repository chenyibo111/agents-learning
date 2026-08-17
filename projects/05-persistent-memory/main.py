import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

SESSION_FILE = Path(__file__).with_name("session.json")
SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "你是一个学习用计算 Agent。所有算术运算都必须调用工具。"
        "请结合当前对话历史理解‘刚才的结果’等指代。"
    ),
}


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


def save_messages(messages: list[dict[str, Any]]) -> None:
    SESSION_FILE.write_text(
        json.dumps(messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_messages() -> list[dict[str, Any]]:
    if not SESSION_FILE.exists():
        return [SYSTEM_MESSAGE.copy()]

    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("警告：session.json 格式损坏，将创建新的会话。")
        return [SYSTEM_MESSAGE.copy()]

    if not isinstance(data, list) or not data:
        return [SYSTEM_MESSAGE.copy()]
    return data


def run_agent(client: OpenAI, model: str, messages: list[dict[str, Any]]) -> None:
    for step in range(5):
        print(f"\n--- agent step {step + 1} ---")
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        save_messages(messages)

        if not message.tool_calls:
            print(f"Agent：{message.content or '没有返回文本。'}")
            return

        for tool_call in message.tool_calls:
            name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"调用工具: {name}({arguments})")

            try:
                result = call_tool(name, arguments)
            except Exception as error:
                result = f"工具执行失败：{error}"
            print(f"工具结果: {result}")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
            )
            save_messages(messages)

    print("Agent：超过最大步数，停止本次任务。")


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None

    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")

    client = OpenAI(api_key=api_key, base_url=base_url)
    messages = load_messages()
    print(f"已加载 {len(messages) - 1} 条历史消息。")
    print("输入 exit 退出，输入 clear 清空持久化记忆。")

    while True:
        user_task = input("\n你：").strip()

        if user_task.lower() in {"exit", "quit"}:
            print("对话结束。")
            return
        if user_task.lower() == "clear":
            messages = [SYSTEM_MESSAGE.copy()]
            save_messages(messages)
            print("已清空持久化记忆。")
            continue
        if not user_task:
            print("请输入任务。")
            continue

        messages.append({"role": "user", "content": user_task})
        save_messages(messages)
        run_agent(client, model, messages)


if __name__ == "__main__":
    main()

