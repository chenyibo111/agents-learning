import importlib.util
from pathlib import Path
import unittest


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "03-llm-foundation"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "hello_agents_llm_foundation",
        PROJECT / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class LLMFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.llm = load_module()

    def test_token_estimate_is_positive_and_approximate(self):
        self.assertEqual(1, self.llm.estimate_tokens(""))
        self.assertEqual(1, self.llm.estimate_tokens("abcd"))
        self.assertGreater(self.llm.estimate_tokens("这是一个测试"), 0)

    def test_build_messages_preserves_protocol_and_history(self):
        messages = self.llm.build_messages(
            "只回答事实",
            "什么是 token？",
            [{"role": "assistant", "content": "先从文本切分理解。"}],
        )
        self.assertEqual(["system", "assistant", "user"], [item["role"] for item in messages])
        self.assertEqual("什么是 token？", messages[-1]["content"])

    def test_truncate_messages_keeps_system_and_latest_context(self):
        messages = self.llm.build_messages(
            "系统指令",
            "最后一个问题",
            [
                {"role": "user", "content": "很长的旧历史 " * 20},
                {"role": "assistant", "content": "较新的历史"},
            ],
        )
        kept = self.llm.truncate_messages(messages, max_tokens=8)
        self.assertEqual("system", kept[0]["role"])
        self.assertEqual("最后一个问题", kept[-1]["content"])
        self.assertLessEqual(
            sum(self.llm.estimate_tokens(item["content"]) for item in kept),
            8,
        )

    def test_structured_response_is_validated(self):
        raw = self.llm.deterministic_response(
            [{"role": "user", "content": "解释 token"}],
            response_format="json",
        )
        parsed = self.llm.validate_structured_response(raw)
        self.assertEqual("model-generated", parsed["source"])
        with self.assertRaises(ValueError):
            self.llm.validate_structured_response('{"answer": 1}')
        with self.assertRaises(ValueError):
            self.llm.validate_structured_response(
                '{"answer":"x","confidence":2,"source":"model"}'
            )

    def test_demo_reports_json_validation_and_context_budget(self):
        output = self.llm.demo(
            history=[{"role": "assistant", "content": "历史消息"}],
            max_tokens=20,
            response_format="json",
        )
        self.assertIn("预算=20", output)
        self.assertIn("JSON 校验=通过", output)
        self.assertIn("model-generated", output)


if __name__ == "__main__":
    unittest.main()
