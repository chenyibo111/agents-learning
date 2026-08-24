"""第 7 课 CLI：保留旧 Demo，并提供 Mini Agent Framework 工程实现。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ask_llm
from common.llm import LLMConfigurationError
from mini_agent.memory import SQLiteCheckpointStore
from mini_agent.model import OpenAITextModel, RuleModel
from mini_agent.runner import Runner
from mini_agent.tools import ToolRegistry, ToolSpec
from mini_agent.errors import FrameworkError


def legacy_demo() -> str:
    """Keep the original compressed loop demo unchanged in behavior."""

    from common import run_loop

    def decide(state):
        return "add" if "result" not in state else "finish"

    def act(state, action):
        if action == "add":
            return {**state, "result": state["a"] + state["b"]}, "tool:add"
        return state, f"answer={state['result']}"

    result = run_loop(
        {"a": 4, "b": 5},
        decide,
        act,
        lambda state: "result" in state and result_safe(state),
        max_steps=3,
    )
    return f"MiniFramework events={len(result.events)}; {result.answer}"


def result_safe(state):
    return isinstance(state.get("result"), int)


def build_tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="add",
            description="计算两个整数之和",
            input_schema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer"},
                    "b": {"type": "integer"},
                },
                "required": ["a", "b"],
                "additionalProperties": False,
            },
            handler=lambda a, b: a + b,
            permission="calculator",
        )
    )
    return registry


def run_framework(args: argparse.Namespace) -> int:
    store = SQLiteCheckpointStore(args.checkpoint or ":memory:")
    model = RuleModel() if args.framework_demo else OpenAITextModel()
    runner = Runner(
        model=model,
        tools=build_tools(),
        permissions={"calculator"},
        max_steps=args.max_steps,
        tool_max_attempts=args.tool_max_attempts,
        pause_after_step=args.pause_after_step,
        checkpoint_store=store,
    )

    if args.resume:
        if not args.run_id:
            raise ValueError("--resume 需要 --run-id")
        result = runner.resume(args.run_id)
    else:
        result = runner.run(args.query)

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status in {"completed", "paused"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="第 7 课：从零构建 Agent 框架")
    parser.add_argument("--demo", action="store_true", help="运行原有压缩版 Demo")
    parser.add_argument("--llm", action="store_true", help="保留原有课程问答入口")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--framework-demo",
        action="store_true",
        help="运行 Mini Agent Framework 的离线规则模型",
    )
    modes.add_argument(
        "--llm-agent",
        action="store_true",
        help="运行 OpenAI-compatible 真实 LLM Agent",
    )
    parser.add_argument("--query", default="计算 4 + 5")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--tool-max-attempts", type=int, default=1)
    parser.add_argument("--pause-after-step", type=int)
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.llm:
            print(ask_llm("设计一个最小 Agent Framework，说明 Model、Tool、Policy、Runner 的边界。"))
            return 0

        if args.framework_demo or args.llm_agent:
            return run_framework(args)

        # No new mode selected: preserve the original --demo/default behavior.
        print(legacy_demo())
        return 0
    except (FrameworkError, LLMConfigurationError, ValueError) as error:
        print(f"执行失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
