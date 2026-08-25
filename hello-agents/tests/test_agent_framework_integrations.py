import importlib.util
import asyncio
from contextlib import redirect_stderr
import io
import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch


PROJECT = Path(__file__).resolve().parents[1] / "projects" / "06-agent-frameworks"
INTEGRATIONS = PROJECT / "integrations"
COMMON = INTEGRATIONS / "common.py"
RETRY = PROJECT / "retry.py"
OPENAI_ADAPTER = INTEGRATIONS / "openai_compatible.py"
ASYNC_RUNTIME = PROJECT / "async_runtime.py"
AUTOGEN_ADAPTER = INTEGRATIONS / "autogen_adapter.py"
AGENTSCOPE_ADAPTER = INTEGRATIONS / "agentscope_adapter.py"
LANGGRAPH_ADAPTER = INTEGRATIONS / "langgraph_adapter.py"
MAIN = PROJECT / "main.py"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))
if str(PROJECT.parent) not in sys.path:
    sys.path.insert(0, str(PROJECT.parent))


def load_common():
    from integrations import common

    return common


def load_retry():
    if not RETRY.exists():
        raise AssertionError("retry.py must exist")
    spec = importlib.util.spec_from_file_location(
        "agent_framework_retry",
        RETRY,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 retry.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_openai_adapter():
    if not OPENAI_ADAPTER.exists():
        raise AssertionError("openai_compatible.py must exist")
    spec = importlib.util.spec_from_file_location(
        "agent_framework_openai_compatible",
        OPENAI_ADAPTER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 openai_compatible.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_async_runtime():
    if not ASYNC_RUNTIME.exists():
        raise AssertionError("async_runtime.py must exist")
    spec = importlib.util.spec_from_file_location(
        "agent_framework_async_runtime",
        ASYNC_RUNTIME,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 async_runtime.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_autogen_adapter():
    if not AUTOGEN_ADAPTER.exists():
        raise AssertionError("autogen_adapter.py must exist")
    spec = importlib.util.spec_from_file_location(
        "agent_framework_autogen_adapter",
        AUTOGEN_ADAPTER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 autogen_adapter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_agentscope_adapter():
    if not AGENTSCOPE_ADAPTER.exists():
        raise AssertionError("agentscope_adapter.py must exist")
    spec = importlib.util.spec_from_file_location(
        "agent_framework_agentscope_adapter",
        AGENTSCOPE_ADAPTER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 agentscope_adapter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_langgraph_adapter():
    if not LANGGRAPH_ADAPTER.exists():
        raise AssertionError("langgraph_adapter.py must exist")
    spec = importlib.util.spec_from_file_location(
        "agent_framework_langgraph_adapter",
        LANGGRAPH_ADAPTER,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 langgraph_adapter.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_lesson_main():
    """按绝对路径加载第 6 课 CLI，避免其他课程的 main.py 污染 sys.modules。"""
    spec = importlib.util.spec_from_file_location("agent_framework_lesson_main", MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载第 6 课 main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError):
        return False


class FakeCompletionClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="真实回答"),
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=4,
                completion_tokens=6,
                total_tokens=10,
            ),
        )


class FakeStream:
    def __init__(self, chunks):
        self.chunks = chunks

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        for chunk in self.chunks:
            yield chunk


class FakeStreamingClient:
    def __init__(self):
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        return FakeStream(
            [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="真实"))
                    ]
                ),
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(delta=SimpleNamespace(content="回答"))
                    ]
                ),
            ]
        )


class FakeErrorClient:
    def __init__(self, message):
        self.message = message
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kwargs):
        raise RuntimeError(self.message)


class FakeAutoGenAgent:
    def __init__(self, name, model_client, system_message):
        self.name = name
        self.model_client = model_client
        self.system_message = system_message

    async def run(self, task):
        return SimpleNamespace(
            messages=[
                SimpleNamespace(
                    content="AutoGen 回答",
                    models_usage=SimpleNamespace(
                        prompt_tokens=2,
                        completion_tokens=3,
                    ),
                )
            ]
        )

    async def run_stream(self, task):
        yield SimpleNamespace(content="中间消息")
        yield SimpleNamespace(content="AutoGen 最终回答")


