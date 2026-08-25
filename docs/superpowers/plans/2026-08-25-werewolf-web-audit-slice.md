# Werewolf Web Audit Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, single-room Web audit slice that automatically advances a deterministic RulePolicy game and exposes an incremental god-view timeline.

**Architecture:** Add a public one-phase `GameEngine.step()` that preserves the existing rule authority. Add `werewolf_arena.web` with a thread-safe in-memory `RoomStore`, a daemon worker, standard-library HTTP routes, and explicit audit/public serializers. Serve a self-contained `web.html` that creates/starts a room and polls audit events every 500ms.

**Tech Stack:** Python 3.11 standard library (`http.server`, `threading`, `urllib`), existing immutable `GameState`/`GameEngine`/`RulePolicy`, browser-native HTML/CSS/JavaScript, `unittest`.

---

### Task 1: Expose deterministic single-phase engine stepping

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write the failing engine contract test**

Create the test module bootstrap exactly as existing Werewolf tests do, then add:

```python
def test_step_advances_one_phase_without_running_to_completion(self):
    state = initial_game(seed=7)
    engine = GameEngine(seed=7)

    stepped = engine.step(state)

    self.assertEqual(stepped.phase, Phase.NIGHT_WOLF_CONFIRM)
    self.assertEqual(stepped.round_number, 1)
    self.assertEqual(stepped.status, "RUNNING")
    self.assertNotEqual(stepped, state)
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run:

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_step_advances_one_phase_without_running_to_completion -v
```

Expected: `AttributeError` because `GameEngine.step` does not exist.

- [ ] **Step 3: Implement the smallest engine change**

Add this public method to `GameEngine`:

```python
def step(self, state: GameState) -> GameState:
    """收集并结算当前阶段一次，供 Web worker 和单步测试复用。"""
    if state.status != "RUNNING":
        return state
    return self._advance_one_phase(state)
```

Change `run()` to call `self.step(state)` inside its existing loop, preserving checkpoint and event callback behavior.

- [ ] **Step 4: Run focused and regression tests**

Run:

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_step_advances_one_phase_without_running_to_completion -v
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
```

Expected: the new test passes and the existing 72 Werewolf tests remain green.

- [ ] **Step 5: Commit the isolated engine change**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/engine.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: expose one-phase werewolf engine stepping"
```

### Task 2: Add the thread-safe single-room runtime

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write failing room lifecycle tests**

Add tests for the public runtime contracts:

```python
def test_room_store_creates_one_room_and_rejects_second_active_room(self):
    store = RoomStore(step_interval=0.001)
    first = store.create(seed=7)
    self.assertEqual(first.state.phase, Phase.NIGHT_WOLF)

    with self.assertRaises(RoomConflictError):
        store.create(seed=18)

    store.close()

def test_room_step_once_returns_incremental_snapshot(self):
    store = RoomStore(step_interval=0.001)
    room = store.create(seed=7)

    before = room.snapshot(after=0)
    room.step_once()
    after = room.snapshot(after=0)

    self.assertEqual(before["cursor"], 0)
    self.assertGreater(after["cursor"], before["cursor"])
    self.assertEqual(after["state"]["phase"], "night_wolf_confirm")
    store.close()

def test_room_worker_reaches_terminal_state(self):
    store = RoomStore(step_interval=0.001, max_rounds=4)
    room = store.create(seed=7)
    room.start()

    self.assertTrue(room.wait_until_done(timeout=2.0))
    self.assertIn(room.snapshot(after=0)["state"]["status"], {"COMPLETED", "DRAW"})
    store.close()
```

- [ ] **Step 2: Run the room tests and verify they fail for missing runtime types**

