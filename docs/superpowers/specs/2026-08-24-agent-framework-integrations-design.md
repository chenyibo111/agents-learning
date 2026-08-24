# 第六课真实 Agent 框架集成设计

## 目标

在保留第六课现有离线 Demo 和同步 Runtime 的前提下，增加可选的真实能力：

- 官方 AutoGen SDK 调用；
- 官方 AgentScope SDK 调用；
- 官方 LangGraph `StateGraph`；
- OpenAI-compatible 真实 LLM 对话；
- 真实框架的中断/恢复边界；
- 流式事件；
- 生产级取消、超时和重试。

真实框架依赖必须是可选的。没有安装某一个框架时，离线 Demo、现有测试和其他适配器不能因此失效。API Key 只能从环境变量读取，不能进入源码、测试样例、日志或 checkpoint。

## 背景和现状

第六课当前实现位于 `hello-agents/projects/06-agent-frameworks/`：

- `frameworks.py` 提供 `AgentMessage`、`AgentState`、同步 `AgentRuntime`、SQLite checkpoint 和教学适配器；
- `main.py` 提供离线串行、并行、失败和恢复 Demo；
- `tests/test_agent_frameworks.py` 验证统一消息契约、并行汇总、失败、恢复和超时；
- 三个 `*StyleAdapter` 是教学适配器，不是官方 SDK 封装。

当前环境已发现 `langgraph`、`openai`、`httpx`、`tenacity`，未发现 AutoGen 和 AgentScope。实现不能假设所有可选依赖都已安装。

## 非目标

本次不做以下事情：

- 不删除或重写已有离线同步 Runtime；
- 不把第三方框架内部对象暴露给业务状态；
- 不将真实网络调用作为默认单元测试；
- 不将任何 API Key、Cookie、真实响应或个人配置写入仓库；
- 不把 Runtime 取消伪装成每个框架都支持的业务审批中断；
- 不在本次任务中实现完整的生产分布式任务队列、跨进程锁和计费平台。

## 方案选择

### 方案 A：直接改写 `frameworks.py`

将现有同步 Runtime 改成异步，并在其中直接判断 AutoGen、AgentScope 和 LangGraph。

优点是文件数量少；缺点是会破坏现有 Demo，框架版本差异会渗透到核心业务逻辑，测试也难以脱离 SDK。

不采用。

### 方案 B：新增异步 Runtime 和独立 Adapter 层

保留现有离线实现，增加统一异步协议、真实 LLM Adapter、三个官方框架 Adapter，以及独立的事件、取消和重试机制。

优点是兼容性和可测试性最好，第三方依赖可以懒加载，框架升级只影响对应 Adapter。缺点是会增加少量文件和异步接口。

采用该方案。

### 方案 C：每个框架维护一份独立完整示例

分别写三套状态、消息、运行、事件和恢复代码。

优点是最贴近各框架官方示例；缺点是重复实现严重，三套代码的行为很难保持一致，不适合验证框架替换边界。

不采用。

## 总体架构

```text
                    ┌─────────────────────────────┐
                    │     AsyncAgentRuntime       │
                    │ timeout/cancel/retry/events │
                    └──────────────┬──────────────┘
                                   │ AsyncAgentAdapter
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────▼─────────┐  ┌───────────▼──────────┐  ┌──────────▼──────────┐
│ OpenAI-compatible │  │ Official AutoGen     │  │ Official AgentScope │
│ LLM Adapter       │  │ Adapter              │  │ Adapter             │
└─────────┬─────────┘  └───────────┬──────────┘  └──────────┬──────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │ Official LangGraph│
                         │ StateGraph Adapter│
                         └───────────────────┘
```

所有 Adapter 都转换为课程内的 `AgentMessage`、`AgentEvent` 和统一异常。业务 Runtime 不直接依赖第三方 SDK 类型。

## 阶段 A：真实模型和官方框架

### 统一异步协议

新增 `AsyncAgentAdapter` 协议，至少包含：

```python
async def respond(
    self,
    agent: str,
    prompt: str,
    *,
    on_event: EventSink | None = None,
    cancel_token: CancellationToken | None = None,
) -> AgentMessage:
    ...
```

