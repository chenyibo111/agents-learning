# Research Assistant Architecture Implementation Plan

> **For agentic workers:** Implement this plan task-by-task with tests before production code. Do not commit unless the user explicitly requests it.

**Goal:** Build lesson 27 as a research-assistant architecture that runs the same workflow with either deterministic offline providers or an OpenAI-compatible LLM runtime.

**Architecture:** A shared `ResearchState` and workflow graph will coordinate planning, source collection, evidence extraction, verification, and report generation. The offline runtime returns deterministic records without network access; the LLM runtime calls an OpenAI-compatible Chat Completions endpoint behind the same runtime interface. The CLI selects `--demo` or `--llm`, while tests exercise the workflow with a fake client and never use real credentials.

**Tech Stack:** Python 3.11+, LangGraph, OpenAI-compatible `openai` client, `python-dotenv`, `unittest`.

---

### Task 1: Define the shared state and runtime contract

**Files:**
- Create: `projects/27-research-assistant/state.py`
- Create: `projects/27-research-assistant/runtime.py`
- Test: `tests/test_research_assistant.py`

- [ ] Write tests for the required state fields, deterministic runtime output, and fake LLM runtime output.
- [ ] Run the focused tests and confirm they fail because the lesson 27 modules do not exist.
- [ ] Define `ResearchState`, `ResearchRuntime`, `DemoRuntime`, and `LLMRuntime` interfaces with no API key stored in state.
- [ ] Run the focused tests and confirm both runtimes return the same result shape.

### Task 2: Implement the shared research workflow

**Files:**
- Create: `projects/27-research-assistant/workflow.py`
- Modify: `tests/test_research_assistant.py`

- [ ] Add nodes for `plan`, `collect_sources`, `extract_evidence`, `verify_evidence`, and `write_report`.
- [ ] Connect the nodes in a fixed sequence and make every node update only its own state fields.
- [ ] Make the graph accept a runtime object so Demo and LLM modes use the same topology.
- [ ] Test node order, completed status, evidence verification, and report citations.

### Task 3: Add the CLI entry point and configuration boundary

**Files:**
- Create: `projects/27-research-assistant/main.py`
- Create: `projects/27-research-assistant/requirements.txt`
- Modify: `tests/test_research_assistant.py`

- [ ] Add `--demo` and `--llm` modes with a required `--topic` argument.
- [ ] Ensure `--demo` never reads model credentials or calls the network.
- [ ] Load `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` only for `--llm`.
- [ ] Reject missing or placeholder credentials with an actionable error.
- [ ] Test CLI mode selection and configuration validation with a fake client.

### Task 4: Write the lesson materials and progress links

**Files:**
- Create: `lessons/27-research-assistant-architecture.md`
- Create: `projects/27-research-assistant/README.md`
- Modify: `CURRICULUM.md`
- Modify: `README.md`
- Modify: `ROADMAP.md`

- [ ] Explain the shared workflow, two runtimes, state boundaries, and why Demo and LLM paths must share the same contract.
- [ ] Document macOS/zsh commands for installation and running both modes.
- [ ] Document that real LLM tests use a fake client and never commit `.env`.
- [ ] Mark lesson 26 complete and lesson 27 in progress after the implementation is verified.

### Task 5: Verify the lesson end-to-end

- [ ] Run the focused lesson 27 test suite.
- [ ] Run the offline Demo and confirm it produces a report without network access.
- [ ] Run the full repository test suite.
- [ ] Run `git diff --check` and scan changed files for credentials.
- [ ] Leave all changes uncommitted unless the user separately requests a commit.
