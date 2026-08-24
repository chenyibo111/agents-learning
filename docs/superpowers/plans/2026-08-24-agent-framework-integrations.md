# Agent Framework Integrations Implementation Plan

> 执行状态（2026-08-24）：Task 1～9 的代码、文档、离线验证和安全检查已完成；Task 9 的真实网络 smoke test 按设计未执行，以避免未经确认产生模型费用。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 在保留第六课离线 Demo 的前提下，接入 OpenAI-compatible 真实 LLM、官方 AutoGen、AgentScope 和 LangGraph，并提供异步流式事件、取消、超时、重试和 checkpoint 恢复。

**Architecture:** 保留现有 frameworks.py 的同步离线实现；新增独立的异步协议、Adapter 和 Runtime。第三方 SDK 只在对应 Adapter 内懒加载，所有结果转换为课程内的消息、状态、事件和统一异常。真实 SDK 测试与离线测试分离，默认不产生网络请求和模型费用。

**Tech Stack:** Python 3.11、标准库 asyncio/sqlite3、已有 openai SDK、可选 autogen-agentchat/autogen-ext、可选 agentscope、可选 langgraph、unittest。

---

## 文件边界

新增或修改：

    hello-agents/projects/06-agent-frameworks/
    ├── frameworks.py                  # 既有离线同步实现，不重写
    ├── async_runtime.py               # 异步运行、事件、取消、超时、checkpoint
    ├── retry.py                       # 错误分类、指数退避、重试策略
    ├── integrations/
    │   ├── __init__.py
    │   ├── common.py                  # 协议、能力、异常、脱敏
    │   ├── openai_compatible.py       # 真实 OpenAI-compatible LLM
    │   ├── autogen_adapter.py         # 官方 AutoGen
    │   ├── agentscope_adapter.py      # 官方 AgentScope
    │   └── langgraph_adapter.py       # 官方 LangGraph
    ├── main.py                        # 保留离线参数并增加真实模式
    └── README.md                      # 安装和运行说明

    hello-agents/requirements-frameworks.txt
    hello-agents/tests/test_agent_framework_integrations.py

每个 Adapter 只负责第三方 SDK 交互和返回值归一化；AsyncAgentRuntime 只负责工作流生命周期；retry.py 只负责重试决策。

### Task 1: 统一异步协议和可选依赖边界

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/integrations/__init__.py
- Create: hello-agents/projects/06-agent-frameworks/integrations/common.py
- Test: hello-agents/tests/test_agent_framework_integrations.py

- [x] **Step 1: 写失败测试**

    def test_async_message_is_serializable(self):
        message = AgentMessage("research", "runtime", "result", usage_tokens=3)
        self.assertEqual("research", message.to_dict()["sender"])
        self.assertEqual(3, message.to_dict()["usage_tokens"])

    def test_missing_optional_dependency_has_actionable_error(self):
        error = MissingOptionalDependency("autogen", "pip install -r requirements-frameworks.txt")
        self.assertIn("autogen", str(error))
        self.assertIn("pip install", str(error))

    def test_metadata_redaction_never_returns_api_key(self):
        result = redact_metadata({"api_key": "secret", "model": "demo"})
        self.assertEqual("[REDACTED]", result["api_key"])
        self.assertEqual("demo", result["model"])

- [x] **Step 2: 运行测试确认 RED**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：因为 integrations.common 尚不存在而失败。

- [ ] **Step 3: 实现最小协议**

common.py 定义 AgentMessage、AgentEvent、AdapterCapabilities、AsyncAgentAdapter Protocol、CancellationToken Protocol、AdapterError、MissingOptionalDependency、RunCancelled、RunTimeout 和 redact_metadata。

核心接口：

    class AsyncAgentAdapter(Protocol):
        capabilities: AdapterCapabilities

        async def respond(
            self, agent: str, prompt: str, *,
            on_event: EventSink | None = None,
            cancel_token: CancellationToken | None = None,
        ) -> AgentMessage: ...

AgentEvent 至少包含 run_id、node、phase、timestamp、duration_ms、usage_tokens、attempt、metadata、error。协议不能导入任何第三方 SDK。

- [ ] **Step 4: 运行 focused tests 确认 GREEN**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：协议、安全和序列化测试通过。

