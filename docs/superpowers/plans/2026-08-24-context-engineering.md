# Context Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将第 9 课的优先级选择 Demo 扩展为带 Token 预算、过滤、注入检测、摘要存储和成本监控的上下文编译层。

**Architecture:** 新增 `context_engine` 包，contracts 定义上下文项和构建结果；tokenizer、filters、summary、builder、monitor 各自单一职责。`main.py` 保留旧函数，用工程构建器生成离线 JSON 结果。

**Tech Stack:** Python 3.11 标准库、SQLite、可选 `tiktoken`、现有 OpenAI-compatible `common.ask_llm`、unittest。

---

### Task 1: 数据契约和 Token 计数

**Files:**
- Create: `hello-agents/projects/09-context-engineering/context_engine/__init__.py`
- Create: `hello-agents/projects/09-context-engineering/context_engine/contracts.py`
- Create: `hello-agents/projects/09-context-engineering/context_engine/tokenizer.py`
- Test: `hello-agents/tests/test_context_engineering.py`

- [ ] **Step 1: Write failing tests** for JSON-safe ContextItem, selected/dropped records, deterministic token counting, and explicit tokenizer mode.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement contracts and optional tiktoken-backed TokenCounter with a deterministic fallback.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 2: Filtering, injection detection and summary persistence

**Files:**
- Create: `hello-agents/projects/09-context-engineering/context_engine/filters.py`
- Create: `hello-agents/projects/09-context-engineering/context_engine/summary.py`
- Modify: `hello-agents/tests/test_context_engineering.py`

- [ ] **Step 1: Add failing tests** for API key/cookie redaction, untrusted injection warnings, SQLite summary round-trip and source ID preservation.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement filters and parameterized SQLiteSummaryStore.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 3: Context builder, budget selection and long-session regression

**Files:**
- Create: `hello-agents/projects/09-context-engineering/context_engine/builder.py`
- Modify: `hello-agents/tests/test_context_engineering.py`

- [ ] **Step 1: Add failing tests** for required-item retention, priority/relevance/recency ordering, optional drops, required-over-budget failure, and preservation of task/source/pending metadata.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement ContextBuilder, ContextBudgetError and deterministic rendered context.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 4: Cost monitor and budget gate

**Files:**
- Create: `hello-agents/projects/09-context-engineering/context_engine/monitor.py`
- Modify: `hello-agents/tests/test_context_engineering.py`

- [ ] **Step 1: Add failing tests** for input/output cost calculation, reserve rejection, and usage report serialization.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement ModelPricing, CostMonitor and BudgetExceededError.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 5: CLI integration, documentation and full verification

**Files:**
- Modify: `hello-agents/projects/09-context-engineering/main.py`
- Modify: `hello-agents/projects/09-context-engineering/README.md`
- Modify: `hello-agents/lessons/09-context-engineering.md`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/tests/test_context_engineering.py`

- [ ] **Step 1: Add failing tests** for legacy `select_context`, engineering demo JSON, sensitive redaction, injection warnings and LLM prompt construction with an injected asker.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Integrate CLI flags for budget/model and preserve `--demo`/`--llm`.**
- [ ] **Step 4: Run focused tests and verify GREEN.**
- [ ] **Step 5: Update course status and usage documentation.**
- [ ] **Step 6: Run full tests, compileall, diff check and sensitive-file scan.**
