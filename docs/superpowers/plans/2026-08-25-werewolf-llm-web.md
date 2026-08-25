# Werewolf Real LLM Web Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the local single-room Web audit slice so all six players can use the configured real LLM with non-blocking incremental request tracing and persisted replay artifacts.

**Architecture:** Keep `GameEngine`, `rules.py`, `LLMPolicy`, and `OpenAICompatibleModelAdapter` as the authority. Extend `werewolf_arena.web` with a server-selected `rule|llm` policy mode, a shared adapter plus six policies, a thread-safe request-trace collector, separate state/step locks, dual event/request cursors, and per-room artifact persistence. Keep the browser on 500ms polling and expose only redacted request summaries.

**Tech Stack:** Python 3.11 standard library, existing OpenAI-compatible synchronous adapter, existing `RequestTraceStore`/`ArtifactStore`, browser-native HTML/CSS/JavaScript, `unittest`.

---

### Task 1: Inject RulePolicy or six LLMPolicy instances into a room

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write the failing policy-mode and trace test**

Add a fake adapter test using the existing `ScriptedModelAdapter`:

```python
def test_llm_room_creates_six_policies_and_collects_redacted_requests(self):
    adapter = ScriptedModelAdapter(['{"action_type": "noop"}'])
    store = RoomStore(policy_mode="llm", model_adapter=adapter, step_interval=60.0)
    room = store.create(seed=7)

    room.step_once()
    snapshot = room.snapshot(after=0, request_after=0)

    self.assertEqual(snapshot["policy_mode"], "llm")
    self.assertEqual(len(adapter.calls), 2)
    self.assertEqual(snapshot["request_cursor"], 2)
    self.assertEqual(len(snapshot["llm_requests"]), 2)
    self.assertNotIn("Prompt", json.dumps(snapshot["llm_requests"]))
    self.assertNotIn("response", json.dumps(snapshot["llm_requests"]))
    store.close()
```

The two calls are the two wolves in the first `NIGHT_WOLF` phase. Extend the test bootstrap import to include `ScriptedModelAdapter`.

- [ ] **Step 2: Run the focused test and verify it fails**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_llm_room_creates_six_policies_and_collects_redacted_requests -v
```

Expected: `RoomStore.__init__` rejects the unknown `policy_mode` argument or the snapshot lacks request fields.

- [ ] **Step 3: Implement policy injection and the collector**

In `web.py`:

- Add `RequestTraceCollector` with an `RLock`, `append(record)`, and `snapshot(after)`; append to an optional `RequestTraceStore` after copying the record.
- Add `policy_mode`, `model_adapter`, and `output_root` parameters to `RoomStore`; accept only `rule` and `llm`.
- Add `build_policies(seed, policy_mode, model_adapter, on_request)` that returns six `LLMPolicy` objects in `llm` mode and `{}` in `rule` mode.
- Pass the resulting mapping and seed into `GameEngine` when constructing `Room`.
- Extend `Room.snapshot(after=0, request_after=0)` with `policy_mode`, redacted model name, `llm_requests`, `request_cursor`, and `artifacts` fields while preserving existing event fields.
- For tests, allow an injected adapter; production `main()` will create the adapter once from environment.

Do not expose adapter endpoint or API key in any snapshot.

- [ ] **Step 4: Run focused and regression tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_llm_room_creates_six_policies_and_collects_redacted_requests -v
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena
```

Expected: the new test and all 72 existing Werewolf tests pass.

- [ ] **Step 5: Commit**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: inject real llm policies into web rooms"
```

### Task 2: Make audit polling non-blocking during model calls

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write the failing concurrency test**

Add a `BlockingAdapter` in the test module. Its `complete()` sets `started`, waits on `release`, then returns `ModelResponse('{"action_type":"noop"}')`. Add:

```python
def test_audit_snapshot_is_available_while_llm_call_is_blocked(self):
    adapter = BlockingAdapter()
    store = RoomStore(policy_mode="llm", model_adapter=adapter, step_interval=0.0)
    room = store.create(seed=7)
    worker = threading.Thread(target=room.step_once)
    worker.start()
    self.assertTrue(adapter.started.wait(timeout=1.0))

    started_at = time.monotonic()
    snapshot = room.snapshot(after=0, request_after=0)
    elapsed = time.monotonic() - started_at

    self.assertLess(elapsed, 0.2)
    self.assertEqual(snapshot["state"]["phase"], "night_wolf")
    adapter.release.set()
    worker.join(timeout=1.0)
    store.close()
```

- [ ] **Step 2: Run it and verify it fails or exceeds the timeout**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_audit_snapshot_is_available_while_llm_call_is_blocked -v
```