- [ ] **Step 5: 验证既有离线测试**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_frameworks.py -v

预期：既有六个测试继续通过。

### Task 2: 重试分类和指数退避

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/retry.py
- Modify: hello-agents/projects/06-agent-frameworks/integrations/common.py
- Test: hello-agents/tests/test_agent_framework_integrations.py

- [ ] **Step 1: 写失败测试**

    def test_timeout_and_transient_status_are_retryable(self):
        self.assertTrue(is_retryable_error(RunTimeout("slow")))
        self.assertTrue(is_retryable_error(ProviderError("rate", status_code=429)))
        self.assertTrue(is_retryable_error(ProviderError("server", status_code=503)))

    def test_auth_errors_and_cancel_are_not_retryable(self):
        self.assertFalse(is_retryable_error(ProviderError("bad token", status_code=401)))
        self.assertFalse(is_retryable_error(ProviderError("forbidden", status_code=403)))
        self.assertFalse(is_retryable_error(RunCancelled("cancelled")))

    def test_backoff_is_bounded_without_jitter(self):
        policy = RetryPolicy(max_attempts=4, base_delay=0.1, max_delay=0.25, jitter=0)
        self.assertEqual(0.1, policy.delay_for(1))
        self.assertEqual(0.2, policy.delay_for(2))
        self.assertEqual(0.25, policy.delay_for(3))

- [ ] **Step 2: 运行测试确认 RED**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：因为重试类型和分类函数尚不存在而失败。

- [ ] **Step 3: 实现最小重试模块**

定义 ProviderError(message, status_code=None)、RetryPolicy、is_retryable_error 和 retry_async。默认可重试连接异常、超时、429、500、502、503、504；默认不重试 401、403、参数错误、权限错误和 RunCancelled。

重试循环必须把 sleep 函数作为依赖注入，以便测试不真实等待；每次重试通过回调发出 attempt、错误类型和 delay，不携带请求头、Key 或完整敏感响应。

- [ ] **Step 4: 验证 GREEN**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

### Task 3: OpenAI-compatible 异步 LLM Adapter

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/integrations/openai_compatible.py
- Modify: hello-agents/projects/common/llm.py
- Test: hello-agents/tests/test_agent_framework_integrations.py