Run:

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_room_store_creates_one_room_and_rejects_second_active_room -v
```

Expected: import failure for `RoomStore`/`RoomConflictError`.

- [ ] **Step 3: Implement the minimal room runtime**

Implement in `werewolf_arena/web.py`:

- `RoomConflictError` and `RoomNotFoundError` as `Exception` subclasses.
- `Room` fields: `state`, `engine`, `max_rounds`, `step_interval`, `RLock`, `Thread | None`, `stop_event`, `worker_error`.
- `Room.step_once()` acquires the lock, checks `state.status`, calls `engine.step(state)`, applies `finish_draw` if the round limit is exceeded, and stores the new state.
- `Room.start()` is idempotent and starts a daemon worker.
- Worker loop calls `step_once()`, exits on terminal state, catches exceptions into `worker_error`, and sleeps via `Event.wait(step_interval)`.
- `Room.wait_until_done(timeout)` polls the lock-protected status using a monotonic deadline.
- `Room.snapshot(after)` returns a dict containing `state`, `events`, `cursor`, `running`, and optional `worker_error`; `events` is `state.events[after:]` serialized with `to_dict()`.
- `RoomStore.create(seed)` creates `initial_game(seed)` and rejects an existing non-terminal room; `get(game_id)` raises `RoomNotFoundError`; `close()` stops and joins its room worker.

Do not add persistence or external dependencies.

- [ ] **Step 4: Run focused room tests and all existing tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_room_store_creates_one_room_and_rejects_second_active_room hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_room_step_once_returns_incremental_snapshot hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_room_worker_reaches_terminal_state -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
```

Expected: room tests pass and the existing suite remains green.

- [ ] **Step 5: Commit the room runtime**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: add single-room werewolf web runtime"
```

### Task 3: Add audit/public serializers and HTTP API

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write failing HTTP contract tests**

Start a `ThreadingHTTPServer` on port 0 using a handler factory bound to a fresh `RoomStore`. Use `urllib.request.urlopen` and close the server in `addCleanup`. Add tests that assert:

```python
def test_http_create_start_and_incremental_audit(self):
    created = self.request_json("POST", "/api/rooms", {"seed": 7})
    self.assertEqual(created.status, 201)
    game_id = created.payload["game_id"]

    started = self.request_json("POST", f"/api/rooms/{game_id}/start", {})
    self.assertEqual(started.status, 200)

    room = self.store.get(game_id)
    room.step_once()
    audit = self.request_json("GET", f"/api/rooms/{game_id}/audit?after=0")
    self.assertEqual(audit.status, 200)
    self.assertEqual(audit.payload["state"]["phase"], "night_wolf_confirm")
    self.assertEqual(audit.payload["cursor"], len(audit.payload["state"]["events"]))
    self.assertGreaterEqual(len(audit.payload["events"]), 1)

def test_public_endpoint_omits_private_identity_and_events(self):
    created = self.request_json("POST", "/api/rooms", {"seed": 7})
    game_id = created.payload["game_id"]
    room = self.store.get(game_id)
    room.step_once()

    public = self.request_json("GET", f"/api/rooms/{game_id}/public?after=0")
    body = json.dumps(public.payload, ensure_ascii=False)
    self.assertNotIn('"role"', body)
    self.assertNotIn('"pending_actions"', body)
    self.assertNotIn('"public": false', body)

def test_http_errors_are_stable_json(self):
    response = self.request_json("GET", "/api/rooms/missing/audit", expect_error=True)
    self.assertEqual(response.status, 404)
    self.assertEqual(response.payload["error"], "room_not_found")
```

- [ ] **Step 2: Run the focused HTTP tests and verify they fail**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_http_create_start_and_incremental_audit -v
```

Expected: route/handler symbols are missing.

- [ ] **Step 3: Implement the HTTP layer**

Add to `werewolf_arena/web.py`:

- `audit_snapshot(room, after)` returning complete `GameState.to_dict()` and serialized incremental events.
- `public_snapshot(room, after)` returning only game ID, seed, phase, round, status, winner, alive player IDs, public metrics, public events, and cursor.
- `make_handler(store, html_path)` returning a `BaseHTTPRequestHandler` subclass.
- `GET /` serving `web.html` with `text/html; charset=utf-8`.
- `GET /api/rooms/{id}/audit` and `/public` parsing non-negative integer `after`.
- `POST /api/rooms` parsing an optional object body, defaulting seed to 7.
- `POST /api/rooms/{id}/start` starting the room.
- `_send_json` and `_send_error` helpers with stable error codes and `Content-Length`.
- `build_server(host="127.0.0.1", port=8765, store=None)` returning `ThreadingHTTPServer` and keeping a reference to the store for test cleanup.
- `main()` parsing `--host`, `--port`, `--seed`, and `--step-interval`, creating a store, creating the initial room, printing the local URL, and serving until interrupted.