Adapter 必须将真实 SDK 返回值转换为 `AgentMessage`，不得让 Runtime 读取 SDK 私有字段。

Adapter 同时暴露能力信息：

```text
supports_streaming
supports_interrupt
supports_checkpoint
supports_cancellation
```

能力声明用于 CLI 校验和清晰报错，不能静默降级成另一种语义。

### OpenAI-compatible Adapter

使用项目已有的 OpenAI-compatible 配置习惯：

```text
OPENAI_API_KEY
OPENAI_BASE_URL
OPENAI_MODEL
OPENAI_TOOL_CHOICE（如果模型/网关支持）
```

Adapter 使用异步客户端，支持兼容 DeepSeek 或其他 OpenAI-compatible 网关。默认不打印请求头、API Key 和完整敏感响应。模型名称、耗时和 token usage 可以写入脱敏 metadata。

### AutoGen Adapter

使用官方 AutoGen AgentChat 和 OpenAI 扩展包。Adapter 内部负责：

- 创建模型客户端；
- 创建 AssistantAgent/团队；
- 发送任务；
- 读取最终消息和 usage；
- 将团队事件转换为课程事件；
- 将官方异常转换为统一异常。

AutoGen 的内部消息类型只存在于 Adapter 内部。

### AgentScope Adapter

使用官方 AgentScope 的 Agent、Message 和模型抽象。Adapter 内部负责：

- 创建模型和 Agent；
- 生成 AgentScope Message；
- 执行 Agent 调用；
- 处理同步/异步版本差异；
- 将结果转换为 `AgentMessage`；
- 将可用的流式事件转换为课程事件。

由于 AgentScope API 可能随版本变化，导入和版本检查必须集中在该 Adapter 中，不能散落到 Runtime 或 CLI。

### LangGraph Adapter

使用官方 `StateGraph`、`START`、`END` 和 checkpointer。图内节点只接收和返回课程定义的可序列化状态字段；SDK 的图状态不会直接成为业务层公共类型。

LangGraph Adapter 负责：

- 创建节点和边；
- 编译 StateGraph；
- 配置 checkpointer；
- 调用 `invoke`/`ainvoke` 或流式 API；
- 将节点事件转换为课程事件；
- 暴露原生 interrupt/resume 能力。

### CLI

保留现有参数，并增加显式真实模式，例如：

```text
--adapter offline
--adapter openai
--adapter autogen
--adapter agentscope
--adapter langgraph
--stream
--interrupt
```

未安装可选依赖时，CLI 输出具体安装命令和当前 Adapter，不影响 `--demo`。

## 阶段 B：运行时控制能力

### 统一事件

事件至少包括：

```text
run_started
node_started
message_delta
message_completed
retry_scheduled
node_completed
node_failed
run_paused
run_cancelled
run_completed
```

事件包含：

```text
run_id
node
phase
timestamp
duration_ms（可用时）
usage_tokens（可用时）
attempt
metadata
error（失败时）
```

事件通过异步迭代器或回调输出。事件消费失败不能破坏主任务；主任务失败必须产生 `node_failed` 或 `run_cancelled` 事件。

### 取消和超时

取消分为两层：

1. Runtime 层取消 `asyncio.Task`，阻止后续节点执行；
2. Provider 层使用 SDK/httpx 的 timeout 和取消传播，尽量终止网络请求。

取消必须满足：

- 抛出统一的 `RunCancelled`；
- 保存最后一个可恢复 checkpoint；
- 不进入重试；
- 不继续执行后续节点；
- 事件中记录 `run_cancelled`。

超时必须转换为统一 `RunTimeout`，默认视为可重试的暂时性错误，但达到重试上限后进入 `failed`。

### 生产级重试

重试策略可配置：

```text
max_attempts
base_delay
max_delay
jitter
retryable_status_codes
```

默认允许重试：

- 连接异常；
- 请求超时；
- HTTP 429；
- HTTP 500、502、503、504。

默认不重试：

- HTTP 401、403；
- 参数校验错误；
- 工具权限错误；
- 用户主动取消；
- 明确不可恢复的框架错误。

重试必须记录 `retry_scheduled` 事件。对于可能产生副作用的工具调用，只有在调用声明幂等或带有 idempotency key 时才能自动重试。

