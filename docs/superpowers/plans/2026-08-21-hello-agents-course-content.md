# Hello-Agents Course Content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate a complete, independent 16-chapter Hello-Agents learning track under `hello-agents/`, including detailed lessons, runnable offline demos, optional LLM entry points, and tests.

**Architecture:** Keep each chapter self-contained under `hello-agents/projects/<chapter>/`. Shared behavior is limited to small standard-library helpers under `hello-agents/projects/common/`; no module imports anything from `achieve/`. Every project has deterministic offline behavior, while LLM-capable projects load configuration from the local environment and fail with an actionable message when configuration is absent.

**Tech Stack:** Python 3.11, standard library, optional `openai`, `python-dotenv`, Markdown, `unittest`.

---

### Task 1: Complete course navigation and lessons

**Files:**
- Modify: `hello-agents/CURRICULUM.md`
- Modify: `hello-agents/PROGRESS.md`
- Create: `hello-agents/lessons/02-agent-history.md` through `hello-agents/lessons/16-graduation-project.md`

- [ ] Add stable links, learning status, prerequisites, concepts, practical work, and acceptance criteria for every chapter.
- [ ] Mark `achieve/` overlap explicitly without omitting the original chapter topics.
- [ ] Keep learning progress separate from generated-content status.

### Task 2: Add shared offline utilities

**Files:**
- Create: `hello-agents/projects/common/__init__.py`
- Create: `hello-agents/projects/common/llm.py`
- Create: `hello-agents/projects/common/agent_loop.py`

- [ ] Provide environment-based optional LLM configuration with no secret logging.
- [ ] Provide a deterministic step-limited observe-decide-act loop used by examples.

### Task 3: Add chapter projects

**Files:**
- Create: `hello-agents/projects/02-agent-history/` through `hello-agents/projects/16-graduation-project/`

- [ ] Give every chapter a README explaining the learning objective, offline command, LLM command where applicable, and an experiment.
- [ ] Give every chapter a runnable `main.py` with `--demo` and a clear configuration error for `--llm` when needed.
- [ ] Keep examples small enough to read alongside the lesson and deterministic in offline mode.

### Task 4: Add tests and verify

**Files:**
- Create: `hello-agents/tests/test_course_content.py`
- Create: `hello-agents/tests/test_projects.py`

- [ ] Test that all 16 lessons and projects exist and are linked.
- [ ] Test shared loop limits, offline outputs, and configuration safety.
- [ ] Run `python -m unittest discover -s hello-agents/tests -p 'test_*.py' -v`.
- [ ] Run each project's `main.py --demo`.
- [ ] Run `git diff --check` and scan candidate files for credential-like values.

---

## Summary for Wave

### 变更文件清单

新增 Hello-Agents 16 章课程笔记、15 个新章节项目、共享离线运行模块、课程内容测试与本实现计划；更新课程表和学习进度文档。

### 实现步骤概览

先补齐课程知识结构，再实现统一的离线 Agent 基础设施，随后为每章加入最小可运行示例和可选 LLM 入口，最后执行全量静态、单元和 Demo 验证。

### 潜在风险

真实 LLM 模式需要用户自行配置网关地址、模型名和 API Key；默认验证只使用离线模式，不触发外部请求。章节涉及的第三方框架以概念和适配接口为主，避免把学习环境锁定在单一版本。

### 预计复杂度

中
