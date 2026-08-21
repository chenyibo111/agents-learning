# Final Evaluation and Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the final course project with offline/LLM evaluation, runtime monitoring, and deployment readiness checks.

**Architecture:** The app adapter reuses the lesson 30 research/report pipeline. A pure evaluator consumes an injected app contract, a monitor records execution telemetry, and a deployment module validates configuration without exposing secrets. The CLI composes these pieces.

**Tech Stack:** Python 3.11, existing lesson 28/29/30 modules, standard-library `unittest`, SQLite/LLM dependencies supplied by earlier lessons.

---

### Task 1: Build evaluation and monitoring primitives with tests first

**Files:**
- Create: `projects/32-final-evaluation-deployment/evaluation.py`
- Create: `projects/32-final-evaluation-deployment/monitoring.py`
- Test: `tests/test_final_evaluation_deployment.py`

- [ ] **Step 1: Write failing tests** for fixed cases, source/citation/status checks, pass-rate summary, monitor success/failure spans, token estimation, and cost totals.
- [ ] **Step 2: Run the focused test file** and confirm it fails because the lesson-32 modules do not exist.
- [ ] **Step 3: Implement minimal typed contracts and deterministic evaluator/monitor behavior.
- [ ] **Step 4: Run focused tests** and confirm they pass.

### Task 2: Add deployment validation and previous-lesson adapter

**Files:**
- Create: `projects/32-final-evaluation-deployment/deployment.py`
- Create: `projects/32-final-evaluation-deployment/app_adapter.py`
- Test: `tests/test_final_evaluation_deployment.py`

- [ ] **Step 1: Add failing configuration tests** for Demo, missing LLM fields, placeholder keys, valid LLM config, and redacted health summaries.
- [ ] **Step 2: Implement configuration validation** without returning or printing the API key.
- [ ] **Step 3: Implement the adapter** that runs lesson 30's research workflow/report layer for Demo or LLM mode.
- [ ] **Step 4: Run focused tests** without real network calls.

### Task 3: Add CLI, docs, and course progress

**Files:**
- Create: `projects/32-final-evaluation-deployment/main.py`
- Create: `projects/32-final-evaluation-deployment/README.md`
- Create: `projects/32-final-evaluation-deployment/requirements.txt`
- Create: `lessons/32-final-evaluation-deployment.md`
- Modify: `CURRICULUM.md`
- Modify: `ROADMAP.md`
- Modify: `README.md`

- [ ] **Step 1: Add an offline CLI smoke test** for `--demo --evaluate` and `--demo --health`.
- [ ] **Step 2: Implement CLI flags** `--demo/--llm`, `--evaluate`, `--health`, `--query`, and `--budget-usd`.
- [ ] **Step 3: Document the final architecture, metrics, deployment checks, and macOS/zsh commands.
- [ ] **Step 4: Mark lesson 32 as in progress, not complete.

### Task 4: Verify and review

**Files:**
- Review: all lesson-32 files and changed course indexes

- [ ] **Step 1: Run focused tests:** `.venv311/bin/python -m unittest tests/test_final_evaluation_deployment.py -v`.
- [ ] **Step 2: Run the full suite:** `.venv311/bin/python -m unittest discover -s tests -p 'test_*.py' -v`.
- [ ] **Step 3: Run offline evaluation and health CLI commands.
- [ ] **Step 4: Run `git diff --check` and scan changed files for API keys, tokens, cookies, `.env`, and generated artifacts.
- [ ] **Step 5: Leave changes uncommitted unless explicitly requested.
