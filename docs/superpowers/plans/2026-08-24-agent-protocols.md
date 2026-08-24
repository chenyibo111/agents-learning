# Agent Protocols Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将第 10 课的协议 Demo 扩展为带 JSON-RPC/MCP 工具资源调用、A2A 任务生命周期、认证授权、幂等和重放保护的本地工程实现。

**Architecture:** `protocol_engine` 按契约、错误、版本、注册表、认证、幂等、重放、任务和 JSON-RPC 服务拆分。`mcp_adapter.py` 注册本地工具/资源，`a2a_adapter.py` 提供任务客户端，`main.py` 组合离线演示并保留真实 LLM 解释模式。

**Tech Stack:** Python 3.11 标准库、可选 `mcp==1.29.0`、unittest、JSON-RPC 2.0 风格数据契约。

---

### Task 1: 协议契约、错误码和版本协商

**Files:**
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/__init__.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/contracts.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/errors.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/codec.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/versioning.py`
- Test: `hello-agents/tests/test_agent_protocols.py`

- [ ] **Step 1: Write failing tests** for JSON-RPC request/response round-trip, JSON-safe tool/resource/task contracts, stable error payloads and exact version negotiation.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement the minimal dataclasses, codec, error registry and version negotiator.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 2: Registry、认证授权和 JSON-RPC MCP 服务

**Files:**
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/auth.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/registry.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/idempotency.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/replay.py`
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/server.py`
- Modify: `hello-agents/tests/test_agent_protocols.py`

- [ ] **Step 1: Add failing tests** for tools/list, tools/call, resources/list/read, schema errors, resource allowlist, forbidden scope, idempotent replay and request-id replay protection.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement explicit registries, scope-based authorizer and JSON-RPC dispatcher.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 3: A2A task lifecycle、超时和取消

**Files:**
- Create: `hello-agents/projects/10-agent-protocols/protocol_engine/tasks.py`
- Create: `hello-agents/projects/10-agent-protocols/a2a_adapter.py`
- Modify: `hello-agents/projects/10-agent-protocols/protocol_engine/server.py`
- Modify: `hello-agents/tests/test_agent_protocols.py`

- [ ] **Step 1: Add failing tests** for submitted/working/completed/failed/cancelled/expired transitions, invalid transitions, timeout and cancellation.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement TaskManager and task JSON-RPC methods with cooperative cancellation semantics.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 4: MCP adapter、CLI 和课程文档

**Files:**
- Create: `hello-agents/projects/10-agent-protocols/mcp_adapter.py`
- Modify: `hello-agents/projects/10-agent-protocols/main.py`
- Modify: `hello-agents/projects/10-agent-protocols/README.md`
- Modify: `hello-agents/lessons/10-agent-protocols.md`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/tests/test_agent_protocols.py`

- [ ] **Step 1: Add failing integration tests** for offline protocol demo, custom JSON request dispatch, legacy task envelope and optional official MCP factory.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Integrate `--demo`, `--llm`, `--request`, `--token` and protocol selection without exposing credentials.**
- [ ] **Step 4: Update README, lesson and progress evidence.**
- [ ] **Step 5: Run full tests, compileall, diff check and sensitive-file scan.**