### 中断和恢复

中断能力分为原生能力和通用能力：

- LangGraph 使用官方 `interrupt()` 和 `Command(resume=...)`；
- AutoGen、AgentScope 只在当前官方版本确实提供用户输入/暂停边界时接入原生机制；
- 如果某个版本只支持取消，不得把取消冒充为业务审批中断；
- 通用 Runtime 提供 `pause`、`resume`、`cancel` 状态，但会通过能力声明明确语义差异。

恢复必须依赖 checkpoint 和 `run_id`。已完成节点不得重复执行；非幂等节点恢复前必须要求幂等键或人工确认。

## 依赖和安全

基础离线依赖保持可运行。真实框架依赖使用单独的可选依赖文件或 extras：

```text
requirements.txt              # 基础课程依赖
requirements-frameworks.txt   # 可选真实框架依赖
```

具体版本以实现时官方兼容版本为准，并在 README 中记录安装方式。依赖导入必须懒加载，错误消息必须指出：

- 哪个 Adapter 缺少依赖；
- 需要安装什么包；
- 当前离线模式仍可如何运行。

敏感数据规则：

- 只读取环境变量；
- 不打印 API Key；
- 不把请求头写入事件；
- checkpoint 中只保存脱敏消息和状态；
- 测试使用 fake client 或本地 scripted adapter。

## 测试验收

### 离线测试

- 现有第六课测试全部继续通过；
- 异步消息协议可序列化；
- 串行和并行异步流程正确完成；
- 流式事件顺序正确；
- 取消不会执行后续节点；
- timeout 按策略重试后失败；
- 429/连接错误按退避重试；
- 401/403 不重试；
- checkpoint 恢复不重复已完成节点；
- retry 事件不包含 API Key。

### 可选 SDK 测试

- 未安装依赖时测试清晰跳过；
- 安装依赖时只运行导入和最小构造 smoke test；
- 真实网络 smoke test 必须显式环境变量开启；
- 默认测试不能产生真实模型费用。

### 手工验收

```text
1. --demo 在没有任何第三方 Agent 框架时仍成功。
2. openai-compatible 模式能通过环境变量调用真实网关。
3. autogen/agentscope/langgraph 模式缺依赖时给出可操作提示。
4. langgraph 模式能暂停、保存 checkpoint 并通过 resume 继续。
5. --stream 能看到节点和消息增量事件。
6. 取消后不会继续调用下一个 Agent。
7. 429/超时会退避重试，401 不重试。
8. 运行输出和仓库文件中没有 API Key。
```

## 文件边界

```text
hello-agents/projects/06-agent-frameworks/
├── frameworks.py                  # 既有离线同步实现，保持兼容
├── async_runtime.py                # 异步运行、事件、取消、恢复
├── retry.py                        # 重试分类和指数退避
├── integrations/
│   ├── __init__.py
│   ├── common.py                   # 异步协议、能力和统一异常
│   ├── openai_compatible.py        # 真实 LLM
│   ├── autogen_adapter.py          # 官方 AutoGen
│   ├── agentscope_adapter.py       # 官方 AgentScope
│   └── langgraph_adapter.py        # 官方 LangGraph
├── main.py                         # 保留离线参数，增加真实模式
└── README.md                       # 安装和运行说明
```

测试新增到 `hello-agents/tests/test_agent_framework_integrations.py`，不修改原有测试的离线语义。

## 风险和控制

| 风险 | 控制措施 |
|---|---|
| 第三方 SDK API 变化 | 懒加载、版本检查、Adapter 隔离、独立 smoke test |
| 真实调用产生费用 | 默认离线，网络 smoke test 显式开启 |
| 重试导致重复副作用 | 仅对幂等操作自动重试，工具使用 idempotency key |
| 取消无法真正终止 provider 请求 | Runtime 取消 + HTTP timeout，文档明确 best effort |
| checkpoint 泄漏敏感响应 | 脱敏、禁止保存请求头和 Key |
| 并行状态覆盖 | Worker 只返回结果，主 Runtime 统一合并 |
| LangGraph 与通用 Runtime 双重调度 | LangGraph Adapter 内部负责图调度，外层只负责统一协议和生命周期 |
