# Research Task Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build lesson 29 as a four-node research workflow that reuses lesson 28 retrieval and supports offline Demo plus real OpenAI-compatible LLM execution.

**Architecture:** A `ResearchRuntime` supplies planning, evidence extraction, and verification behavior. A lesson-28 retriever is injected into the `retrieve` node. LangGraph connects `plan → retrieve → extract → verify`; the workflow returns verified evidence and does not generate the final report yet.

**Tech Stack:** Python 3.11, LangGraph, OpenAI-compatible client, existing lesson-28 keyword/vector retrievers, `unittest`.

---

### Task 1: Define the runtime and workflow contracts with tests first

**Files:**
- Create: `projects/29-research-task-workflow/state.py`
- Create: `projects/29-research-task-workflow/runtime.py`
- Create: `projects/29-research-task-workflow/workflow.py`
- Test: `tests/test_research_task_workflow.py`

- [ ] **Step 1: Write failing tests** for DemoRuntime records, LLMRuntime JSON validation, node-by-node state updates, and event ordering.
- [ ] **Step 2: Run the focused test file** and confirm it fails because the lesson-29 modules do not exist.
- [ ] **Step 3: Implement minimal state types, DemoRuntime, LLMRuntime, and four node functions.** The runtime contract must not contain a search method; retrieval is injected separately.
- [ ] **Step 4: Run the focused tests** and confirm the tests pass.

### Task 2: Add the LangGraph composition and retrieval adapter

**Files:**
- Modify: `projects/29-research-task-workflow/workflow.py`
- Create: `projects/29-research-task-workflow/retrieval_source.py`
- Test: `tests/test_research_task_workflow.py`

- [ ] **Step 1: Add a failing graph test** using a fake retriever and DemoRuntime; assert the graph reaches `completed` and carries retrieved chunks into evidence.
- [ ] **Step 2: Run the graph test** and confirm the new graph behavior fails.
- [ ] **Step 3: Compile the graph** with `plan`, `retrieve`, `extract`, and `verify`, using a checkpointer compatible with installed LangGraph versions.
- [ ] **Step 4: Implement the adapter** that loads lesson-28 `load_chunks`, `KeywordRetriever`, and optional `VectorRetriever` without duplicating retrieval logic.
- [ ] **Step 5: Run focused tests** and confirm graph and adapter tests pass without downloading models.

### Task 3: Add CLI and user-facing lesson materials

**Files:**
- Create: `projects/29-research-task-workflow/main.py`
- Create: `projects/29-research-task-workflow/README.md`
- Create: `lessons/29-research-task-workflow.md`
- Modify: `CURRICULUM.md`
- Modify: `ROADMAP.md`
- Modify: `README.md`

- [ ] **Step 1: Add a CLI smoke test** for `--demo --retriever keyword` that asserts the output includes workflow status and evidence source identifiers.
- [ ] **Step 2: Run the smoke test** and confirm the CLI fails before implementation.
- [ ] **Step 3: Implement CLI flags** `--demo/--llm`, `--retriever`, `--query`, `--top-k`, and `--thread-id`; keep vector dependencies lazy and preserve placeholder-key validation.
- [ ] **Step 4: Write the README and lesson note** explaining state initialization, node input/output, runtime/retriever boundaries, and how to run both modes.
- [ ] **Step 5: Mark lesson 29 as in progress** in the course indexes without marking it complete before tests and the learning exercise are finished.

### Task 4: Verify and review

**Files:**
- Review: all lesson-29 files and changed course indexes

- [ ] **Step 1: Run focused tests:** `python3 -m unittest tests/test_research_task_workflow.py -v`.
- [ ] **Step 2: Run the full suite:** `python3 -m unittest discover -s tests -p 'test_*.py' -v`.
- [ ] **Step 3: Run the offline CLI** with the keyword retriever.
- [ ] **Step 4: Search the diff for secrets** such as API keys, tokens, cookies, and accidental `.env` content.
- [ ] **Step 5: Report the exact verification results and leave changes uncommitted unless the user explicitly requests a commit.
