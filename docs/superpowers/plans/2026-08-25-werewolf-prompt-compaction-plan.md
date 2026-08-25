# Werewolf Prompt Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce redundant LLM Prompt tokens in the Werewolf Arena without changing authorized business facts, action protocol, or game rules.

**Architecture:** Keep authorization filtering in `observation_for`; add a pure compact projection for already-authorized events; have `model_prompts` serialize compact events directly as an array instead of embedding a JSON string. Preserve event phase, round, type, and full payload, and drop only audit metadata that the model does not need.

**Tech Stack:** Python 3.11, `unittest`, dataclasses, JSON serialization.

---

### Task 1: Lock down the compact event contract

**Files:**
- Modify: `hello-agents/tests/test_werewolf_arena.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`

- [x] **Step 1: Write failing tests**

Add tests that assert `model_prompts` keeps each event's `round_number`, `phase`, `event_type`, and complete `payload`; removes `event_id`, `public`, `recipients`, and `rule`; emits `untrusted_public_transcript` as an array; and preserves non-boilerplate private memory while omitting the fixed boilerplate memory.

- [x] **Step 2: Run the focused tests and verify the expected failures**

Run:

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_model_prompt_compacts_authorized_events_without_changing_facts -v
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_model_prompt_keeps_real_private_memory -v
```

Expected: the new behavior assertions fail against the current full event dictionaries and string transcript.

### Task 2: Implement semantic-preserving Prompt compaction

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`

- [x] **Step 1: Add a pure `compact_event` helper**

Return a new dictionary with `round`, `phase`, `type`, and the original `payload` value. Do not mutate the source event or payload.

- [x] **Step 2: Apply the helper after authorization filtering**

Use it for both public and private event lists. Keep all role/resource fields and all custom private memory except the exact fixed boilerplate string.

- [x] **Step 3: Serialize the transcript as a JSON array**

Pass the compact public events directly as `untrusted_public_transcript`; do not call `json.dumps` on that list before placing it in the outer Prompt object.

- [x] **Step 4: Run the focused tests and verify they pass**

Run the two focused tests above, then run:

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
```

Expected: all Werewolf Arena tests pass.

### Task 3: Record and verify the change

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/ISSUES.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/FIXES.md`

- [x] **Step 1: Update I-008 with the implemented scope and validation**

Record that only redundant Prompt representation and audit metadata were removed; no semantic summary or rule change was introduced.

- [x] **Step 2: Add a concise fix entry**

Record the compact event projection, direct array serialization, and test validation.

- [x] **Step 3: Run final verification**

Run:

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py'
git diff --check
```

Expected: all tests pass and `git diff --check` produces no output.
