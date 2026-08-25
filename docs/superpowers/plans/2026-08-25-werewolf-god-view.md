# Werewolf God View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (or superpowers:subagent-driven-development) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在显式 `--god-view` 下生成独立的开发/裁判上帝视角页面，展示完整 GameState 和事件审计，同时保持普通观众页的隐私边界。

**Architecture:** 新增 `god_view.py` 作为完整状态到自包含 HTML 的纯展示层；`ArtifactStore.write()` 通过显式布尔开关决定是否写入 `god_view.html`；`main.py` 增加 `--god-view` 并将工件路径纳入 JSON payload。普通 `spectator.html` 继续只消费公开事件，两个页面不共享完整状态序列化入口。

**Tech Stack:** Python 3.11 标准库、dataclasses、`unittest`、HTML escaping、内联 HTML/CSS/JavaScript；不引入前端框架、WebSocket、HTTP API 或数据库。

**Spec:** `docs/superpowers/specs/2026-08-25-werewolf-god-view-design.md`

---

### Task 1: CLI 开关与 ArtifactStore 契约

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/main.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/storage.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [ ] **Step 1: 写失败测试，锁定显式开关行为。**

在 `WerewolfArenaTests` 增加两个测试：一个调用 `ArtifactStore.write(state, report)`，断言默认 artifacts 没有 `god_view`；另一个通过 subprocess 调用 `main.py --god-view --json --output-dir <tempdir>`，解析 stdout JSON，断言 `artifacts["god_view"]` 存在且文件存在。

```python
def test_artifact_store_only_writes_god_view_when_enabled(self):
    state = GameEngine(seed=7).run(max_rounds=1)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        normal = ArtifactStore(root / "normal").write(state, evaluate_game(state))
        god = ArtifactStore(root / "god").write(state, evaluate_game(state), god_view=True)

        self.assertNotIn("god_view", normal)
        self.assertNotIn("god_view.html", {path.name for path in (root / "normal").iterdir()})
        self.assertTrue(Path(god["god_view"]).exists())

def test_cli_god_view_flag_reports_god_view_artifact(self):
    with tempfile.TemporaryDirectory() as directory:
        result = subprocess.run(
            [sys.executable, str(PROJECT / "main.py"), "--demo", "--seed", "7",
             "--max-rounds", "1", "--json", "--god-view", "--output-dir", directory],
            capture_output=True, text=True, check=True,
        )
    payload = json.loads(result.stdout)
    self.assertTrue(Path(payload["artifacts"]["god_view"]).exists())
```

- [ ] **Step 2: 运行测试确认当前实现失败。**

Run:

```bash
.venv311/bin/python -m unittest \
  hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_artifact_store_only_writes_god_view_when_enabled \
  hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_cli_god_view_flag_reports_god_view_artifact -v
```

Expected: `ArtifactStore.write()` 不接受 `god_view` 参数，且 CLI 不识别 `--god-view`。

- [ ] **Step 3: 实现最小开关链路。**

将 `ArtifactStore.write()` 签名扩展为 `write(state, report, god_view=False)`；始终写入现有三类工件和 `spectator.html`，只有 `god_view=True` 时导入并调用 `render_god_view_html(state)`，写入 `god_view.html` 并增加 artifacts 路径。`main.py` 增加 `parser.add_argument("--god-view", action="store_true")`，并将 `god_view=args.god_view` 传入存储层。不要把完整状态放入普通观战页面。

- [ ] **Step 4: 运行开关测试确认通过。**

Run the same two unittest targets from Step 2. Expected: `OK`.

- [ ] **Step 5: Commit the isolated integration change.**

```bash
git add hello-agents/projects/16-graduation-project/main.py \
  hello-agents/projects/16-graduation-project/werewolf_arena/storage.py \
  hello-agents/tests/test_werewolf_arena.py
git commit -m "feat: add god view artifact flag"
```

### Task 2: 上帝视角 HTML 渲染器

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/god_view.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [ ] **Step 1: 写失败测试，锁定完整数据和转义。**

增加 `test_god_view_contains_private_audit_data_and_escapes_text`：用 `replace(initial_game(seed=7), events=(...))` 构造包含狼人私聊、查验、女巫用药、身份和带 `<script>` 的公开发言的状态，调用 `render_god_view_html(state)`，断言包含角色、私有事件类型、`recipients`、规则诊断字段和转义后的脚本；同时断言不是把完整 `state.to_dict()` 直接嵌入脚本变量。

```python
def test_god_view_contains_private_audit_data_and_escapes_text(self):
    state = replace(initial_game(seed=7), events=(
        Event("private", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message",
              {"speaker": "bob", "text": "<script>secret</script>"},
              public=False, recipients=("bob", "eve")),
        Event("inspect", 1, Phase.NIGHT_SEER, "inspection_result",
              {"target": "alice", "alignment": "good"},
              public=False, recipients=("frank",)),
    ))
    html = render_god_view_html(state)
    self.assertIn("wolf_negotiation_message", html)
    self.assertIn("inspection_result", html)
    self.assertIn("wolf", html)
    self.assertIn("&lt;script&gt;secret&lt;/script&gt;", html)
    self.assertIn("recipients", html)
    self.assertNotIn("window.__GAME_STATE__", html)
```

- [ ] **Step 2: 运行测试确认当前模块尚未实现。**

Run:

```bash
.venv311/bin/python -m unittest \
  hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_god_view_contains_private_audit_data_and_escapes_text -v
```

Expected: `ModuleNotFoundError` 或 `ImportError`，因为 `god_view.py` 尚不存在。

- [ ] **Step 3: 实现自包含时间线审计页。**

实现 `render_god_view_html(state: GameState) -> str`：

