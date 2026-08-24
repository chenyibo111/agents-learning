# 06 - Agent 框架实践：消息、状态图与 Runtime

对应课程：[06-agent-frameworks](../../lessons/06-agent-frameworks.md)，状态：✅ 已完成；回顾 `achieve` 第 23～26 课。

本课不把业务代码绑死在某个第三方框架上，而是先实现稳定的框架无关接口，再把 OpenAI-compatible LLM、官方 AutoGen、AgentScope 和 LangGraph 接到同一套异步 Runtime。

## 三层实现

### 第一层：概念

比较三个框架时关注：谁持有状态、消息怎样传递、节点怎样路由、检查点怎样保存、失败怎样恢复。

### 第二层：最小 Demo

`--demo` 会用三个风格适配器运行相同的串行协作：

```text
research Agent → writing Agent → end
```

运行：

```bash
cd /Users/yibo.chen/project/agents-learning
.venv311/bin/python hello-agents/projects/06-agent-frameworks/main.py --demo
```

### 第三层：工程实现

核心代码在 `frameworks.py`：

- `AgentMessage`：统一消息协议和 token 用量；
- `AgentState`：任务、结果、消息、事件、当前节点和状态；
- `AgentRuntime`：串行、并行、fan-out/fan-in、超时、失败和成本观测；
- `SQLiteCheckpointStore`：保存和恢复完整运行状态；
- `AutoGenStyleAdapter`：对话协作风格；
- `AgentScopeStyleAdapter`：Agent/消息/Runtime 组织风格；
- `LangGraphStyleAdapter`：状态图和 checkpoint 风格；
- `ScriptedAdapter`：用于测试失败和慢调用。

`integrations/` 下的适配器是真实 SDK 的边界层：

- `openai_compatible.py`：异步 OpenAI-compatible Chat Completions、流式 delta、usage 和取消；
- `autogen_adapter.py`：官方 `autogen-agentchat` 的 `AssistantAgent`；
- `agentscope_adapter.py`：官方 AgentScope 1.x 的 `ReActAgent`、消息队列流式事件；
- `langgraph_adapter.py`：官方 `StateGraph`、`MemorySaver`、`interrupt()` 和 `Command(resume=...)`。

适配器把 SDK 的返回值转换为统一的 `AgentMessage`，把流式片段转换为 `AgentEvent`，把供应商异常转换为 `ProviderError`。业务 Runtime 不需要知道第三方 SDK 的具体 API。

`frameworks.py` 中的 `AutoGenStyleAdapter`、`AgentScopeStyleAdapter`、`LangGraphStyleAdapter` 仍然保留，它们是零依赖的概念 Demo；`integrations/` 才是官方 SDK 接入。

## 官方依赖安装

三个框架都属于可选依赖，而且 AutoGen 与 AgentScope 的 protobuf 依赖范围可能冲突。不要把三个 requirements 文件安装到同一个虚拟环境，按要验证的框架分别创建环境：

```bash
python3.11 -m venv .venv-autogen
source .venv-autogen/bin/activate
python -m pip install -r hello-agents/requirements-autogen.txt
deactivate

python3.11 -m venv .venv-agentscope
source .venv-agentscope/bin/activate
python -m pip install -r hello-agents/requirements-agentscope.txt
deactivate

python3.11 -m venv .venv-langgraph
source .venv-langgraph/bin/activate
python -m pip install -r hello-agents/requirements-langgraph.txt
```

`requirements-frameworks.txt` 只是依赖索引，不会安装全部框架。当前验证版本写在各自的 requirements 文件中。

## 异步 CLI

显式选择 `--adapter` 后，CLI 使用新的异步 Runtime；不传 `--adapter` 时，旧版同步离线参数保持兼容：

```bash
# 零依赖、零网络的异步实现
python hello-agents/projects/06-agent-frameworks/main.py \
  --adapter offline --query "解释 Agent 的状态流转"

# 输出生命周期事件和模型增量事件
python hello-agents/projects/06-agent-frameworks/main.py \
  --adapter openai --stream --query "用三句话解释 StateGraph"
```

真实模式读取仓库 `.env` 或当前 shell 的：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。网关只要兼容 OpenAI Chat Completions 即可，例如把 `OPENAI_BASE_URL` 设置为网关的 `/v1` 地址：

```bash
python hello-agents/projects/06-agent-frameworks/main.py --adapter openai
python hello-agents/projects/06-agent-frameworks/main.py --adapter autogen
python hello-agents/projects/06-agent-frameworks/main.py --adapter agentscope --stream
python hello-agents/projects/06-agent-frameworks/main.py --adapter langgraph
```

