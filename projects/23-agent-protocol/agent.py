"""Local and LLM-driven Agents that both use the lesson protocol."""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from protocol import (
    EXECUTION_ERROR,
    INVALID_PARAMS,
    decode_message,
    encode_message,
)
from server import ProtocolServer


def send_protocol_request(
    server: ProtocolServer,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Send a request through the same JSON boundary used by the demo."""
    wire_request = encode_message(payload)
    decoded_request = decode_message(wire_request)
    response = server.handle(decoded_request)
    return decode_message(encode_message(response))


class LocalRuleAgent:
    """A deterministic Agent for offline learning and repeatable tests."""

    def __init__(self, server: ProtocolServer) -> None:
        self.server = server

    def plan(self, user_input: str) -> Dict[str, Any]:
        text = user_input.strip()

        multiplication = re.search(
            r"([+-]?\d+)\s*(?:\*|×|x|乘以|乘)\s*([+-]?\d+)",
            text,
            flags=re.IGNORECASE,
        )
        if multiplication:
            return {
                "type": "tool_call",
                "name": "mul_numbers",
                "arguments": {
                    "a": int(multiplication.group(1)),
                    "b": int(multiplication.group(2)),
                },
            }

        addition = re.search(
            r"([+-]?\d+)\s*(?:\+|加|plus)\s*([+-]?\d+)",
            text,
            flags=re.IGNORECASE,
        )
        if addition:
            return {
                "type": "tool_call",
                "name": "add_numbers",
                "arguments": {
                    "a": int(addition.group(1)),
                    "b": int(addition.group(2)),
                },
            }

        if re.search(r"搜索|查找|查询", text):
            query = re.sub(r"^(请)?\s*(搜索|查找|查询)\s*", "", text)
            return {
                "type": "tool_call",
                "name": "search_notes",
                "arguments": {"query": query or text},
            }

        if re.search(r"读取|查看|打开|阅读", text):
            uri = self._find_resource_uri(text)
            if uri:
                return {"type": "resource_read", "uri": uri}

        return {
            "type": "answer",
            "text": (
                "本地规则 Agent 当前支持：计算加法、计算乘法、搜索笔记、读取已注册资源。"
            ),
        }

    def run(self, user_input: str) -> str:
        action = self.plan(user_input)
        if action["type"] == "answer":
            return action["text"]

        if action["type"] == "resource_read":
            response = send_protocol_request(
                self.server,
                {
                    "id": 1,
                    "method": "resources/read",
                    "params": {"uri": action["uri"]},
                },
            )
        else:
            response = send_protocol_request(
                self.server,
                {
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": action["name"],
                        "arguments": action["arguments"],
                    },
                },
            )
        return render_protocol_response(response)

    def _find_resource_uri(self, text: str) -> Optional[str]:
        response = send_protocol_request(
            self.server,
            {"id": 1, "method": "resources/list", "params": {}},
        )
        for resource in response.get("result", []):
            if resource["uri"].lower() in text.lower():
                return resource["uri"]
            if resource["name"].lower() in text.lower():
                return resource["uri"]
        return None


class LLMToolAgent:
    """An OpenAI-compatible Agent whose tool calls cross ProtocolServer."""

    def __init__(
        self,
        server: ProtocolServer,
        client: Any,
        model: str,
        max_rounds: int = 4,
    ) -> None:
        if max_rounds < 1:
            raise ValueError("max_rounds 必须至少为 1")
        self.server = server
        self.client = client
        self.model = model
        self.max_rounds = max_rounds

    def run(self, user_input: str) -> str:
        tools, resources = self._discover_capabilities()
        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": self._system_prompt(resources),
            },
            {"role": "user", "content": user_input},
        ]

        for _ in range(self.max_rounds):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            tool_calls = _get_value(message, "tool_calls") or []
            if not tool_calls:
                return _get_value(message, "content") or "模型没有返回文本结果。"

            messages.append(self._assistant_message(message, tool_calls))
            for tool_call in tool_calls:
                result = self._execute_tool_call(tool_call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": _get_value(tool_call, "id"),
                        "name": self._tool_call_name(tool_call),
                        "content": json.dumps(
                            result,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )

        return "已达到最大工具调用轮数，任务暂未完成。"

    def _discover_capabilities(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        tool_response = send_protocol_request(
            self.server,
            {"id": 1, "method": "tools/list", "params": {}},
        )
        resource_response = send_protocol_request(
            self.server,
            {"id": 2, "method": "resources/list", "params": {}},
        )

        tools = [
            {
                "type": "function",
                "function": {
                    "name": item["name"],
                    "description": item["description"],
                    "parameters": item["input_schema"],
                },
            }
            for item in tool_response.get("result", [])
        ]
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "read_resource",
                    "description": "读取 resources/list 返回的一个已注册资源",
                    "parameters": {
                        "type": "object",
                        "required": ["uri"],
                        "properties": {"uri": {"type": "string"}},
                    },
                },
            }
        )
        return tools, resource_response.get("result", [])

    def _system_prompt(self, resources: List[Dict[str, Any]]) -> str:
        catalog = "\n".join(
            f"- {item['uri']}: {item['description']}"
            for item in resources
        ) or "暂无可读取资源"
        return (
            "你是一个工具调用 Agent。只能使用提供的工具，不能编造工具结果。"
            "如果需要读取资源，请调用 read_resource，并且只能使用下面列出的 URI：\n"
            f"{catalog}"
        )

    def _assistant_message(
        self,
        message: Any,
        tool_calls: List[Any],
    ) -> Dict[str, Any]:
        return {
            "role": "assistant",
            "content": _get_value(message, "content"),
            "tool_calls": [
                {
                    "id": _get_value(call, "id"),
                    "type": "function",
                    "function": {
                        "name": self._tool_call_name(call),
                        "arguments": self._tool_call_arguments(call),
                    },
                }
                for call in tool_calls
            ],
        }

    def _tool_call_name(self, tool_call: Any) -> str:
        function = _get_value(tool_call, "function")
        return str(_get_value(function, "name") or "")

    def _tool_call_arguments(self, tool_call: Any) -> str:
        function = _get_value(tool_call, "function")
        arguments = _get_value(function, "arguments")
        return arguments if isinstance(arguments, str) else json.dumps(arguments or {})

    def _execute_tool_call(self, tool_call: Any) -> Dict[str, Any]:
        name = self._tool_call_name(tool_call)
        raw_arguments = self._tool_call_arguments(tool_call)
        try:
            arguments = json.loads(raw_arguments)
        except (TypeError, json.JSONDecodeError):
            return {
                "error": {
                    "code": INVALID_PARAMS,
                    "message": "模型返回的工具参数不是合法 JSON",
                }
            }
        if not isinstance(arguments, dict):
            return {
                "error": {
                    "code": INVALID_PARAMS,
                    "message": "模型返回的工具参数必须是对象",
                }
            }

        if name == "read_resource":
            return send_protocol_request(
                self.server,
                {
                    "id": 1,
                    "method": "resources/read",
                    "params": {"uri": arguments.get("uri")},
                },
            )

        return send_protocol_request(
            self.server,
            {
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def render_protocol_response(response: Dict[str, Any]) -> str:
    if "error" in response:
        error = response["error"]
        return f"执行失败（{error.get('code')}）：{error.get('message')}"

    result = response.get("result")
    if isinstance(result, dict) and "contents" in result:
        return str(result["contents"])
    if isinstance(result, dict) and "sum" in result:
        return f"计算结果：{result['sum']}"
    if isinstance(result, list):
        if not result:
            return "没有找到匹配内容。"
        return "找到：" + "、".join(item.get("name", "") for item in result)
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


def create_llm_client() -> Tuple[Any, str]:
    from dotenv import load_dotenv
    from openai import OpenAI
    import os

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("replace-") or api_key.startswith("你的"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")

    kwargs: Dict[str, Any] = {"api_key": api_key}
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs), os.getenv("OPENAI_MODEL", "deepseek-v4-flash")