class FakeAgentScopeAgent:
    def __init__(self, name, sys_prompt, model, formatter):
        self.name = name
        self.sys_prompt = sys_prompt
        self.model = model
        self.formatter = formatter
        self.queue = None

    def set_msg_queue_enabled(self, enabled, queue=None):
        self.queue = queue if enabled else None

    async def __call__(self, message):
        if self.queue is not None:
            await self.queue.put(
                (SimpleNamespace(content="中间消息"), False, None)
            )
            await self.queue.put(
                (SimpleNamespace(content="AgentScope 最终回答"), True, None)
            )
        return SimpleNamespace(
            content="AgentScope 回答",
            usage=SimpleNamespace(input_tokens=2, output_tokens=3),
        )


class FakeChatModel:
    async def ainvoke(self, prompt):
        return SimpleNamespace(content=f"LangGraph 回答：{prompt}")

    async def astream(self, prompt):
        yield SimpleNamespace(content="LangGraph ")
        yield SimpleNamespace(content="流式回答")


class ScriptedAsyncAdapter:
    capabilities = None

    def __init__(self, common):
        self.common = common
        self.calls = []
        self.capabilities = common.AdapterCapabilities(
            supports_streaming=False,
            supports_cancellation=True,
        )

    async def respond(self, agent, prompt, *, on_event=None, cancel_token=None):
        self.calls.append(agent)
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
        return self.common.AgentMessage(
            sender=agent,
            recipient="runtime",
            content=f"{agent}: {prompt}",
            usage_tokens=2,
        )


class BlockingAsyncAdapter(ScriptedAsyncAdapter):
    def __init__(self, common):
        super().__init__(common)
        self.started = asyncio.Event()

    async def respond(self, agent, prompt, *, on_event=None, cancel_token=None):
        self.started.set()
        await asyncio.Event().wait()
        return await super().respond(
            agent,
            prompt,
            on_event=on_event,
            cancel_token=cancel_token,
        )


class FailOnceAsyncAdapter(ScriptedAsyncAdapter):
    def __init__(self, common):
        super().__init__(common)
        self.attempts = 0

    async def respond(self, agent, prompt, *, on_event=None, cancel_token=None):
        self.attempts += 1
        if agent == "research" and self.attempts == 1:
            raise self.common.RunTimeout("temporary timeout")
        return await super().respond(
            agent,
            prompt,
            on_event=on_event,
            cancel_token=cancel_token,
        )


class AgentFrameworkIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.common = load_common()

    def test_async_message_is_serializable(self):
        self.assertTrue(COMMON.exists(), "common.py must exist")
        message = self.common.AgentMessage(
            sender="research",
            recipient="runtime",
            content="result",
            usage_tokens=3,
        )

        payload = message.to_dict()

        self.assertEqual("research", payload["sender"])
        self.assertEqual("result", payload["content"])
        self.assertEqual(3, payload["usage_tokens"])

    def test_missing_optional_dependency_has_actionable_error(self):
        self.assertTrue(COMMON.exists(), "common.py must exist")
        error = self.common.MissingOptionalDependency(
            "autogen",
            "pip install -r requirements-frameworks.txt",
        )

        self.assertIn("autogen", str(error))
        self.assertIn("pip install", str(error))

    def test_metadata_redaction_never_returns_api_key(self):
        self.assertTrue(COMMON.exists(), "common.py must exist")
        result = self.common.redact_metadata(
            {
                "api_key": "secret",
                "authorization": "Bearer secret",
                "model": "demo",
            }
        )

        self.assertEqual("[REDACTED]", result["api_key"])
        self.assertEqual("[REDACTED]", result["authorization"])
        self.assertEqual("demo", result["model"])

    def test_timeout_and_transient_status_are_retryable(self):
        self.assertTrue(RETRY.exists(), "retry.py must exist")
        retry = load_retry()

        self.assertTrue(retry.is_retryable_error(self.common.RunTimeout("slow")))
        self.assertTrue(
            retry.is_retryable_error(retry.ProviderError("rate", status_code=429))
        )
        self.assertTrue(
            retry.is_retryable_error(retry.ProviderError("server", status_code=503))
        )

    def test_auth_errors_and_cancel_are_not_retryable(self):
        self.assertTrue(RETRY.exists(), "retry.py must exist")
        retry = load_retry()

        self.assertFalse(
            retry.is_retryable_error(retry.ProviderError("bad token", status_code=401))
        )
        self.assertFalse(
            retry.is_retryable_error(retry.ProviderError("forbidden", status_code=403))
        )
        self.assertFalse(
            retry.is_retryable_error(self.common.RunCancelled("cancelled"))
        )

    def test_backoff_is_bounded_without_jitter(self):
        self.assertTrue(RETRY.exists(), "retry.py must exist")
        retry = load_retry()
        policy = retry.RetryPolicy(
            max_attempts=4,
            base_delay=0.1,
            max_delay=0.25,
            jitter=0,
        )

        self.assertEqual(0.1, policy.delay_for(1))
        self.assertEqual(0.2, policy.delay_for(2))
        self.assertEqual(0.25, policy.delay_for(3))


class RetryAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_retry_async_retries_transient_error_and_reports_attempt(self):
        retry = load_retry()
        attempts = []
        delays = []
        callbacks = []

        async def operation(attempt):
            attempts.append(attempt)
            if len(attempts) == 1:
                raise retry.ProviderError("temporary", status_code=503)
            return "ok"

        async def no_sleep(delay):
            delays.append(delay)

        result = await retry.retry_async(
            operation,
            policy=retry.RetryPolicy(
                max_attempts=2,
                base_delay=0.25,
                max_delay=1,
                jitter=0,
            ),
            on_retry=lambda attempt, error, delay: callbacks.append(
                (attempt, str(error), delay)
            ),
            sleep=no_sleep,
        )

        self.assertEqual("ok", result)
        self.assertEqual([1, 2], attempts)
        self.assertEqual([0.25], delays)
        self.assertEqual([(1, "temporary", 0.25)], callbacks)


class OpenAICompatibleAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_openai_adapter_normalizes_completion_and_usage(self):
        adapter_module = load_openai_adapter()
        adapter = adapter_module.OpenAICompatibleAdapter(
            client=FakeCompletionClient(),
            model="demo-model",
            system="你是测试 Agent",
        )

        message = await adapter.respond("research", "问题")

        self.assertEqual("真实回答", message.content)
        self.assertEqual(10, message.usage_tokens)
        self.assertEqual("demo-model", message.metadata["model"])

    async def test_openai_adapter_emits_stream_deltas(self):
        adapter_module = load_openai_adapter()
        events = []
        adapter = adapter_module.OpenAICompatibleAdapter(
            client=FakeStreamingClient(),
            model="demo-model",
            stream=True,
        )

        result = await adapter.respond(
            "research",
            "问题",
            on_event=lambda event: events.append(event),
        )

        self.assertEqual("真实回答", result.content)
        self.assertEqual(
            ["真实", "回答"],
            [event.metadata["delta"] for event in events],
        )

    async def test_openai_adapter_redacts_configured_key_from_provider_error(self):
        adapter_module = load_openai_adapter()
        adapter = adapter_module.OpenAICompatibleAdapter(
            client=FakeErrorClient("request failed: secret-key"),
            model="demo-model",
            api_key_for_redaction="secret-key",
        )

        with self.assertRaises(adapter_module.ProviderError) as context:
            await adapter.respond("research", "问题")

        self.assertNotIn("secret-key", str(context.exception))
        self.assertIn("[REDACTED]", str(context.exception))


class AsyncRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.common = load_common()

    async def test_async_runtime_emits_ordered_serial_events(self):
        self.assertTrue(ASYNC_RUNTIME.exists(), "async_runtime.py must exist")
        runtime_module = load_async_runtime()
        runtime = runtime_module.AsyncAgentRuntime(
            ScriptedAsyncAdapter(self.common),
            sleep=runtime_module.noop_sleep,
        )

        result, events = await runtime.run_with_events("总结 Agent")

        self.assertEqual("completed", result.status)
        phases = [event.phase for event in events]
        self.assertEqual("run_started", phases[0])
        self.assertEqual("run_completed", phases[-1])
        self.assertLess(phases.index("node_started"), phases.index("node_completed"))

    async def test_cancel_stops_next_node_and_saves_cancelled_checkpoint(self):
        self.assertTrue(ASYNC_RUNTIME.exists(), "async_runtime.py must exist")
        runtime_module = load_async_runtime()
        adapter = BlockingAsyncAdapter(self.common)
        runtime = runtime_module.AsyncAgentRuntime(adapter)
        task = asyncio.create_task(runtime.run("总结 Agent"))
        await adapter.started.wait()

        await runtime.cancel(task)
        result = await task

        self.assertEqual("cancelled", result.status)
        self.assertNotIn("writing", result.completed_nodes)
        restored = runtime.checkpoint_store.load(result.run_id)
        self.assertEqual("cancelled", restored.status)

    async def test_retry_event_is_emitted_and_success_is_returned(self):
        self.assertTrue(ASYNC_RUNTIME.exists(), "async_runtime.py must exist")
        runtime_module = load_async_runtime()
        runtime = runtime_module.AsyncAgentRuntime(
            FailOnceAsyncAdapter(self.common),
            retry_policy=runtime_module.RetryPolicy(
                max_attempts=2,
                base_delay=0,
                max_delay=0,
                jitter=0,
            ),
            sleep=runtime_module.noop_sleep,
        )

        result, events = await runtime.run_with_events("总结 Agent")

        self.assertEqual("completed", result.status)
        self.assertTrue(any(event.phase == "retry_scheduled" for event in events))

    async def test_stream_yields_lifecycle_events(self):
        runtime_module = load_async_runtime()
        runtime = runtime_module.AsyncAgentRuntime(
            ScriptedAsyncAdapter(self.common),
            sleep=runtime_module.noop_sleep,
        )

        events = [event async for event in runtime.stream("总结 Agent")]

        self.assertEqual("run_started", events[0].phase)
        self.assertEqual("run_completed", events[-1].phase)

    async def test_resume_skips_completed_research_node(self):
        runtime_module = load_async_runtime()
        adapter = ScriptedAsyncAdapter(self.common)
        runtime = runtime_module.AsyncAgentRuntime(
            adapter,
            sleep=runtime_module.noop_sleep,
        )
        state = runtime_module.AgentState(
            task="总结 Agent",
            status="paused",
            completed_nodes=["research"],
            results={"research": "已有研究结果"},
        )
        runtime.checkpoint_store.save(state)

        resumed = await runtime.resume(state.run_id)

        self.assertEqual("completed", resumed.status)
        self.assertEqual(["writing"], adapter.calls)