重试和节点超时可通过 CLI 调整：

```bash
python hello-agents/projects/06-agent-frameworks/main.py \
  --adapter openai --timeout-seconds 20 --max-attempts 3
```

## LangGraph 原生中断

LangGraph 的审批节点使用官方 `interrupt()`，恢复使用 `Command(resume=...)`，不是把普通取消伪装成审批：

```bash
python hello-agents/projects/06-agent-frameworks/main.py \
  --adapter langgraph --interrupt --query "发布报告"

# 为了演示，在同一次进程中暂停后立即恢复
python hello-agents/projects/06-agent-frameworks/main.py \
  --adapter langgraph --interrupt --approval approved --query "发布报告"
```

示例使用 `MemorySaver`，checkpoint 只在当前进程有效；生产环境应替换为持久化 checkpointer，并用稳定的 `thread_id` 跨进程恢复。通用 Runtime 的 `AsyncAgentRuntime.cancel(task)` 则负责生产级任务取消；取消会保存 `cancelled` 状态，也不会触发重试。

## 事件、重试与安全

统一事件包含 `run_id`、节点、阶段、耗时、attempt、usage、metadata 和 error。可观察到 `run_started`、`node_started`、`message_delta`、`message_completed`、`retry_scheduled`、`node_completed`、`node_failed`、`run_cancelled` 和 `run_completed`。

默认只重试超时、连接错误和 429/5xx；401、403、参数错误和取消不重试。事件、checkpoint 和错误文本都会对 API key、Authorization、Cookie、token 等字段脱敏。默认测试不调用网络；设置 `RUN_REAL_AGENT_SMOKE=1` 才会启用真实模型 smoke test，并可能产生费用。

## 串行协作

```bash
.venv311/bin/python hello-agents/projects/06-agent-frameworks/main.py
```

状态大致经过：

```text
running
  ↓
research
  ↓ checkpoint
writing
  ↓
completed
```

## 并行 fan-out/fan-in

```bash
.venv311/bin/python hello-agents/projects/06-agent-frameworks/main.py --parallel
```

两个 Agent 并行执行：

```text
             ┌─ research ─┐
task ────────┤             ├── writing ── completed
             └─ critic ────┘
```

并行分支完成后，由 writing Agent 汇总两个结果。真实系统中并行共享状态时需要 reducer 或明确的合并策略，不能让两个线程无保护地覆盖同一个字段。

## 失败和恢复

模拟 research Agent 失败：

```bash
.venv311/bin/python hello-agents/projects/06-agent-frameworks/main.py --fail
```

失败状态会保存：

```json
{
  "status": "failed",
  "current_node": "research",
  "error": "Agent research 执行失败"
}
```

从 checkpoint 恢复：

```bash
checkpoint=/tmp/hello-agents-frameworks.sqlite3

# 命令输出中的 run_id 需要保留
.venv311/bin/python hello-agents/projects/06-agent-frameworks/main.py \
  --stop-after research \
  --checkpoint "$checkpoint"

# 使用上一步输出的 run_id 恢复
.venv311/bin/python hello-agents/projects/06-agent-frameworks/main.py \
  --resume \
  --run-id "替换为上一步的 run_id" \
  --checkpoint "$checkpoint"
```

恢复时不会重复执行已经完成的 research 节点，而是继续 writing。

## 观测与成本

每个事件记录：

```text
node
phase
duration_ms
usage_tokens
error
```

这让 Runtime 可以回答：

- 哪个 Agent 最慢？
- 哪个节点消耗 token 最多？
- 失败发生在哪个节点？
- 恢复时是否重复执行了节点？

## 实验

- 把串行 research → writing 改成 research/critic 并行后汇总；
- 用 checkpoint 暂停并恢复，验证 completed_nodes 不重复；
- 模拟 Agent 失败，区分 `failed` 和正常结束；
- 调小 timeout，观察慢 Agent 如何失败；
- 为消息增加 trace_id，并让所有节点事件携带它；
- 以后接入真实框架时，只替换 Adapter，不改状态和业务测试。

## 测试

```bash
.venv311/bin/python -m unittest hello-agents/tests/test_agent_frameworks.py -v
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v
```

完成标准：能解释三种框架的抽象差异，能运行串行和并行协作，能从 checkpoint 恢复，能定位失败和超时，并能解释为什么 Adapter 边界可以降低框架升级对业务代码的影响。