- [ ] **Step 1: 写 fake-client 失败测试**

    async def test_openai_adapter_normalizes_completion_and_usage(self):
        client = FakeAsyncClient(
            content="真实回答",
            usage={"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10},
        )
        adapter = OpenAICompatibleAdapter(client=client, model="demo-model")
        message = await adapter.respond("research", "问题")
        self.assertEqual("真实回答", message.content)
        self.assertEqual(10, message.usage_tokens)

    async def test_openai_adapter_emits_stream_deltas(self):
        client = FakeStreamingClient(["真实", "回答"])
        events = []
        adapter = OpenAICompatibleAdapter(client=client, model="demo-model")
        result = await adapter.respond(
            "research", "问题", on_event=lambda event: events.append(event)
        )
        self.assertEqual("真实回答", result.content)
        self.assertEqual(["真实", "回答"], [event.metadata["delta"] for event in events])

- [ ] **Step 2: 运行测试确认 RED**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：Adapter 尚不存在而失败。

- [ ] **Step 3: 实现 Adapter**

Adapter 在没有注入 client 时懒加载 AsyncOpenAI，并读取现有 OPENAI_BASE_URL、OPENAI_API_KEY、OPENAI_MODEL 配置；注入 fake client 时完全不读取网络配置。

实现非流式和流式 chat completion，转换 content 和 usage；流式期间每个增量产生 message_delta；在调用前和每个 chunk 前检查 CancellationToken；异常转换为 ProviderError；API Key 不进入 metadata、事件或异常文本。common/llm.py 只增加异步配置/客户端辅助函数，保留 ask_llm() 的兼容行为。

- [ ] **Step 4: 验证 focused tests 和既有 LLM 测试**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py hello-agents/tests/test_llm_foundation.py -v

预期：无需网络即可通过。

### Task 4: Async Runtime、事件流、取消、超时和 checkpoint

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/async_runtime.py
- Modify: hello-agents/projects/06-agent-frameworks/integrations/common.py
- Test: hello-agents/tests/test_agent_framework_integrations.py

- [ ] **Step 1: 写失败测试**

    async def test_async_runtime_emits_ordered_serial_events(self):
        runtime = AsyncAgentRuntime(ScriptedAsyncAdapter(), sleep=immediate_sleep)
        events = [event async for event in runtime.stream("总结 Agent")]
        self.assertEqual("run_started", events[0].phase)
        self.assertEqual("run_completed", events[-1].phase)

    async def test_cancel_stops_next_node_and_saves_cancelled_checkpoint(self):
        adapter = BlockingAsyncAdapter()
        runtime = AsyncAgentRuntime(adapter)
        task = asyncio.create_task(runtime.run("总结 Agent"))
        await adapter.started.wait()
        await runtime.cancel(task)
        result = await task
        self.assertEqual("cancelled", result.status)
        self.assertNotIn("writing", result.completed_nodes)

    async def test_retry_event_is_emitted_and_success_is_returned(self):
        runtime = AsyncAgentRuntime(
            FailOnceAsyncAdapter(),
            retry_policy=RetryPolicy(max_attempts=2),
            sleep=immediate_sleep,
        )
        result, events = await runtime.run_with_events("总结 Agent")
        self.assertEqual("completed", result.status)
        self.assertTrue(any(event.phase == "retry_scheduled" for event in events))

- [ ] **Step 2: 运行测试确认 RED**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：AsyncAgentRuntime 和测试适配器尚不存在而失败。

- [ ] **Step 3: 实现 Async Runtime**

提供 async run(task)、run_with_events(task)、stream(task)、resume(run_id) 和 cancel(task)。Runtime 必须：

- 新建带 UUID 的可序列化状态；
- 按 research → writing 执行；
- 发出 run_started、node_started、message_delta、message_completed、node_completed、run_completed；
- 每个节点完成后保存 SQLite checkpoint；
- 使用 asyncio.wait_for 处理节点 timeout；
- 对 RunCancelled 保存 cancelled 状态且不重试；
- 只通过 retry_async 重试可恢复错误；
- 记录 attempt、duration、usage 和脱敏 metadata；
- 失败时保存 failed 状态和 node_failed；
- resume 时跳过 completed_nodes；
- 通过队列或异步生成器发送事件，事件消费者异常不能改变任务结果；
- 不导入 AutoGen、AgentScope、LangGraph 或 OpenAI SDK。

- [ ] **Step 4: 验证异步和既有测试**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py hello-agents/tests/test_agent_frameworks.py -v

预期：新旧测试全部通过。

### Task 5: 官方 AutoGen Adapter

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/integrations/autogen_adapter.py
- Create: hello-agents/requirements-frameworks.txt
- Modify: hello-agents/tests/test_agent_framework_integrations.py

- [ ] **Step 1: 写依赖门控测试**

    @unittest.skipUnless(has_module("autogen_agentchat"), "AutoGen optional dependency is not installed")
    def test_autogen_adapter_imports_official_api(self):
        adapter = AutoGenAdapter.from_environment()
        self.assertTrue(adapter.capabilities.supports_streaming)

    @unittest.skipUnless(os.getenv("RUN_REAL_AGENT_SMOKE") == "1", "real smoke test disabled")
    async def test_autogen_real_smoke(self):
        message = await AutoGenAdapter.from_environment().respond(
            "research", "用一句话解释 Agent"
        )
        self.assertTrue(message.content)

- [ ] **Step 2: 验证缺依赖行为**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：未安装时只跳过或返回明确 MissingOptionalDependency，不得在测试收集阶段崩溃。

- [ ] **Step 3: 实现官方 Adapter**

使用官方 AgentChat 和 OpenAI 扩展包，在 Adapter 内构造 OpenAIChatCompletionClient、AssistantAgent、有限终止条件和团队运行；使用官方异步运行 API；归一化最终消息和 usage；将可用流式消息转换为 common 事件；统一异常；必要时关闭 client/team。

不要导入旧版 autogen 包作为 fallback，避免与官方 autogen-agentchat API 冲突。Adapter 只声明当前安装版本实际支持的能力。

- [ ] **Step 4: 记录依赖版本并验证**

在 requirements-frameworks.txt 和 README 中记录实现时验证的包名/版本。默认测试不调用真实网络；RUN_REAL_AGENT_SMOKE=1 才允许 smoke test。

### Task 6: 官方 AgentScope Adapter

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/integrations/agentscope_adapter.py
- Modify: hello-agents/requirements-frameworks.txt
- Modify: hello-agents/tests/test_agent_framework_integrations.py

- [ ] **Step 1: 写依赖门控测试**

    @unittest.skipUnless(has_module("agentscope"), "AgentScope optional dependency is not installed")
    def test_agentscope_adapter_imports_official_api(self):
        adapter = AgentScopeAdapter.from_environment()
        self.assertTrue(hasattr(adapter, "respond"))

    @unittest.skipUnless(os.getenv("RUN_REAL_AGENT_SMOKE") == "1", "real smoke test disabled")
    async def test_agentscope_real_smoke(self):
        message = await AgentScopeAdapter.from_environment().respond(
            "research", "用一句话解释 Agent"
        )
        self.assertTrue(message.content)

- [ ] **Step 2: 验证 RED/skip**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：缺依赖时清晰跳过；不能因为可选包缺少而导致整个模块导入失败。

- [ ] **Step 3: 实现官方 Adapter**

所有 AgentScope 导入和版本检查集中在该 Adapter；创建官方模型、Agent 和 Message；使用当前已验证版本的 async invocation；转换返回消息和 usage；若版本支持流式则转发 message_delta；取消和 provider 错误转换为 common 异常；准确报告原生 interrupt/checkpoint 能力，不用 Runtime 取消冒充审批中断。

- [ ] **Step 4: 验证离线和 gated tests**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py hello-agents/tests/test_agent_frameworks.py -v

### Task 7: 官方 LangGraph StateGraph、中断和恢复

**Files:**

- Create: hello-agents/projects/06-agent-frameworks/integrations/langgraph_adapter.py
- Modify: hello-agents/requirements-frameworks.txt
- Modify: hello-agents/tests/test_agent_framework_integrations.py

- [x] **Step 1: 写失败测试**

    async def test_langgraph_adapter_routes_research_to_writing_with_fake_model(self):
        adapter = LangGraphAdapter(model=FakeChatModel(), checkpointer=InMemoryCheckpointer())
        result = await adapter.respond("research", "总结 Agent")
        self.assertTrue(result.content)

    @unittest.skipUnless(has_native_langgraph_interrupt(), "LangGraph interrupt unavailable")
    async def test_langgraph_interrupt_resume_uses_command(self):
        adapter = LangGraphAdapter(model=FakeChatModel(), checkpointer=InMemoryCheckpointer())
        paused = await adapter.run_until_interrupt("需要审批")
        resumed = await adapter.resume(paused.run_id, "approved")
        self.assertEqual("completed", resumed.status)

- [x] **Step 2: 运行测试确认 RED**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：StateGraph Adapter 尚不存在而失败；API 不可用时仅 capability-gated 测试跳过。

- [x] **Step 3: 实现官方 StateGraph Adapter**

构造 START → research → writing → END 图；使用官方 StateGraph、START、END 和当前版本兼容的 checkpointer；图状态保持可序列化并与 AgentState 转换；支持 ainvoke 和流式 API；审批节点使用官方 interrupt()，恢复使用 Command(resume=...)；图更新和消息 chunk 转换为 common 事件；GraphRecursionError、provider error、cancel 和 timeout 转换为统一异常。

- [x] **Step 4: 验证 LangGraph 和离线测试**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py hello-agents/tests/test_agent_frameworks.py -v

### Task 8: CLI、依赖说明和课程材料

**Files:**

- Modify: hello-agents/projects/06-agent-frameworks/main.py
- Modify: hello-agents/projects/06-agent-frameworks/README.md
- Modify: hello-agents/lessons/06-agent-frameworks.md
- Modify: hello-agents/requirements-frameworks.txt
- Test: hello-agents/tests/test_agent_framework_integrations.py

- [x] **Step 1: 写 CLI 失败测试**

    def test_demo_does_not_require_optional_frameworks(self):
        completed = subprocess.run(
            [sys.executable, str(MAIN), "--demo"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(0, completed.returncode)

    def test_missing_real_adapter_prints_install_hint(self):
        completed = subprocess.run(
            [sys.executable, str(MAIN), "--adapter", "autogen"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn("requirements-frameworks", completed.stdout + completed.stderr)

- [x] **Step 2: 运行测试确认 RED**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

- [x] **Step 3: 实现显式 CLI 模式**

保持 --demo、--parallel、--fail、--stop-after、--resume 兼容；增加 --adapter {offline,openai,autogen,agentscope,langgraph}、--stream、--interrupt、--timeout-seconds、--max-attempts。--demo 永远不导入可选 SDK；真实模式缺配置/缺依赖时快速失败并给出安装提示；输出不得包含 Key 或 Authorization。

- [x] **Step 4: 更新文档**

记录可选安装命令、OPENAI_API_KEY/OPENAI_BASE_URL/OPENAI_MODEL 配置、离线命令、真实 Adapter 命令、显式 smoke test 开关、stream、interrupt/resume、取消、重试和安全说明。

- [x] **Step 5: 运行课程全量测试**

    .venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v

预期：所有离线课程测试通过。

### Task 9: 安全、兼容性和交付验证

**Files:**

- Modify only if needed: Tasks 1–8 files

- [x] **Step 1: 扫描敏感信息**

    rg -n --hidden -g '!*.pyc' -g '!.git/**' -g '!*.sqlite3' \
      'sk-[A-Za-z0-9]|OPENAI_API_KEY=.+|Authorization: Bearer|api_key[[:space:]]*=' \
      hello-agents docs/superpowers/specs docs/superpowers/plans

预期：没有真实 Key；只允许变量名和脱敏占位内容。

- [x] **Step 2: 编译和全量离线验证**

    .venv311/bin/python -m compileall -q hello-agents/projects/06-agent-frameworks hello-agents/tests
    .venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v

- [x] **Step 3: 验证可选导入**

    .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

预期：未安装 SDK 时清晰跳过，已安装 LangGraph 的检查通过。

- [ ] **Step 4: 显式运行真实 smoke test**

    RUN_REAL_AGENT_SMOKE=1 .venv311/bin/python -m unittest hello-agents/tests/test_agent_framework_integrations.py -v

该命令可能产生模型费用，只在用户配置好环境变量并明确运行时执行。

- [x] **Step 5: 检查 diff，不提交**

    git diff --check
    git status --short
    git diff --stat -- hello-agents/projects/06-agent-frameworks hello-agents/tests hello-agents/requirements-frameworks.txt hello-agents/lessons/06-agent-frameworks.md

不得 stage 或 commit，除非用户明确要求。

## 执行顺序

    Task 1 → Task 2 → Task 3 → Task 4
                              ↓
                         阶段 A 基础完成
                              ↓
                    Task 5 → Task 6 → Task 7
                              ↓
                    官方框架和原生能力完成
                              ↓
                         Task 8 → Task 9

每个 Task 必须先看到测试失败，再实现最小代码，再运行相关测试。阶段 A 完成后进行一次手工验收，再完成文档和交付检查。

---

## Summary for Wave

### 变更文件清单

- 新增第六课异步协议、重试、Runtime 和四个 Adapter；
- 新增可选真实框架依赖说明；
- 扩展第六课 CLI、README 和课程笔记；
- 新增离线集成测试和可选 SDK smoke test；
- 保留现有同步离线实现和测试。

### 实现步骤概览

先建立统一异步消息、事件和异常协议，再实现 OpenAI-compatible LLM 和 Async Runtime。然后分别接入官方 AutoGen、AgentScope、LangGraph，并把流式和 LangGraph 原生中断映射到统一边界。最后更新 CLI 和文档，执行离线全量测试、可选依赖检查和安全扫描。

### 潜在风险

第三方 SDK 版本和 API 可能变化；三个框架的中断语义并不完全一致；真实网络调用可能超时、产生费用或暴露敏感数据。通过 Adapter 隔离、能力声明、可选依赖、fake client、显式 smoke test 和脱敏事件控制风险。

### 预计复杂度

高
