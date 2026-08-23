"""第一课的可读版 Agent 内核：工具、状态、循环和离线策略。"""

from dataclasses import dataclass, field
import re
import time
from typing import Any


class UnknownToolError(ValueError):
    """模型或规则策略请求了未注册的工具。"""


class MaxStepsExceeded(RuntimeError):
    """Agent 在规定步数内没有结束。"""


@dataclass
class AgentResult:
    answer: str
    steps: int
    tool_names: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


def add_numbers(a: float, b: float) -> float:
    """返回两个数字的和。"""
    return a + b

def subtract_numbers(a: float, b: float) -> float:
    """返回两个数字的差。"""
    return a - b

def multiply_numbers(a: float, b: float) -> float:
    """返回两个数字的乘积。"""
    return a * b


def divide_numbers(a: float, b: float) -> float:
    """用 a 除以 b；除数不能为零。"""
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
    {"type": "function", "function": {"name": "add_numbers", "description": "计算两个数字的和。", "parameters": NUMBER_PARAMETERS}},
    {"type": "function", "function": {"name": "subtract_numbers", "description": "计算两个数字的差。", "parameters": NUMBER_PARAMETERS}},
    {"type": "function", "function": {"name": "multiply_numbers", "description": "计算两个数字的乘积。", "parameters": NUMBER_PARAMETERS}},
    {"type": "function", "function": {"name": "divide_numbers", "description": "用第一个数字除以第二个数字；除数不能为 0。", "parameters": NUMBER_PARAMETERS}},
]

_TOOL_FUNCTIONS = {
    "add_numbers": add_numbers,
    "subtract_numbers": subtract_numbers,
    "multiply_numbers": multiply_numbers,
    "divide_numbers": divide_numbers,
}


def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """根据注册表调用工具，并把模型参数转换为受控的数字输入。"""
    function = _TOOL_FUNCTIONS.get(name)
    if function is None:
        raise UnknownToolError(f"未知工具: {name}")
    if set(arguments) != {"a", "b"}:
        raise ValueError("工具参数必须只有 a 和 b")
    try:
        a, b = float(arguments["a"]), float(arguments["b"])
    except (TypeError, ValueError) as exc:
        raise ValueError("a 和 b 必须是数字") from exc
    return str(function(a, b))


def execute_tool_safely(name: str, arguments: dict[str, Any]) -> str:
    """把工具异常转换为 observation，交给上层 Agent 决定如何处理。"""
    try:
        return call_tool(name, arguments)
    except Exception as error:  # 工具边界必须隔离未知的业务异常
        return f"工具执行失败：{error}"


def run_actions(actions: list[tuple[str, dict[str, Any]]], *, max_steps: int = 5) -> AgentResult:
    """执行已规划的工具动作；动作数量超过上限时立即停止。"""
    if max_steps < 1:
        raise ValueError("max_steps 必须大于 0")
    if len(actions) > max_steps:
        raise MaxStepsExceeded(f"动作数 {len(actions)} 超过最大步数 {max_steps}")
    messages: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    tool_names: list[str] = []
    answer = ""
    for step, (name, arguments) in enumerate(actions, start=1):
        started_at = time.perf_counter()
        observation = execute_tool_safely(name, arguments)
        duration_ms = round((time.perf_counter() - started_at) * 1000, 3)
        tool_names.append(name)
        messages.append({"role": "tool", "name": name, "arguments": arguments, "content": observation})
        events.append(
            {
                "step": step,
                "tool": name,
                "arguments": dict(arguments),
                "observation": observation,
                "duration_ms": duration_ms,
            }
        )
        answer = observation
    return AgentResult(answer=answer, steps=len(actions), tool_names=tool_names, messages=messages, events=events)


def _number(value: str) -> float:
    return float(value)


def parse_offline_actions(task: str) -> list[tuple[str, dict[str, Any]]]:
    """解析课程用的固定中文算术任务，展示规则策略而非伪装成 LLM。"""
    addition = re.search(r"(\d+(?:\.\d+)?)\s*加\s*(\d+(?:\.\d+)?)", task)
    multiplication = re.search(r"(\d+(?:\.\d+)?)\s*(?:乘以|乘)\s*(\d+(?:\.\d+)?)", task)
    result_multiplication = re.search(r"结果\s*(?:乘以|乘)\s*(\d+(?:\.\d+)?)", task)
    division = re.search(r"(\d+(?:\.\d+)?)\s*(?:除以|除)\s*(\d+(?:\.\d+)?)", task)
    subtraction = re.search(r"(\d+(?:\.\d+)?)\s*(?:减去|减)\s*(\d+(?:\.\d+)?)", task)
    if addition and (multiplication or result_multiplication):
        first = (_number(addition.group(1)), _number(addition.group(2)))
        second = (_number(multiplication.group(2)),) if multiplication else (_number(result_multiplication.group(1)),)
        first_result = add_numbers(*first)
        return [("add_numbers", {"a": first[0], "b": first[1]}), ("multiply_numbers", {"a": first_result, "b": second[0]})]
    if addition:
        return [("add_numbers", {"a": _number(addition.group(1)), "b": _number(addition.group(2))})]
    if multiplication:
        return [("multiply_numbers", {"a": _number(multiplication.group(1)), "b": _number(multiplication.group(2))})]
    if division:
        return [("divide_numbers", {"a": _number(division.group(1)), "b": _number(division.group(2))})]
    if subtraction:
        return [("subtract_numbers", {"a": _number(subtraction.group(1)), "b": _number(subtraction.group(2))})]
    raise ValueError("离线 Demo 只支持加法、减法、乘法、除法示例")


def run_offline(task: str, *, max_steps: int = 5) -> AgentResult:
    """用规则策略完成任务，保留和真实 Agent 相同的结果结构。"""
    actions = parse_offline_actions(task)
    return run_actions(actions, max_steps=max_steps)
