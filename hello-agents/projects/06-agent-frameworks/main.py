"""第 6 课 CLI：离线 Runtime 与真实 Agent 框架适配器。"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
if str(PROJECTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECTS_DIR))

from common import ask_llm
from common.llm import LLMConfigurationError
from frameworks import (
    AgentRuntime,
    SQLiteCheckpointStore,
    ScriptedAdapter,
    build_adapters,
    demo,
)
from integrations.common import (
    AdapterCapabilities,
    AgentMessage,
    MissingOptionalDependency,
    ProviderError,
)
from async_runtime import AsyncAgentRuntime
from retry import RetryPolicy


class OfflineAsyncAdapter:
    """Use deterministic local responses through the same async contract."""

    capabilities = AdapterCapabilities(supports_cancellation=True)

    async def respond(
        self,
        agent: str,
        prompt: str,
        *,
        on_event=None,
        cancel_token=None,
    ) -> AgentMessage:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        if agent == "research":
            content = "研究结果：Agent 由模型、工具、状态和 Runtime 组成。"
        else:
            content = f"写作草稿：根据资料整理“{prompt}”。"
        return AgentMessage(
            sender=agent,
            recipient="runtime",
            content=content,
            usage_tokens=max(1, len(content) // 4),
            metadata={"framework": "offline"},
        )


def _build_adapter(name: str, *, stream: bool) -> Any:
    if name == "offline":
        return OfflineAsyncAdapter()
    if name == "openai":
        from integrations.openai_compatible import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter.from_environment(stream=stream)
    if name == "autogen":
        from integrations.autogen_adapter import AutoGenAdapter

        return AutoGenAdapter.from_environment(stream=stream)
    if name == "agentscope":
        from integrations.agentscope_adapter import AgentScopeAdapter

        return AgentScopeAdapter.from_environment(stream=stream)
    if name == "langgraph":
        from integrations.langgraph_adapter import LangGraphAdapter

        return LangGraphAdapter.from_environment(stream=stream)
    raise ValueError(f"不支持的 adapter：{name}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="第 6 课：多 Agent 框架与 Runtime")
    parser.add_argument("--demo", action="store_true", help="运行原有同步离线 Demo")
    parser.add_argument("--llm", action="store_true", help="保留原有课程问答入口")
    parser.add_argument(
        "--adapter",
        choices=["offline", "openai", "autogen", "agentscope", "langgraph"],
        help="选择异步 Runtime 适配器；不传则保留旧版离线参数行为",
    )
    parser.add_argument("--query", default="总结 Agent")
    parser.add_argument("--stream", action="store_true", help="输出 Runtime 生命周期/模型增量事件")
    parser.add_argument("--interrupt", action="store_true", help="运行 LangGraph 原生审批中断")
    parser.add_argument("--approval", help="与 --interrupt 一起使用时恢复 LangGraph 审批")
    parser.add_argument("--parallel", action="store_true")
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--stop-after", choices=["research"])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=10)
    parser.add_argument("--max-attempts", type=int, default=3)
    return parser


async def _run_async_mode(args: argparse.Namespace) -> int:
    adapter_name = args.adapter or "offline"
    adapter = _build_adapter(adapter_name, stream=args.stream)
    store = SQLiteCheckpointStore(args.checkpoint or ":memory:")
    runtime = AsyncAgentRuntime(
        adapter,
        checkpoint_store=store,
        timeout_seconds=args.timeout_seconds,
        retry_policy=RetryPolicy(max_attempts=args.max_attempts),
    )

    try:
        if args.interrupt:
            if adapter_name != "langgraph":
                raise ValueError("--interrupt 只有 langgraph adapter 支持")
            paused = await adapter.run_until_interrupt(args.query)
            print(json.dumps(asdict(paused), ensure_ascii=False, indent=2))
            if args.approval is not None:
                resumed = await adapter.resume(paused.run_id, args.approval)
                print(json.dumps(resumed.to_dict(), ensure_ascii=False, indent=2))
            return 0

        if args.resume:
            if not args.run_id:
                raise ValueError("--resume 需要 --run-id")
            result = await runtime.resume(args.run_id)
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            return 0

        if args.stream:
            run_id = ""
            async for event in runtime.stream(args.query):
                run_id = event.run_id
                print(json.dumps(event.to_dict(), ensure_ascii=False))
            if run_id:
                result = store.load(run_id)
                print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            return 0

        result = await runtime.run(args.query)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.status == "completed" else 1
    finally:
        close = getattr(adapter, "aclose", None)
        if close is not None:
            await close()


def _run_legacy_mode(args: argparse.Namespace) -> int:
    if args.llm:
        print(ask_llm("比较 AutoGen、AgentScope 和 LangGraph 时，应该关注哪些架构问题？"))
        return 0
    if args.demo and not any((args.parallel, args.fail, args.stop_after, args.resume, args.checkpoint)):
        print(json.dumps(demo(), ensure_ascii=False, indent=2))
        return 0

    store = SQLiteCheckpointStore(args.checkpoint or ":memory:")
    if args.resume:
        if not args.run_id:
            raise ValueError("--resume 需要 --run-id")
        result = AgentRuntime(build_adapters()[0], checkpoint_store=store).resume(args.run_id)
    else:
        adapter = ScriptedAdapter(fail_on="research" if args.fail else None)
        runtime = AgentRuntime(adapter, checkpoint_store=store)
        if args.parallel:
            result = runtime.run_parallel("总结 Agent")
        else:
            result = runtime.run_serial("总结 Agent", stop_after=args.stop_after)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status in {"completed", "paused"} else 1


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.adapter is None:
            return _run_legacy_mode(args)
        if args.demo:
            # --demo is intentionally independent of every optional SDK.
            print(json.dumps(demo(), ensure_ascii=False, indent=2))
            return 0
        return asyncio.run(_run_async_mode(args))
    except (LLMConfigurationError, MissingOptionalDependency, ProviderError, ValueError) as error:
        print(f"执行失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
