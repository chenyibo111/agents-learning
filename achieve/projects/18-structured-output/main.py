import argparse
import json
import os
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["title", "summary", "key_points", "confidence", "sources"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "key_points": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "maxItems": 5,
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "sources": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
}
REQUIRED_FIELDS = tuple(OUTPUT_SCHEMA["required"])
ALLOWED_FIELDS = set(OUTPUT_SCHEMA["properties"])
MAX_REPAIR_ATTEMPTS = 2


class StructuredOutputError(ValueError):
    """模型输出无法解析或不符合结构化结果契约。"""


def strip_code_fence(content: str) -> str:
    cleaned = content.strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_json_object(content: str) -> Any:
    cleaned = strip_code_fence(content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise StructuredOutputError(
            f"JSON 解析失败：第 {error.lineno} 行第 {error.colno} 列附近格式不正确"
        ) from error


def collect_validation_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["顶层结果必须是 JSON 对象"]

    errors: list[str] = []
    missing_fields = [field for field in REQUIRED_FIELDS if field not in value]
    errors.extend(f"缺少必填字段：{field}" for field in missing_fields)

    extra_fields = sorted(set(value) - ALLOWED_FIELDS)
    errors.extend(f"不允许的字段：{field}" for field in extra_fields)

    if "title" in value and (
        not isinstance(value["title"], str) or not value["title"].strip()
    ):
        errors.append("字段 title 必须是非空字符串")

    if "summary" in value and (
        not isinstance(value["summary"], str) or not value["summary"].strip()
    ):
        errors.append("字段 summary 必须是非空字符串")

    if "key_points" in value:
        key_points = value["key_points"]
        if not isinstance(key_points, list):
            errors.append("字段 key_points 必须是数组")
        else:
            if not 1 <= len(key_points) <= 5:
                errors.append("字段 key_points 必须包含 1 到 5 项")
            for index, item in enumerate(key_points):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"字段 key_points[{index}] 必须是非空字符串")

    if "confidence" in value and value["confidence"] not in {
        "high",
        "medium",
        "low",
    }:
        errors.append("字段 confidence 必须是 high、medium 或 low")

    if "sources" in value:
        sources = value["sources"]
        if not isinstance(sources, list):
            errors.append("字段 sources 必须是数组")
        else:
            for index, item in enumerate(sources):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"字段 sources[{index}] 必须是非空字符串")

    return errors


def parse_and_validate(content: str) -> dict[str, Any]:
    value = parse_json_object(content)
    errors = collect_validation_errors(value)
    if errors:
        formatted_errors = "\n".join(f"- {error}" for error in errors)
        raise StructuredOutputError(f"结构化结果校验失败：\n{formatted_errors}")
    return value


def validate_with_repair(
    content: str,
    repair: Callable[[str, str], str],
    max_repairs: int = MAX_REPAIR_ATTEMPTS,
) -> dict[str, Any]:
    if max_repairs < 0:
        raise ValueError("max_repairs 不能小于 0")

    current_content = content
    for repair_index in range(max_repairs + 1):
        try:
            return parse_and_validate(current_content)
        except StructuredOutputError as error:
            if repair_index == max_repairs:
                raise

            attempt = repair_index + 1
            print(f"结构化输出校验失败，开始第 {attempt}/{max_repairs} 次自动修复")
            current_content = repair(current_content, str(error))

    raise RuntimeError("自动修复流程异常结束")


def schema_text() -> str:
    return json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2)


def request_completion(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def generate_structured_result(
    client: OpenAI,
    model: str,
    task: str,
) -> dict[str, Any]:
    system_prompt = (
        "你是一个结构化信息整理助手。\n"
        "必须只返回一个 JSON 对象，不要使用 Markdown 代码围栏，不要补充解释。\n"
        f"输出契约如下：\n{schema_text()}"
    )
    initial_content = request_completion(
        client,
        model,
        system_prompt,
        f"请完成以下任务，并严格按照输出契约返回结果：\n{task}",
    )

    def repair(content: str, errors: str) -> str:
        repair_prompt = (
            "请修复下面的模型输出，使其严格符合 JSON 输出契约。\n"
            "只返回修复后的 JSON 对象，不要使用 Markdown 代码围栏，不要解释修复过程。\n\n"
            f"输出契约：\n{schema_text()}\n\n"
            f"校验错误：\n{errors}\n\n"
            f"原始输出：\n{content}"
        )
        return request_completion(client, model, system_prompt, repair_prompt)

    return validate_with_repair(initial_content, repair)


def run_demo() -> None:
    invalid_content = json.dumps(
        {
            "title": "Agent 工具调用",
            "summary": "模型可以请求程序执行外部工具。",
            "key_points": "这里错误地使用了字符串",
            "confidence": "unknown",
        },
        ensure_ascii=False,
    )
    repaired_content = json.dumps(
        {
            "title": "Agent 工具调用",
            "summary": "模型可以请求程序执行外部工具。",
            "key_points": ["模型提出工具调用", "程序执行工具", "结果返回模型"],
            "confidence": "high",
            "sources": ["lessons/01-minimal-agent.md"],
        },
        ensure_ascii=False,
    )

    def repair(_: str, errors: str) -> str:
        print(f"检测到的问题：\n{errors}")
        return repaired_content

    result = validate_with_repair(invalid_content, repair)
    print("\n自动修复后的结构化结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def get_client() -> tuple[OpenAI, str]:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    base_url = os.getenv("OPENAI_BASE_URL") or None
    if not api_key or api_key.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_API_KEY")
    if not model or model.startswith("replace-"):
        raise RuntimeError("请先在 .env 中设置 OPENAI_MODEL")
    return OpenAI(api_key=api_key, base_url=base_url), model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--task")
    args = parser.parse_args()

    if args.demo:
        run_demo()
        return

    task = args.task or input("请输入任务：").strip()
    if not task:
        raise ValueError("任务不能为空")

    client, model = get_client()
    try:
        result = generate_structured_result(client, model, task)
    except StructuredOutputError as error:
        raise RuntimeError(f"结构化输出最终失败：{error}") from error

    print("\n最终结构化结果：")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