Use URL path segments only; reject malformed paths rather than accepting arbitrary file paths. Do not bind `0.0.0.0` by default.

- [ ] **Step 4: Run focused HTTP tests and all tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
```

Expected: all new Web tests and the existing suite pass.

- [ ] **Step 5: Commit the API layer**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: expose werewolf audit and public web APIs"
```

### Task 4: Build the timeline audit page

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/web.html`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write the failing page contract test**

Add a test that reads `web.html` and asserts it contains these exact user-visible or executable markers: `上帝视角`, `开发 / 裁判回放`, `/api/rooms`, `/audit?after=`, `事件时间线`, `事件详情`, `状态快照`, and `setInterval`.

- [ ] **Step 2: Run the page test and verify it fails because the asset is absent**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_audit_page_contains_timeline_and_polling_contract -v
```

Expected: `FileNotFoundError`.

- [ ] **Step 3: Implement the self-contained page**

Create a no-build HTML page with:

- dark theater-style layout and three-column audit grid;
- seed input plus create/start controls;
- KPI cards for phase, round, alive count, winner, cursor and metrics;
- timeline list with event type, phase and round;
- selected event JSON detail;
- state snapshot JSON panel;
- polling loop using `setInterval(..., 500)` and the cursor returned by the API;
- visible `fetch` error message that leaves the previous snapshot intact;
- HTML escaping before inserting event text;
- explicit local-only “开发 / 裁判回放” warning.

`web.py` must load the HTML from its module directory, not from the process current directory.

- [ ] **Step 4: Run page, HTTP, and full regression tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
git diff --check
```

Expected: all tests pass and the diff has no whitespace errors.

- [ ] **Step 5: Commit the audit page**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.html hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: add werewolf timeline audit page"
```

### Task 5: Document the local Web entry point and verify the vertical slice

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/FLOW.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/PROGRESS.md`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write the CLI smoke test**

Run the module in a subprocess with an ephemeral port and terminate after confirming the startup line contains `http://127.0.0.1:` and `/`. The test must not require a network dependency and must terminate the child in `finally`.

- [ ] **Step 2: Run the smoke test and verify it fails before documentation wiring**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_web_module_starts_local_server -v
```

Expected: module startup or URL output is not yet implemented.

- [ ] **Step 3: Add documented usage and status updates**

Document:

```bash
cd hello-agents/projects/16-graduation-project
python -m werewolf_arena.web --port 8765 --seed 7
```

Explain that the page is development/court replay only, uses automatic RulePolicy, is local-only, and does not yet support human Action submission or persistence. Update the flow diagram with `RoomStore -> GameEngine.step -> audit polling`, and mark the Web audit vertical slice complete while leaving authentication, persistence, multi-room and player UI open.

- [ ] **Step 4: Run the complete verification set**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
git diff --check
git status --short
```

Expected: all tests pass; only intentionally untracked `.superpowers/` remains outside the implementation commits.

- [ ] **Step 5: Commit documentation and final verification**

```bash
git add hello-agents/PROGRESS.md hello-agents/projects/16-graduation-project/FLOW.md hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md hello-agents/projects/16-graduation-project/README.md hello-agents/tests/test_werewolf_web.py
git commit -m "docs: document werewolf web audit slice"
```

Re-run the full verification set after the commit before reporting completion.

---

## Summary for Wave

### 变更文件清单

- `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- `hello-agents/projects/16-graduation-project/werewolf_arena/web.html`
- `hello-agents/tests/test_werewolf_web.py`
- `hello-agents/projects/16-graduation-project/README.md`
- `hello-agents/projects/16-graduation-project/FLOW.md`
- `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- `hello-agents/PROGRESS.md`

### 实现步骤概览

1. 暴露可复用的单阶段引擎入口。
2. 建立带锁的内存单房间和自动 RulePolicy worker。
3. 增加裁判/公开快照 API 与增量事件游标。
4. 实现三列时间线审计台和 500ms 轮询。
5. 补充模块启动命令、项目文档和全量验证。

### 潜在风险

- 后台线程测试需要可靠的超时和清理，避免测试悬挂。
- 裁判端点没有认证，只能保持回环监听并明确禁止公网使用。
- 页面以完整审计 JSON 为主，普通玩家视图仍是后续独立切片。

### 预计复杂度

中