class AutoGenAdapterTests(unittest.TestCase):
    @unittest.skipUnless(
        has_module("autogen_agentchat"),
        "AutoGen optional dependency is not installed",
    )
    def test_from_environment_constructs_official_client_without_network(self):
        adapter_module = load_autogen_adapter()
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "dummy-key",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "OPENAI_MODEL": "dummy-model",
            },
            clear=False,
        ):
            adapter = adapter_module.AutoGenAdapter.from_environment()

        self.assertEqual("OpenAIChatCompletionClient", type(adapter.model_client).__name__)
        asyncio.run(adapter.aclose())

    def test_autogen_adapter_normalizes_injected_agent(self):
        adapter_module = load_autogen_adapter()
        adapter = adapter_module.AutoGenAdapter(
            model_client=object(),
            agent_factory=FakeAutoGenAgent,
        )

        message = asyncio.run(adapter.respond("research", "问题"))

        self.assertEqual("AutoGen 回答", message.content)
        self.assertEqual(5, message.usage_tokens)
        self.assertEqual("autogen", message.metadata["framework"])

    def test_autogen_adapter_forwards_stream_messages(self):
        adapter_module = load_autogen_adapter()
        events = []
        adapter = adapter_module.AutoGenAdapter(
            model_client=object(),
            agent_factory=FakeAutoGenAgent,
            stream=True,
        )

        message = asyncio.run(
            adapter.respond(
                "research",
                "问题",
                on_event=lambda event: events.append(event),
            )
        )

        self.assertEqual("AutoGen 最终回答", message.content)
        self.assertEqual(
            ["中间消息", "AutoGen 最终回答"],
            [event.metadata["delta"] for event in events],
        )

    @unittest.skipUnless(
        not has_module("autogen_agentchat"),
        "AutoGen is installed; missing-dependency path is not applicable",
    )
    def test_missing_autogen_dependency_has_actionable_error(self):
        adapter_module = load_autogen_adapter()

        with self.assertRaises(adapter_module.MissingOptionalDependency) as context:
            adapter_module.AutoGenAdapter.from_environment()

        self.assertIn("autogen", str(context.exception).lower())
        self.assertIn("requirements-autogen", str(context.exception))

    @unittest.skipUnless(
        has_module("autogen_agentchat"),
        "AutoGen optional dependency is not installed",
    )
    def test_autogen_adapter_loads_official_agentchat_api(self):
        adapter_module = load_autogen_adapter()
        sdk = adapter_module.load_autogen_sdk()

        self.assertTrue(hasattr(sdk, "AssistantAgent"))
        self.assertTrue(hasattr(sdk, "OpenAIChatCompletionClient"))

    @unittest.skipUnless(
        has_module("autogen_agentchat")
        and os.getenv("RUN_REAL_AGENT_SMOKE") == "1",
        "AutoGen real smoke test disabled",
    )
    def test_autogen_real_smoke(self):
        adapter_module = load_autogen_adapter()
        message = asyncio.run(
            adapter_module.AutoGenAdapter.from_environment().respond(
                "research",
                "用一句话解释 Agent",
            )
        )

        self.assertTrue(message.content)


class AgentScopeAdapterTests(unittest.TestCase):
    @unittest.skipUnless(
        has_module("agentscope"),
        "AgentScope optional dependency is not installed",
    )
    def test_from_environment_constructs_official_model_without_network(self):
        adapter_module = load_agentscope_adapter()
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "dummy-key",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "OPENAI_MODEL": "dummy-model",
            },
            clear=False,
        ):
            adapter = adapter_module.AgentScopeAdapter.from_environment()

        self.assertEqual("OpenAIChatModel", type(adapter.model).__name__)
        asyncio.run(adapter.aclose())

    def test_agentscope_adapter_normalizes_injected_agent(self):
        adapter_module = load_agentscope_adapter()
        adapter = adapter_module.AgentScopeAdapter(
            model=object(),
            formatter=object(),
            agent_factory=FakeAgentScopeAgent,
        )

        message = asyncio.run(adapter.respond("research", "问题"))

        self.assertEqual("AgentScope 回答", message.content)
        self.assertEqual(5, message.usage_tokens)
        self.assertEqual("agentscope", message.metadata["framework"])

    def test_agentscope_adapter_forwards_message_queue_stream(self):
        adapter_module = load_agentscope_adapter()
        events = []
        adapter = adapter_module.AgentScopeAdapter(
            model=object(),
            formatter=object(),
            agent_factory=FakeAgentScopeAgent,
            stream=True,
        )

        message = asyncio.run(
            adapter.respond(
                "research",
                "问题",
                on_event=lambda event: events.append(event),
            )
        )

        self.assertEqual("AgentScope 回答", message.content)
        self.assertEqual(
            ["中间消息", "AgentScope 最终回答"],
            [event.metadata["delta"] for event in events],
        )

    @unittest.skipUnless(
        not has_module("agentscope"),
        "AgentScope is installed; missing-dependency path is not applicable",
    )
    def test_missing_agentscope_dependency_has_actionable_error(self):
        adapter_module = load_agentscope_adapter()

        with self.assertRaises(adapter_module.MissingOptionalDependency) as context:
            adapter_module.AgentScopeAdapter.from_environment()

        self.assertIn("agentscope", str(context.exception).lower())
        self.assertIn("requirements-agentscope", str(context.exception))

    @unittest.skipUnless(
        has_module("agentscope"),
        "AgentScope optional dependency is not installed",
    )
    def test_agentscope_adapter_loads_official_api(self):
        adapter_module = load_agentscope_adapter()
        sdk = adapter_module.load_agentscope_sdk()

        self.assertTrue(hasattr(sdk, "Msg"))
        self.assertTrue(hasattr(sdk, "ReActAgent"))

    @unittest.skipUnless(
        has_module("agentscope")
        and os.getenv("RUN_REAL_AGENT_SMOKE") == "1",
        "AgentScope real smoke test disabled",
    )
    def test_agentscope_real_smoke(self):
        adapter_module = load_agentscope_adapter()
        message = asyncio.run(
            adapter_module.AgentScopeAdapter.from_environment().respond(
                "research",
                "用一句话解释 Agent",
            )
        )

        self.assertTrue(message.content)


class LangGraphAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_from_environment_constructs_openai_compatible_model_without_network(self):
        adapter_module = load_langgraph_adapter()
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "dummy-key",
                "OPENAI_BASE_URL": "https://example.invalid/v1",
                "OPENAI_MODEL": "dummy-model",
            },
            clear=False,
        ):
            adapter = adapter_module.LangGraphAdapter.from_environment()

        self.assertEqual("_AdapterModel", type(adapter.model).__name__)
        await adapter.aclose()

    async def test_langgraph_adapter_loads_official_stategraph_api(self):
        adapter_module = load_langgraph_adapter()
        sdk = adapter_module.load_langgraph_sdk()

        self.assertTrue(hasattr(sdk, "StateGraph"))
        self.assertTrue(hasattr(sdk, "MemorySaver"))
        self.assertTrue(hasattr(sdk, "interrupt"))
        self.assertTrue(hasattr(sdk, "Command"))

    async def test_langgraph_adapter_routes_with_fake_model(self):
        adapter_module = load_langgraph_adapter()
        adapter = adapter_module.LangGraphAdapter(model=FakeChatModel())

        result = await adapter.respond("research", "总结 Agent")

        self.assertIn("LangGraph 回答", result.content)
        self.assertEqual("langgraph", result.metadata["framework"])

    async def test_langgraph_interrupt_resume_uses_command(self):
        adapter_module = load_langgraph_adapter()
        adapter = adapter_module.LangGraphAdapter(model=FakeChatModel())

        paused = await adapter.run_until_interrupt("需要审批")
        self.assertTrue(paused.interrupted)

        resumed = await adapter.resume(paused.run_id, "approved")

        self.assertEqual("completed", resumed.status)
        self.assertEqual("approved", resumed.results["approval"])


class LessonSixCliTests(unittest.TestCase):
    def test_cli_supports_explicit_offline_adapter(self):
        completed = subprocess.run(
            [sys.executable, str(MAIN), "--adapter", "offline", "--query", "解释 Agent"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn('"status": "completed"', completed.stdout)

    def test_cli_real_adapter_reports_missing_configuration_without_secret(self):
        lesson_main = load_lesson_main()

        error_output = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [str(MAIN), "--adapter", "openai", "--query", "解释 Agent"],
            ),
            patch.object(
                lesson_main,
                "_build_adapter",
                side_effect=lesson_main.LLMConfigurationError(
                    "真实 LLM 模式缺少配置：OPENAI_API_KEY"
                ),
            ),
            redirect_stderr(error_output),
        ):
            return_code = lesson_main.main()

        self.assertNotEqual(0, return_code)
        self.assertIn("OPENAI_API_KEY", error_output.getvalue())
        self.assertNotIn("sk-", error_output.getvalue())


if __name__ == "__main__":
    unittest.main()
