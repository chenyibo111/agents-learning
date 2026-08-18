import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_DIR = Path(__file__).resolve().parents[1] / "projects" / "23-agent-protocol"


def load_project_module(module_name: str):
    source_file = PROJECT_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


protocol = load_project_module("protocol")
registry = load_project_module("registry")
business = load_project_module("business")
server = load_project_module("server")
agent = load_project_module("agent")


def text_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=None))]
    )


def tool_response(call_id: str, name: str, arguments: str):
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[call])
            )
        ]
    )


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(responses)
        )


class LLMToolAgentTests(unittest.TestCase):
    def build_agent(self, client, max_rounds=4):
        return agent.LLMToolAgent(
            server.ProtocolServer(business.build_registry()),
            client,
            model="test-model",
            max_rounds=max_rounds,
        )

    def test_plain_model_text_ends_without_tool_call(self) -> None:
        client = FakeClient([text_response("你好，我可以帮助你。")])

        answer = self.build_agent(client).run("你好")

        self.assertEqual(answer, "你好，我可以帮助你。")
        self.assertEqual(len(client.chat.completions.calls), 1)

    def test_tool_call_goes_through_protocol_and_returns_to_model(self) -> None:
        client = FakeClient(
            [
                tool_response("call-1", "add_numbers", '{"a": 4, "b": 6}'),
                text_response("计算结果是 10。"),
            ]
        )

        answer = self.build_agent(client).run("请计算 4 加 6")

        self.assertEqual(answer, "计算结果是 10。")
        self.assertEqual(len(client.chat.completions.calls), 2)
        follow_up_messages = client.chat.completions.calls[1]["messages"]
        tool_messages = [
            message for message in follow_up_messages if message["role"] == "tool"
        ]
        self.assertEqual(len(tool_messages), 1)
        self.assertIn('"sum": 10', tool_messages[0]["content"])

    def test_read_resource_tool_becomes_resources_read_protocol_call(self) -> None:
        client = FakeClient(
            [
                tool_response(
                    "call-2",
                    "read_resource",
                    '{"uri": "note://agent-basics"}',
                ),
                text_response("我读到了 Agent 基础笔记。"),
            ]
        )

        answer = self.build_agent(client).run("读取 Agent 基础")

        self.assertIn("Agent 基础", answer)
        follow_up_messages = client.chat.completions.calls[1]["messages"]
        tool_message = [
            message for message in follow_up_messages if message["role"] == "tool"
        ][0]
        self.assertIn("Agent 通常通过模型", tool_message["content"])

    def test_invalid_tool_json_is_returned_as_error_result(self) -> None:
        client = FakeClient(
            [
                tool_response("call-3", "add_numbers", "not-json"),
                text_response("参数格式不正确。"),
            ]
        )

        self.build_agent(client).run("请计算")

        tool_message = [
            message
            for message in client.chat.completions.calls[1]["messages"]
            if message["role"] == "tool"
        ][0]
        self.assertEqual(json.loads(tool_message["content"])["error"]["code"], -32602)

    def test_tool_loop_stops_at_max_rounds(self) -> None:
        repeated = [
            tool_response(f"call-{index}", "add_numbers", '{"a": 1, "b": 1}')
            for index in range(3)
        ]
        client = FakeClient(repeated)

        answer = self.build_agent(client, max_rounds=2).run("持续计算")

        self.assertIn("最大工具调用轮数", answer)
        self.assertEqual(len(client.chat.completions.calls), 2)


if __name__ == "__main__":
    unittest.main()
