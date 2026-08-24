# 07 - Mini Agent Framework

对应课程：[07-build-agent-framework](../../lessons/07-build-agent-framework.md)，状态：✅ 已完成。

运行：`python projects/07-build-agent-framework/main.py --demo`；`--llm` 保留原有课程问答入口。Demo 使用共享 `run_loop`，展示最小循环的压缩形态。

工程实现运行：

```bash
python projects/07-build-agent-framework/main.py \
  --framework-demo \
  --query "计算 4 + 5"
```

真实 LLM Agent：

```bash
python projects/07-build-agent-framework/main.py \
  --llm-agent \
  --query "计算 4 + 5"
```

真实模式复用仓库已有的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL` 配置。模型需要按提示返回 JSON action；默认测试不联网。

## 工程结构

```text
mini_agent/
├── contracts.py   # Message、Action、ModelResponse、RunResult、AgentEvent
├── errors.py      # 协议、工具和执行异常
├── model.py       # Model 协议、RuleModel、OpenAITextModel
├── tools.py       # ToolSpec、ToolRegistry、schema 和权限校验
├── memory.py      # 消息记忆和 SQLite checkpoint
├── policy.py      # 严格解析 final/tool_call
└── runner.py      # 有限循环、工具执行、事件、重试和恢复
```

数据流是：

```text
用户任务 → Runner → Memory → Model → Policy
                              ↓
                   final 或 tool_call
                              ↓
             ToolRegistry → Tool → Observation
                              ↓
                            Memory
```

### Model

`Model` 只负责根据消息和工具 schema 产生响应。`RuleModel` 用于离线测试；`OpenAITextModel` 调用真实 OpenAI-compatible API。模型不直接执行工具，也不能绕过 Runner 修改状态。

### ToolRegistry

工具注册后才允许执行。执行顺序固定为：

```text
查找工具 → 检查权限 → 校验 required/type/schema → 执行 handler
```

未知工具、缺少参数、类型错误和权限不足都会拒绝执行。

### Memory 和 checkpoint

Memory 保存用户消息、模型消息、工具观察结果、事件、步数和状态。每个关键节点保存到 SQLite，因此可以用 `--checkpoint` 和 `--resume` 恢复运行：

```bash
checkpoint=/tmp/lesson07.sqlite3

python projects/07-build-agent-framework/main.py \
  --framework-demo \
  --pause-after-step 1 \
  --checkpoint "$checkpoint"
```

输出中的 `run_id` 可以用于同一 checkpoint 文件恢复：

```bash
python projects/07-build-agent-framework/main.py \
  --framework-demo \
  --resume \
  --run-id "替换为上一步的 run_id" \
  --checkpoint "$checkpoint"
```

### Runner

Runner 负责最大步数、状态更新、工具调用、工具重试、事件、失败结果和 checkpoint。它不依赖 AutoGen、AgentScope 或 LangGraph，因此可以替换 Model 而不重写执行流程。

## 实验

- 在 `tools.py` 中新增一个带字符串参数的工具，补充 schema 校验；
- 把 `RuleModel` 替换成另一个 fake Model，验证 Runner 不变；
- 让工具第一次抛出 `RetryableToolError`，观察 `retry_scheduled` 事件；
- 让模型一直返回 tool_call，观察 `max_steps` 状态；
- 使用 SQLite checkpoint 手工构造暂停状态，验证恢复时不重复已完成步骤；
- 检查事件和错误文本不会输出 API Key、Authorization 或 Cookie。

## 测试

```bash
python -m unittest hello-agents/tests/test_build_agent_framework.py -v
python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v
```

## 三层实现状态

- 概念层：已完成 Model、Tool、Policy、Runner 的边界设计。
- 最小实践层：当前 Demo 已使用规则模型、工具和有上限的 Runner。
- 工程实现层：已拆分 `mini_agent` 包，加入消息 schema、工具注册、权限校验、SQLite checkpoint、事件观测、错误分类、离线 Model、真实 LLM Model 和完整测试。
