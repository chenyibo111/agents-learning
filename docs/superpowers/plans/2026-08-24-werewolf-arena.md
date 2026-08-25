# Werewolf Arena Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a replayable six-agent werewolf game with private observations, authoritative rules, pluggable model policies, recovery, and offline evaluation.

**Architecture:** The game engine owns the complete state and advances phases. Visibility projection gives each Policy a least-privilege observation; policies propose structured actions, while rules validate and emit events. JSON checkpoints and JSONL traces make games replayable and auditable.

**Tech Stack:** Python 3.14 standard library, dataclasses, `unittest`, JSON, optional environment-based model adapter.

**Spec:** `docs/superpowers/specs/2026-08-24-werewolf-arena-design.md`

## Global Constraints

- Default execution is offline and must never call network services.
- The engine, not an LLM, is the sole authority for game state and victory.
- A Policy receives `PlayerObservation`, never `GameState`.
- Public speech is untrusted data and is limited to 240 characters.
- Persisted JSON uses schema version `1.0` and writes atomically.
- No secrets may be stored in checkpoints, traces, reports, tests, or documentation.

---

### Task 1: Domain schema and visibility contract

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/schemas.py`
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

**Interfaces:**
- Produces `GameState`, `PlayerState`, `Action`, `Event`, `PlayerObservation` and `observation_for(state, player_id)`.

- [x] Write a test proving that a villager Observation excludes role assignments, seer results, witch resources, and wolf teammates.
- [x] Run `python -m unittest hello-agents/tests/test_werewolf_arena.py -v`; verified import failure before implementation.
- [x] Implement serializable immutable schemas and explicit event recipients.
- [x] Implement least-privilege observation projection and rerun the test.

### Task 2: Authoritative game rules

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/rules.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

**Interfaces:**
- Consumes `GameState`, `Action`, `Event`.
- Produces `initial_game(seed)`, `submit_action(state, action)`, `resolve_night(state)`, `resolve_vote(state)`, `check_winner(state)`.

- [x] Write failing tests for deterministic role distribution, illegal actions, matched wolf attacks, witch saves, and tied votes.
- [x] Run the focused test module; verify failure before rule modules existed.
- [x] Implement minimum rules and event creation to satisfy each test.
- [x] Rerun focused tests after each rule group.

### Task 3: Policy and phase engine

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/policies.py`
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

**Interfaces:**
- Produces `Policy.decide(observation) -> Action`, `RulePolicy`, `ScriptedModelAdapter`, `LLMPolicy`, `GameEngine.run()` and `GameEngine.resume()`.

- [x] Write failing tests for a full deterministic game, model-policy JSON fallback, and max-round draw.
- [x] Run tests and verify failure before production code exists.
- [x] Implement phase orchestration and deterministic fallback policies.
- [x] Rerun focused tests and verify the complete game progresses without an LLM.

### Task 4: Persistence, evaluation and CLI

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/storage.py`
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/evaluation.py`
- Modify: `hello-agents/projects/16-graduation-project/main.py`
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/CURRICULUM.md`
- Test: `hello-agents/tests/test_werewolf_arena.py`

**Interfaces:**
- Produces `CheckpointStore`, `ArtifactStore`, `evaluate_game(state)`, CLI `--demo --json --seed --max-rounds --output-dir --resume`.

- [x] Write failing tests for checkpoint resume equality, privacy audit, JSON CLI output and artifacts.
- [x] Run tests and confirm missing persistence or CLI behavior.
- [x] Implement atomic persistence, reporting and the CLI.
- [x] Update documentation with configuration, limitations, tests and six-agent rule set.
- [x] Run focused and related project regression tests, then `git diff --check`.
