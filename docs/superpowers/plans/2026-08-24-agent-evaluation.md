# Agent Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, replayable, production-oriented Agent evaluation engine for lesson 12.

**Architecture:** A versioned dataset feeds deterministic policies through a runner that records trace and cost data. Hard-rule metrics, Judge results, strategy comparison, Pareto analysis, artifact storage, and release gates remain separate modules and are combined by one experiment orchestrator.

**Tech Stack:** Python standard library, `dataclasses`, `unittest`, JSON/JSONL, atomic file replacement; no new runtime dependency and no external model API in the offline path.

**Spec:** `docs/superpowers/specs/2026-08-24-agent-evaluation-design.md`

## Global Constraints

- Keep the default path deterministic and offline.
- Do not mix hard-rule metrics with Judge scores.
- Preserve the existing uncommitted lesson 11 changes.
- Use schema version `1.0` and dataset version `agent-eval-v1`.
- Every new behavior gets a failing test before implementation.

---

### Task 1: Domain schemas and versioned dataset

**Files:**
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/schemas.py`
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/dataset.py`
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/__init__.py`
- Create: `hello-agents/tests/test_agent_evaluation.py`

**Interfaces:**
- Produce `EvalCase`, `ToolCall`, `TraceEvent`, `AgentRun`, `JudgeResult`, `MetricReport`, `GateResult` and `EVAL_DATASET_VERSION`.
- Produce `evaluation_cases()` and `get_case(case_id)` with stable case ids and scenario labels.

- [ ] Write tests proving the dataset version is stable, cases contain required fields, and unknown case ids fail with `ValueError`.
- [ ] Run `python -m unittest hello-agents/tests/test_agent_evaluation.py -v`; verify the new imports fail before implementation.
- [ ] Implement frozen dataclasses and a fixed dataset covering normal, boundary, tool failure, prompt injection and evidence missing cases.
- [ ] Re-run the focused tests and verify they pass.

### Task 2: Runner, replay data, and hard metrics

**Files:**
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/runner.py`
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/metrics.py`
- Modify: `hello-agents/tests/test_agent_evaluation.py`

**Interfaces:**
- Produce `run_case(strategy, case) -> AgentRun`, `run_dataset(strategy, cases=None) -> list[AgentRun]`, `compute_metrics(runs) -> MetricReport`, and `replay_run(run) -> list[TraceEvent]`.
- Hard metrics must calculate success, steps, latency, tokens, cost, safety violations, tool correctness and evidence completeness.

- [ ] Add failing tests for a successful case, a safety failure, metric aggregation and exact trace replay.
- [ ] Run the focused tests and verify failures are due to missing runner/metrics behavior.
- [ ] Implement two deterministic strategies and the runner with explicit trace events and deterministic cost formulas.
- [ ] Implement metrics from run data only; do not call Judge code.
- [ ] Run focused tests and verify they pass.

### Task 3: Judge separation, calibration, strategy comparison, and Pareto frontier

**Files:**
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/judges.py`
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/comparison.py`
- Modify: `hello-agents/tests/test_agent_evaluation.py`

**Interfaces:**
- Produce `judge_run(run) -> JudgeResult`, `calibrate_judges(results, human_labels) -> dict`, `compare_strategies(reports) -> dict`, and `pareto_frontier(reports) -> list[str]`.
- Judge output must contain rubric, score, reason and `human_calibrated`; it must not mutate hard metrics.

- [ ] Add failing tests showing Judge results are separate, calibration changes only calibration metadata, and dominated strategies are excluded from the frontier.
- [ ] Run focused tests and verify the expected failures.
- [ ] Implement deterministic rubric scoring, calibration aggregation, metric comparison and Pareto dominance for higher success/lower cost/lower latency.
- [ ] Run focused tests and verify they pass.

### Task 4: Release gates and artifact storage

**Files:**
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/gate.py`
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/storage.py`
- Modify: `hello-agents/tests/test_agent_evaluation.py`

**Interfaces:**
- Produce `evaluate_release_gate(report, baseline=None) -> GateResult`, `ArtifactStore.save_run(...)`, and `ArtifactStore.load_run(...)`.
- Gate output must include `passed`, threshold values, failed metrics and failed case ids.

- [ ] Add failing tests for a passing report, safety failure, baseline cost regression, and artifact round-trip.
- [ ] Run focused tests and verify failures.
- [ ] Implement explicit threshold checks and atomic JSON/JSONL writes with schema validation on load.
- [ ] Run focused tests and verify they pass.

### Task 5: Experiment orchestrator, CLI, documentation, and integration verification

**Files:**
- Create: `hello-agents/projects/12-agent-evaluation/agent_evaluation/experiment.py`
- Create: `hello-agents/projects/12-agent-evaluation/main.py`
- Create: `hello-agents/projects/12-agent-evaluation/README.md`
- Modify: `hello-agents/tests/test_projects.py`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/CURRICULUM.md`

**Interfaces:**
- Produce `run_experiment()` and CLI flags `--demo`, `--json`, `--strategy`, `--output-dir`, and `--replay-case`.
- Report must include dataset version, strategy reports, Judge section, comparison, Pareto frontier, gate result, and artifact paths.

- [ ] Add failing integration tests for CLI demo, JSON report, artifact directory and replay output.
- [ ] Run the integration tests and verify failure before the CLI exists.
- [ ] Implement orchestrator and CLI without requiring network or model credentials.
- [ ] Document the three-layer learning scope and commands.
- [ ] Run focused lesson tests, project offline demos, `git diff --check`, and the full available test suite; record unrelated optional dependency failures if any.
