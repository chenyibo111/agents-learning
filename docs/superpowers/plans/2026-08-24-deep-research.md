# DeepResearch Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]` syntax for tracking.

**Goal:** Build a deterministic, auditable and resumable DeepResearch workflow for lesson 14.

**Architecture:** A versioned local corpus is accessed through a retriever interface. The engine advances a research state through planned rounds, stores source/evidence/claim/citation objects separately, and produces a citation-audited report with checkpoint recovery.

**Tech Stack:** Python standard library, `dataclasses`, `datetime`, `unittest`, JSON/JSONL; no network or new runtime dependency in the default path.

**Spec:** `docs/superpowers/specs/2026-08-24-deep-research-design.md`

## Global Constraints

- Default path is deterministic and offline.
- Search snippets are never treated as evidence.
- Every claim must reference stored evidence and every citation must be auditable.
- Research execution is bounded by round/source/token/cost budgets.
- Checkpoint writes are atomic and resume does not repeat completed rounds.
- Preserve current lesson 13 uncommitted changes.

---

### Task 1: Schemas, local corpus, retriever and evidence extraction

**Files:**
- Create: `hello-agents/projects/14-deep-research/deep_research/schemas.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/corpus.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/retriever.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/evidence.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/__init__.py`
- Create: `hello-agents/tests/test_deep_research.py`

**Interfaces:**
- Produce `ResearchQuery`, `Source`, `Evidence`, `Claim`, `Citation`, `ResearchState`, `FixtureRetriever`, `dedupe_sources`, and `extract_evidence`.

- [ ] Write tests for source metadata, duplicate removal, evidence provenance and claim/evidence association.
- [ ] Run the focused tests and verify they fail because the package does not exist.
- [ ] Implement versioned dataclasses, fixed local sources, retriever failure injection and evidence extraction.
- [ ] Re-run focused tests and verify they pass.

### Task 2: Planner and resumable research engine

**Files:**
- Create: `hello-agents/projects/14-deep-research/deep_research/planner.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/engine.py`
- Modify: `hello-agents/tests/test_deep_research.py`

**Interfaces:**
- Produce `decompose_question`, `ResearchEngine.run`, `ResearchEngine.resume`, and `ResearchEngine.plan`.
- Engine must track round, sources, evidence, claims, citations, warnings, tokens, cost and status.

- [ ] Add failing tests for two-round research, source/token budgets, retriever failure degradation and interrupt/resume.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement bounded round execution, conflict detection, missing-evidence warnings and checkpoint callbacks.
- [ ] Re-run focused tests and verify they pass.

### Task 3: Citation audit, report generation, and artifact storage

**Files:**
- Create: `hello-agents/projects/14-deep-research/deep_research/audit.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/report.py`
- Create: `hello-agents/projects/14-deep-research/deep_research/storage.py`
- Modify: `hello-agents/tests/test_deep_research.py`

**Interfaces:**
- Produce `audit_citations`, `render_report`, `CheckpointStore`, and `ArtifactStore`.
- Audit must reject dangling citations, source mismatches and claims with no evidence.

- [ ] Add failing tests for unsupported citations, conflict uncertainty, checkpoint round-trip and report rendering.
- [ ] Run focused tests and verify expected failures.
- [ ] Implement strict citation validation, deterministic Markdown/JSON output and atomic checkpoint/report writes.
- [ ] Re-run focused tests and verify they pass.

### Task 4: CLI, documentation, progress, and integration verification

**Files:**
- Create: `hello-agents/projects/14-deep-research/deep_research/experiment.py`
- Modify: `hello-agents/projects/14-deep-research/main.py`
- Modify: `hello-agents/projects/14-deep-research/README.md`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/CURRICULUM.md`

**Interfaces:**
- Produce `run_demo(conflict=False, retrieval_failure=False, interrupt_after_round=None, resume_path=None, output_dir=None)` and CLI flags `--demo`, `--json`, `--conflict`, `--retrieval-failure`, `--interrupt-after-round`, `--resume`, and `--output-dir`.

- [ ] Add failing integration tests for CLI JSON output, conflict warning and checkpoint resume.
- [ ] Run integration tests and verify failure before the new CLI exists.
- [ ] Implement the offline orchestrator and CLI without network access.
- [ ] Document the relation to archived lessons 27～32 and the new engineering focus.
- [ ] Run lesson tests, all project offline demos, `git diff --check`, and record unrelated full-suite environment failures.
