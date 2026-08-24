# Mini Agent Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为第 7 课补齐 Model、Tool、Memory、Policy、Runner 的工程化教学实现，并保留原有 Demo。

**Architecture:** 在 `projects/07-build-agent-framework/mini_agent/` 下创建框架无关的协议、模型、工具注册表、记忆、策略和 Runner。离线规则模型和 OpenAI-compatible 文本模型都实现同一 Model 协议；Runner 统一处理有限循环、事件、失败和 checkpoint。

**Tech Stack:** Python 3.11、标准库 `dataclasses`/`sqlite3`/`inspect`/`json`、已有 `common.llm`、`unittest`。

**Execution status (2026-08-24):** Tasks 1–6 implementation and focused verification are complete; Task 7 final full-suite, compile and security checks are complete. Git commit is intentionally not performed.

---

### Task 1: Contracts 和统一异常

**Files:**

- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/__init__.py`
- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/contracts.py`
- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/errors.py`
- Test: `hello-agents/tests/test_build_agent_framework.py`

- [ ] 写 `Message`、`ToolCall`、`ModelResponse`、`Action`、`RunResult` 和 `AgentEvent` 的序列化失败测试。
- [ ] 运行 focused test，确认模块不存在导致失败。
- [ ] 实现只依赖标准库的 dataclass 和异常。
- [ ] 运行 focused test，确认协议测试通过。

### Task 2: Tool、Registry 和 schema 校验

**Files:**

- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/tools.py`
- Modify: `mini_agent/errors.py`
- Test: `hello-agents/tests/test_build_agent_framework.py`

- [ ] 测试装饰器注册、未知工具、缺少参数、参数类型错误和权限拒绝。
- [ ] 运行测试确认 RED。
- [ ] 实现 `ToolSpec`、`ToolRegistry.register`、`ToolRegistry.get`、`ToolRegistry.execute`，用标准库校验 object schema 的 required/properties/type。
- [ ] 运行 focused test 确认 GREEN。

### Task 3: Memory 和 SQLite checkpoint

**Files:**

- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/memory.py`
- Test: `hello-agents/tests/test_build_agent_framework.py`

- [ ] 测试消息追加、上下文序列化、checkpoint 保存和加载。
- [ ] 运行测试确认 RED。
- [ ] 实现内存消息列表、运行状态、SQLite `checkpoints` 表和可恢复快照。
- [ ] 运行 focused test 确认 GREEN。

### Task 4: Model 和 Policy

**Files:**

- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/model.py`
- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/policy.py`
- Test: `hello-agents/tests/test_build_agent_framework.py`

- [ ] 测试规则模型产生 tool_call/final，Policy 解析 JSON action，非法 JSON 和未知 action 被拒绝。
- [ ] 运行测试确认 RED。
- [ ] 实现 `Model` Protocol、`RuleModel`、`OpenAITextModel` 和严格 JSON Policy；真实模型调用复用 `common.llm.ask_llm`，不把 API Key 放入响应 metadata。
- [ ] 运行 focused test 确认 GREEN。

### Task 5: Runner、事件、重试和恢复

**Files:**

- Create: `hello-agents/projects/07-build-agent-framework/mini_agent/runner.py`
- Test: `hello-agents/tests/test_build_agent_framework.py`

- [ ] 测试 tool_call → observation → final、最大步数、工具失败、重试事件和恢复跳过已完成步骤。
- [ ] 运行测试确认 RED。
- [ ] 实现 `Runner.run`、有限步数、节点耗时、事件记录、可重试错误、checkpoint 和 `resume`。
- [ ] 运行 focused test 确认 GREEN。

### Task 6: CLI 和课程文档

**Files:**

- Modify: `hello-agents/projects/07-build-agent-framework/main.py`
- Modify: `hello-agents/projects/07-build-agent-framework/README.md`
- Modify: `hello-agents/lessons/07-build-agent-framework.md`
- Modify: `hello-agents/PROGRESS.md`
- Test: `hello-agents/tests/test_build_agent_framework.py`

- [ ] 测试旧 `--demo` 仍成功，`--framework-demo` 离线执行，缺少真实配置时安全失败。
- [ ] 运行 CLI 测试确认 RED。
- [ ] 增加 `--framework-demo`、`--llm-agent`、`--query`、`--max-steps`、`--checkpoint` 和 `--resume`，不改变原有参数语义。
- [ ] 更新三层课程材料、组件关系、运行命令和实验说明。
- [ ] 运行第 7 课测试和全量课程测试。

### Task 7: 交付验证

**Files:**

- Modify only if verification exposes an issue.

- [ ] 运行 `compileall`。
- [ ] 运行全量 `unittest`。
- [ ] 运行 `git diff --check`。
- [ ] 扫描新增代码和文档中的 API Key、Authorization、Cookie 和明文 secret。
- [ ] 保留工作区变更，不执行 Git commit。

---

## Summary for Wave

### 变更文件清单

- 新增第 7 课 `mini_agent` 工程包和集成测试；
- 扩展第 7 课 CLI、README、课程笔记和进度；
- 新增设计文档与实现计划。

### 实现步骤概览

先建立稳定协议，再实现工具注册与校验、记忆与 checkpoint、模型与 Policy，最后用 Runner 串联并接入 CLI。全程保留旧 Demo，默认测试离线且不暴露凭证。

### 潜在风险

真实模型输出可能不遵守 JSON；当前真实模型 Adapter 通过提示词约束并严格解析，生产系统还应优先使用 provider 的 structured output/tool calling。

### 预计复杂度

中高
