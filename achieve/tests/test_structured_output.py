import importlib.util
import unittest
from pathlib import Path


SOURCE_FILE = (
    Path(__file__).resolve().parents[1]
    / "projects"
    / "18-structured-output"
    / "main.py"
)
SPEC = importlib.util.spec_from_file_location("structured_output", SOURCE_FILE)
assert SPEC and SPEC.loader
structured_output = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(structured_output)


VALID_RESULT = {
    "title": "Agent 工具调用",
    "summary": "Agent 通过模型决定是否调用外部工具。",
    "key_points": ["模型决定调用工具", "程序执行工具", "结果返回模型"],
    "confidence": "high",
    "sources": ["lessons/01-minimal-agent.md"],
}


class StructuredOutputTests(unittest.TestCase):
    def test_accepts_valid_result(self) -> None:
        result = structured_output.parse_and_validate(
            structured_output.json.dumps(VALID_RESULT, ensure_ascii=False)
        )
        self.assertEqual(result, VALID_RESULT)

    def test_accepts_json_inside_markdown_code_fence(self) -> None:
        content = "```json\n" + structured_output.json.dumps(VALID_RESULT) + "\n```"
        result = structured_output.parse_and_validate(content)
        self.assertEqual(result["confidence"], "high")

    def test_reports_missing_and_invalid_fields(self) -> None:
        invalid = {
            "title": "",
            "summary": "有内容",
            "key_points": "不是数组",
            "confidence": "unknown",
        }

        with self.assertRaises(structured_output.StructuredOutputError) as context:
            structured_output.parse_and_validate(
                structured_output.json.dumps(invalid, ensure_ascii=False)
            )

        message = str(context.exception)
        self.assertIn("title", message)
        self.assertIn("key_points", message)
        self.assertIn("confidence", message)
        self.assertIn("sources", message)

    def test_repairs_invalid_result_once(self) -> None:
        repair_calls: list[tuple[str, str]] = []

        def repair(content: str, errors: str) -> str:
            repair_calls.append((content, errors))
            return structured_output.json.dumps(VALID_RESULT, ensure_ascii=False)

        result = structured_output.validate_with_repair(
            '{"title": "缺少字段"}',
            repair,
            max_repairs=2,
        )

        self.assertEqual(result, VALID_RESULT)
        self.assertEqual(len(repair_calls), 1)
        self.assertIn("sources", repair_calls[0][1])

    def test_stops_after_max_repairs(self) -> None:
        repair_calls = 0

        def repair(_: str, __: str) -> str:
            nonlocal repair_calls
            repair_calls += 1
            return '{"title": "仍然不完整"}'

        with self.assertRaises(structured_output.StructuredOutputError):
            structured_output.validate_with_repair(
                '{"title": "第一次不完整"}',
                repair,
                max_repairs=2,
            )

        self.assertEqual(repair_calls, 2)


if __name__ == "__main__":
    unittest.main()