Expected: the current room-wide lock blocks `snapshot()` until the fake model releases.

- [ ] **Step 3: Separate state and step locks**

Refactor `Room` so `_state_lock` protects state reads/writes, `_step_lock` serializes `step_once()`, and the collector has its own lock. `step_once()` must:

1. acquire `_step_lock`;
2. read the current state under `_state_lock`;
3. call `engine.step()` without holding `_state_lock`;
4. publish the returned state under `_state_lock`;
5. set the done event after a terminal state.

Update `running`, `_summary`, `snapshot`, `public_snapshot`, `stop`, and `wait_until_done` to use `_state_lock`. Do not permit two overlapping `step_once()` calls.

- [ ] **Step 4: Run concurrency and full Web tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
```

Expected: all Web tests pass, including the blocked-call test.

- [ ] **Step 5: Commit**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: keep llm audit polling responsive"
```

### Task 3: Add dual-cursor audit API and public isolation

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write failing API tests**

Add tests that create an injected-LLM room and assert:

```python
def test_audit_api_returns_independent_event_and_request_cursors(self):
    created = self.request_json("POST", "/api/rooms", {"seed": 7})
    room = self.http_store.get(created.payload["game_id"])
    room.step_once()
    response = self.request_json("GET", f"/api/rooms/{room.game_id}/audit?after=0&request_after=1")

    self.assertEqual(response.payload["cursor"], len(response.payload["state"]["events"]))
    self.assertEqual(response.payload["request_cursor"], 2)
    self.assertEqual(len(response.payload["llm_requests"]), 1)
    self.assertEqual(response.payload["policy_mode"], "llm")

def test_public_llm_snapshot_omits_request_traces_and_private_state(self):
    created = self.request_json("POST", "/api/rooms", {"seed": 7})
    room = self.http_store.get(created.payload["game_id"])
    room.step_once()
    response = self.request_json("GET", f"/api/rooms/{room.game_id}/public?after=0&request_after=0")
    body = json.dumps(response.payload, ensure_ascii=False)
    self.assertNotIn("llm_requests", body)
    self.assertNotIn('"role"', body)
    self.assertNotIn('"pending_actions"', body)
    self.assertNotIn('"public": false', body)
```

- [ ] **Step 2: Run focused API tests and verify they fail**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_audit_api_returns_independent_event_and_request_cursors -v
```

Expected: the handler does not parse `request_after` and the response lacks `llm_requests`/`request_cursor`.

- [ ] **Step 3: Implement the API contract**

Extend `_cursor` to parse named query parameters. `GET /audit` must parse both `after` and `request_after` and pass both to `Room.snapshot`. `GET /public` must ignore request cursors and return no LLM traces or cost details. Add non-sensitive `policy_mode`, model name, pricing-configured flag, and artifact summary to audit responses.

Use stable 400 `invalid_cursor` errors for malformed or negative values. Keep existing 404/409 error behavior.

- [ ] **Step 4: Run Web and regression tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena
```

- [ ] **Step 5: Commit**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: expose realtime llm audit cursors"
```

### Task 4: Persist per-room LLM artifacts and add the `--policy llm` CLI

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write failing artifact and configuration tests**

Add tests that:

- create a room with a temporary `output_root`, step it to a terminal state, and assert `checkpoint.json`, `events.jsonl`, `report.json`, `spectator.html`, `god_view.html`, and `llm_requests.jsonl` exist;
- launch `python -m werewolf_arena.web --policy llm --port 0` with endpoint/key/model explicitly empty and assert non-zero exit without the key text in stderr;
- assert `GET /api/rooms` reports `policy_mode == "llm"`, model name, and `pricing_configured` without endpoint or key.

- [ ] **Step 2: Run the focused tests and verify the missing behavior**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_llm_room_persists_replay_artifacts -v
```

Expected: no room output directory or LLM CLI policy option exists yet.

- [ ] **Step 3: Implement persistence and startup configuration**

For each room:

- allocate a unique directory under `output_root` using `ArtifactStore.default_run_directory`;
- create a `RequestTraceStore` and collector for that directory;
- after each completed phase call `ArtifactStore.write` with `evaluate_game(state, offline=policy_mode != "llm")` and `god_view=True`;
- on terminal/error state write the same artifacts one final time;
- return only relative artifact names or a local run directory label in API JSON.

Add `--policy {rule,llm}`, `--max-rounds`, `--output-root`, and existing timing/host/port options to `main()`. In LLM mode, construct the adapter once with `OpenAICompatibleModelAdapter.from_environment()` before opening the server. Leave the process unstarted when configuration raises `LLMConfigurationError`.

