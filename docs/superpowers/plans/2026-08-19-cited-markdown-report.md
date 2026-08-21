# Cited Markdown Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate traceable Markdown reports from lesson 29 verified evidence with offline Demo and real LLM writers.

**Architecture:** A pure citation module maps evidence to stable citation numbers and validates model output. A Demo writer renders a deterministic template; an LLM writer only organizes the supplied evidence. A lesson-29 adapter runs the existing research workflow and passes its verified evidence into the report layer.

**Tech Stack:** Python 3.11, LangGraph, OpenAI-compatible client, existing lesson-28/29 modules, `unittest`.

---

### Task 1: Define citation and report-writer contracts with tests first

**Files:**
- Create: `projects/30-cited-markdown-report/report.py`
- Test: `tests/test_cited_markdown_report.py`

- [ ] **Step 1: Write failing tests** for stable citation numbering, duplicate `source + chunk_id` deduplication, deterministic Demo Markdown, LLM context forwarding, and invalid citation rejection.
- [ ] **Step 2: Run the focused test file** and confirm it fails because lesson-30 modules do not exist.
- [ ] **Step 3: Implement `build_citations`, `render_demo_report`, `validate_report_citations`, `DemoReportWriter`, and `LLMReportWriter`.
- [ ] **Step 4: Run focused tests** and confirm they pass.

### Task 2: Integrate lesson 29 workflow and add CLI

**Files:**
- Create: `projects/30-cited-markdown-report/research_source.py`
- Create: `projects/30-cited-markdown-report/main.py`
- Create: `projects/30-cited-markdown-report/requirements.txt`
- Test: `tests/test_cited_markdown_report.py`

- [ ] **Step 1: Add an offline CLI/integration test** using the lesson-29 DemoRuntime and a fake or keyword retriever; assert the output has `#`, `[1]`, and a source identifier.
- [ ] **Step 2: Run the test** and confirm it fails before the integration code exists.
- [ ] **Step 3: Implement the adapter** for lesson-29 runtime/workflow and lesson-28 retrievers without duplicating either workflow or retrieval implementation.
- [ ] **Step 4: Implement CLI flags** `--demo/--llm`, `--retriever`, `--query`, `--top-k`, `--thread-id`, and `--rebuild`.
- [ ] **Step 5: Run focused tests and the offline CLI** without downloading vector dependencies.

### Task 3: Add course materials and progress markers

**Files:**
- Create: `projects/30-cited-markdown-report/README.md`
- Create: `lessons/30-cited-markdown-report.md`
- Modify: `CURRICULUM.md`
- Modify: `ROADMAP.md`
- Modify: `README.md`

- [ ] **Step 1: Document citation numbering, evidence chains, Demo/LLM boundaries, and report validation.
- [ ] **Step 2: Mark lesson 30 as in progress** without marking it complete.

### Task 4: Verify and review

**Files:**
- Review: all lesson-30 files and changed course indexes

- [ ] **Step 1: Run focused tests:** `.venv311/bin/python -m unittest tests/test_cited_markdown_report.py -v`.
- [ ] **Step 2: Run the full suite:** `.venv311/bin/python -m unittest discover -s tests -p 'test_*.py' -v`.
- [ ] **Step 3: Run the offline CLI and inspect generated citations.
- [ ] **Step 4: Run `git diff --check` and scan changed lesson-30 files for API keys, tokens, cookies, and `.env` content.
- [ ] **Step 5: Leave all changes uncommitted unless the user explicitly requests a commit.