1. 复用阶段中文标签和安全 `_safe()` 转义；
2. 顶部显示 game ID、seed、轮次、阶段、status、winner、存活数、规则拒绝数；
3. 左侧逐事件遍历 `state.events`，保留源事件的轮次、阶段、事件类型、payload、`public` 和 recipients，私有/拒绝事件使用显著标签；每个事件卡带有唯一 `data-event-id`；
4. 右侧显示所有玩家的 player ID、role、alive、阵营和女巫资源；
5. 右侧显示选中事件的静态诊断摘要和转义后的 JSON；
6. 用内联 CSS 实现深色审计台布局，用少量内联 JavaScript 实现事件卡片点击高亮；
7. 不把 `state.to_dict()` 作为 JavaScript 全局对象注入，不读取未经筛选的 HTML；所有动态值都经过 `html.escape(..., quote=True)`。

- [ ] **Step 4: 运行渲染测试确认通过。**

Run the Step 2 test. Expected: `OK`.

- [ ] **Step 5: Commit the renderer.**

```bash
git add hello-agents/projects/16-graduation-project/werewolf_arena/god_view.py \
  hello-agents/tests/test_werewolf_arena.py
git commit -m "feat: render werewolf god view audit page"
```

### Task 3: 隐私回归、文档和端到端验证

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/FLOW.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/README.md`
- Modify: `hello-agents/PROGRESS.md`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [ ] **Step 1: 写失败测试，确认普通观众页与上帝页隔离。**

增加一个 CLI 回归测试：不传 `--god-view` 时 artifacts 不含 `god_view`；传入 `--god-view` 时同时断言 `spectator.html` 不包含 `wolf_negotiation_message`，`god_view.html` 包含该字段和角色数据。测试两个文件的内容，而不是只测试路径。

```python
def test_god_view_is_separate_from_public_spectator(self):
    with tempfile.TemporaryDirectory() as directory:
        normal_dir = Path(directory) / "normal"
        god_dir = Path(directory) / "god"
        subprocess.run(
            [sys.executable, str(PROJECT / "main.py"), "--demo", "--seed", "7",
             "--max-rounds", "1", "--output-dir", str(normal_dir)],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            [sys.executable, str(PROJECT / "main.py"), "--demo", "--seed", "7",
             "--max-rounds", "1", "--god-view", "--output-dir", str(god_dir)],
            capture_output=True, text=True, check=True,
        )

        public_html = (normal_dir / "spectator.html").read_text(encoding="utf-8")
        god_html = (god_dir / "god_view.html").read_text(encoding="utf-8")
        self.assertNotIn("wolf_negotiation_message", public_html)
        self.assertIn("wolf_negotiation_message", god_html)
        self.assertIn("wolf", god_html)
```

- [ ] **Step 2: 运行隔离测试确认失败。**

```bash
.venv311/bin/python -m unittest \
  hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_god_view_is_separate_from_public_spectator -v
```

Expected: 当前没有 `god_view.html`，测试失败。

- [ ] **Step 3: 完成隔离测试和页面交互。**

让上帝视角的时间线事件卡使用稳定 `data-event-id`，点击后更新选中事件样式；更新 README/FLOW/PRODUCT_READINESS/领域 README，记录 `--god-view`、两个页面的权限边界和本地静态服务命令。不要把普通观众页改成上帝视角。

- [ ] **Step 4: 运行专项测试和全量测试。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -q
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py'
git diff --check
```

Expected: 第 16 课专项全部通过；全量测试通过，真实模型 smoke test 按环境跳过；无 diff 格式错误。

- [ ] **Step 5: 生成并浏览器检查上帝视角页面。**

```bash
.venv311/bin/python hello-agents/projects/16-graduation-project/main.py \
  --demo --seed 7 --max-rounds 3 --god-view \
  --output-dir hello-agents/projects/16-graduation-project/runs/manual-seed-7
python3 -m http.server 8766 \
  --directory hello-agents/projects/16-graduation-project/runs/manual-seed-7
```

在浏览器打开 `http://127.0.0.1:8766/god_view.html`，检查顶部状态、完整私有事件、身份面板、JSON 诊断和事件点击；再打开 `spectator.html`，确认普通页面仍无私密字段。

- [ ] **Step 6: Commit docs and final verification.**

```bash
git add hello-agents/projects/16-graduation-project/README.md \
  hello-agents/projects/16-graduation-project/FLOW.md \
  hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md \
  hello-agents/projects/16-graduation-project/werewolf_arena/README.md \
  hello-agents/PROGRESS.md \
  hello-agents/tests/test_werewolf_arena.py
git commit -m "docs: document werewolf god view"
```

---

## Summary for Wave

### 变更文件清单

- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/god_view.py`
- Modify: `hello-agents/projects/16-graduation-project/main.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/storage.py`
- Modify: `hello-agents/tests/test_werewolf_arena.py`
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/FLOW.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/README.md`
- Modify: `hello-agents/PROGRESS.md`

### 实现步骤概览

1. 先用测试固定 `--god-view` 和 ArtifactStore 的显式生成契约。
2. 新增独立的完整状态审计页，展示身份、私有事件和规则诊断，并对动态文本转义。
3. 增加普通观众页/上帝视角页隔离测试，更新文档和运行命令。
4. 跑专项、全量、格式检查，并用 seed 7 在本地浏览器检查页面。

### 潜在风险

- 上帝视角包含敏感身份与私有事件，必须保持显式开关和本地工件边界。
- 静态 HTML 页面不会实时更新；实时裁判视图仍属于后续 Web 化工作。
- 现有工作区有用户未提交修改，执行时只修改计划列出的文件。

### 预计复杂度

中
