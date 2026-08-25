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

---

### Task 5: 补充女巫、隐藏投票与轮换发言规则

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/rules.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/schemas.py` (if phase/order metadata needs persistence)
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/FLOW.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/ISSUES.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/FIXES.md`
- Test: `hello-agents/tests/test_werewolf_arena.py`

**Confirmed rules:**

- [x] 当两名狼人没有形成袭击目标时，女巫不能使用解药；`witch_save` 必须被拒绝，解药不能消耗，也不能产生 `night_saved(target=null)` 事件。
- [x] 投票阶段所有玩家独立提交行动；投票提交期间不生成公开的个人投票事件，后续玩家不能从 Observation 看到前面玩家的投票。
- [x] 所有存活玩家完成投票后，一次性公开每名玩家的具体票型和总票数，再按唯一最高票出局或平票无人出局。
- [x] 白天发言采用固定座位的轮换首发顺序：第 1 轮从 `alice` 开始，第 2 轮从 `bob` 开始，之后按固定座位顺时针轮换；死亡玩家跳过，每名存活玩家发言一次，后续玩家可以看到前序发言。
- [x] 发言顺序必须可由 seed、轮次和存活名单确定，并能在 checkpoint 恢复后保持一致。

**Implementation checklist:**

- [x] 先补充女巫无袭击目标、投票期间隐私、投票结束公开票型、轮换发言顺序和恢复一致性的失败测试。
- [x] 修改规则层，使投票提交阶段只保存 pending action，不立即产生公开 `vote_cast` 事件。
- [x] 在投票阶段结算后生成包含个人票型、票数和结算结果的单次公开事件。
- [x] 修改 Engine 的讨论阶段调度，使用轮换后的 speaker order，而不是固定玩家列表顺序。
- [x] 更新 LLM Prompt 和玩家 Observation，明确投票期间看不到其他人的投票，并暴露当前发言顺序。
- [x] 运行第 16 课专项测试、全量测试和 `git diff --check`；专项 48 项通过，全量 250 项通过（4 项跳过）。

### Task 6: LLM 目标语义提前校验

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/policies.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/ISSUES.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/FIXES.md`
- Test: `hello-agents/tests/test_werewolf_arena.py`

**Implementation checklist:**

- [x] 为已死亡目标、自己、狼人队友和错误解药目标补充 Policy 层失败测试。
- [x] 在 `LLMPolicy` 入口校验狼人击杀、预言家查验、女巫毒药和解药目标语义，失败时安全降级为 `noop`。
- [x] 保留 `rules.py` 最终校验，并验证不会产生 `action_rejected`。
- [x] 运行专项 52 项、全量 254 项（4 项跳过）和 `git diff --check`。