- [ ] **Step 4: Run artifact, CLI, Web and regression tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena
```

- [ ] **Step 5: Commit**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.py hello-agents/tests/test_werewolf_web.py
git commit -m "feat: persist web llm replay artifacts"
```

### Task 5: Add the real-LLM request flow to the audit page

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/web.html`
- Test: `hello-agents/tests/test_werewolf_web.py`

- [ ] **Step 1: Write the failing page contract test**

Extend the existing marker test with `REAL LLM`, `llm_requests`, `request_after=`, `请求流`, `truncated`, `fallback_reason`, and `pricing_configured`.

- [ ] **Step 2: Run the page test and verify the missing markers**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web.WerewolfWebTests.test_audit_page_contains_llm_request_flow -v
```

Expected: the current page has no request cursor or LLM request-flow panel.

- [ ] **Step 3: Implement the page changes**

Add:

- an LLM mode/model badge and pricing warning;
- `requestCursor` alongside event `cursor`;
- polling URL `/audit?after=${cursor}&request_after=${requestCursor}`;
- an append-only request-flow panel with escaped Agent/phase/status/latency/tokens/cost/truncation/fallback fields;
- KPI cards for request cursor, total requests, total latency, total tokens, cost and fallback count;
- “等待模型响应” status when the room is running but no new state event has arrived;
- preservation of the last successful state/request list on fetch errors.

Do not render Prompt, raw response, endpoint or authorization fields even if a malformed server response contains them.

- [ ] **Step 4: Run page, Web, and full tests**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/web.html hello-agents/tests/test_werewolf_web.py
git commit -m "feat: show realtime llm request flow"
```

### Task 6: Update project docs and run the real LLM smoke test

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/FLOW.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/PROGRESS.md`

- [ ] **Step 1: Document the LLM Web command and artifact locations**

Document this command and explain that `.env` is loaded automatically:

```bash
cd hello-agents/projects/16-graduation-project
python -m werewolf_arena.web --policy llm --port 8767 --seed 7 --max-rounds 4 --step-interval 0.5
```

Document that the browser uses `http://127.0.0.1:8767/`, the audit API has two cursors, and the run directory contains `llm_requests.jsonl` plus the replay artifacts. Mark the local real-LLM audit slice complete while keeping authentication, human players, multi-room and SSE/WebSocket open.

- [ ] **Step 2: Run the complete automated verification**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
git diff --check
```

Expected: all tests pass; real-model tests remain skipped unless explicitly enabled.

- [ ] **Step 3: Run one explicit real LLM Web smoke test**

With `.env` configured and prices set, start the command above, open the browser, click “开始自动回放”, and capture:

- final `status` and `winner`;
- `request_cursor` / total logical requests;
- truncated request count and fallback count;
- average/P95 latency from `llm_requests.jsonl`;
- `cost_usd` from `GameState.metrics` and `report.json`;
- final run directory path.

Never include the API key, Prompt, raw response, or authorization header in notes or screenshots.

- [ ] **Step 4: Commit documentation and final verification**

```bash
git add hello-agents/PROGRESS.md hello-agents/projects/16-graduation-project/FLOW.md hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md hello-agents/projects/16-graduation-project/README.md
git commit -m "docs: document real llm web audit"
.venv311/bin/python -m unittest discover -s hello-agents/tests
git diff --check
```

---

## Summary for Wave

### 变更文件清单

- `hello-agents/projects/16-graduation-project/werewolf_arena/web.py`
- `hello-agents/projects/16-graduation-project/werewolf_arena/web.html`
- `hello-agents/tests/test_werewolf_web.py`
- `hello-agents/projects/16-graduation-project/README.md`
- `hello-agents/projects/16-graduation-project/FLOW.md`
- `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- `hello-agents/PROGRESS.md`

### 实现步骤概览

1. 为 Web 房间注入离线/真实 LLM Policy，并收集双游标请求追踪。
2. 分离状态锁与阶段锁，使模型请求期间审计 API 不阻塞。
3. 接入双游标 API、公开数据隔离、runs 工件和 `--policy llm` 启动参数。
4. 更新时间线页面展示真实 LLM 请求流、指标和费用。
5. 更新文档，完成自动化验证并执行一次显式真实网关 smoke test。

### 潜在风险

- 真实请求耗时和失败会让单局运行时间明显增加；worker 必须保持单房间阶段串行。
- 无价格环境变量时费用会是 0，文档和页面必须明确这是未配置而不是免费。
- 裁判审计 API 仍包含完整身份和私有事件，只允许本地开发/裁判使用。
- 真实 smoke test 需要用户现有 `.env` 的 endpoint、key、model 和价格配置，不应由自动化测试代替。

### 预计复杂度

中高
