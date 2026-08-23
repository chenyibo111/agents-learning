"""用离线可复现的方式演示 LLM 请求的消息、上下文和结构化输出。"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import ask_llm


ALLOWED_ROLES = {"system", "user", "assistant", "tool"}


def estimate_tokens(text: str) -> int:
    """用粗略字符比例估算 token；不用于真实计费。"""
    return max(1, (len(text) + 3) // 4)


def validate_messages(messages: list[dict[str, Any]]) -> None:
    """校验最小消息协议，避免业务层传入结构错误的消息。"""
    if not messages:
        raise ValueError("消息列表不能为空")
    for message in messages:
        if message.get("role") not in ALLOWED_ROLES:
            raise ValueError("消息 role 必须是 system、user、assistant 或 tool")
        if not isinstance(message.get("content"), str):
            raise ValueError("消息 content 必须是字符串")


def build_messages(
    system: str,
    user: str,
    history: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """按 system → history → user 的协议组装消息。"""
    if not system.strip():
        raise ValueError("system 指令不能为空")
    if not user.strip():
        raise ValueError("用户任务不能为空")
    messages = [{"role": "system", "content": system}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user})
    validate_messages(messages)
    return messages


def render_prompt(messages: list[dict[str, Any]]) -> str:
    """把消息协议渲染成便于观察的文本，不代表所有 SDK 的真实序列化格式。"""
    validate_messages(messages)
    return "\n".join(f"{message['role']}: {message['content']}" for message in messages)


def truncate_messages(
    messages: list[dict[str, Any]],
    max_tokens: int,
) -> list[dict[str, Any]]:
    """保留 system 和尽可能多的最新消息，模拟上下文预算管理。"""
    if max_tokens < 1:
        raise ValueError("max_tokens 必须大于 0")
    validate_messages(messages)

    system = messages[0] if messages[0]["role"] == "system" else None
    candidates = messages[1:] if system else messages
    selected: list[dict[str, Any]] = []
    used = estimate_tokens(system["content"]) if system else 0

    for message in reversed(candidates):
        cost = estimate_tokens(message["content"])
        if used + cost > max_tokens:
            continue
        selected.append(message)
        used += cost

    selected.reverse()
    return ([system] if system else []) + selected


def deterministic_response(
    messages: list[dict[str, Any]],
    *,
    response_format: str = "text",
) -> str:
    """生成不访问网络的演示响应，模拟模型输出但不伪装成真实推理。"""
    validate_messages(messages)
    latest_user = next(
        message["content"]
        for message in reversed(messages)
        if message["role"] == "user"
    )
    if response_format == "json":
        return json.dumps(
            {
                "answer": f"演示响应：{latest_user}",
                "confidence": 0.5,
                "source": "model-generated",
            },
            ensure_ascii=False,
        )
    if response_format != "text":
        raise ValueError("response_format 必须是 text 或 json")
    return f"演示模型响应：{latest_user}；输出仍需经过程序校验。"


def validate_structured_response(raw: str) -> dict[str, Any]:
    """校验演示用 JSON 输出，拒绝缺字段、类型错误和越界置信度。"""
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("模型输出不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("模型 JSON 输出必须是对象")

    required = {"answer", "confidence", "source"}
    missing = required - value.keys()
    if missing:
        raise ValueError(f"模型 JSON 缺少字段: {', '.join(sorted(missing))}")
    if not isinstance(value["answer"], str):
        raise ValueError("answer 必须是字符串")
    if isinstance(value["confidence"], bool) or not isinstance(value["confidence"], (int, float)):
        raise ValueError("confidence 必须是数字")
    if not 0 <= value["confidence"] <= 1:
        raise ValueError("confidence 必须在 0 和 1 之间")
    if not isinstance(value["source"], str):
        raise ValueError("source 必须是字符串")
    return value


def demo(
    *,
    system: str = "只回答事实",
    user: str = "什么是上下文窗口？",
    history: list[dict[str, Any]] | None = None,
    max_tokens: int = 40,
    response_format: str = "text",
) -> str:
    """展示消息拼接、上下文截断和模型输出校验。"""
    messages = build_messages(system, user, history)
    kept_messages = truncate_messages(messages, max_tokens)
    prompt = render_prompt(kept_messages)
    raw_response = deterministic_response(
        kept_messages,
        response_format=response_format,
    )

    lines = [
        f"原始消息数={len(messages)}",
        f"保留消息数={len(kept_messages)}",
        f"估算 token={estimate_tokens(prompt)} / 预算={max_tokens}",
        f"消息协议={','.join(message['role'] for message in kept_messages)}",
    ]
    if response_format == "json":
        parsed = validate_structured_response(raw_response)
        lines.append(f"JSON 校验=通过；source={parsed['source']}")
        lines.append(f"模型输出={json.dumps(parsed, ensure_ascii=False)}")
    else:
        lines.append(f"模型输出={raw_response}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--history", action="store_true", help="加入一组历史消息")
    parser.add_argument("--system", default="只回答事实")
    parser.add_argument("--task", default="什么是上下文窗口？")
    parser.add_argument("--max-tokens", type=int, default=40)
    parser.add_argument("--response-format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    history = (
        [
            {"role": "user", "content": "我正在学习 Agent。"},
            {"role": "assistant", "content": "可以从消息、工具和状态开始。"},
        ]
        if args.history
        else None
    )
    if args.llm:
        output = ask_llm(
            "解释 token、上下文窗口、采样、幻觉和结构化输出。"
            "说明模型输出为什么必须经过程序校验。"
        )
    else:
        output = demo(
            system=args.system,
            user=args.task,
            history=history,
            max_tokens=args.max_tokens,
            response_format=args.response_format,
        )
    print(output)


if __name__ == "__main__":
    main()
