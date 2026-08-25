# 狼人协商与剧场叙事观战实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有六人狼人杀引擎中加入狼人私密协商、明确确认投票、公开剧场叙事和可浏览器回放的 `spectator.html`，同时保留后续 WebSocket/API 改造空间。

**Architecture:** 将 `Phase.NIGHT_WOLF` 定义为狼人私密发言阶段，新增 `Phase.NIGHT_WOLF_CONFIRM` 作为狼人确认投票阶段；所有私密协商事件继续由 `recipients` 控制。新增纯函数叙事层只消费公开事件，`ArtifactStore` 生成自包含静态观战页面，`GameEngine` 通过可选回调输出终端实时叙事。

**Tech Stack:** Python 3.11 标准库、dataclasses、`unittest`、HTML escaping、JSON/JSONL；不引入前端框架、WebSocket 或外部依赖。

**执行顺序：** Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6。Task 3 的章节因后续补充暂列在文档末尾。

**Spec:** `docs/superpowers/specs/2026-08-25-werewolf-negotiation-narrative-design.md`

---

### Task 1: 新增狼人阶段与领域规则

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/schemas.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/rules.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [x] **Step 1: 写失败测试，锁定新阶段和私密发言。**

```python
def test_wolves_negotiate_in_private_before_confirming_target(self):
    state = initial_game(seed=7)
    wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
    state = submit_action(state, Action(wolves[0], "wolf_speak", speech="先观察票型。"))
    self.assertNotIn("wolf_negotiation_message", [event.event_type for event in state.events if event.public])
    wolf_view = observation_for(state, wolves[1])
    self.assertIn("先观察票型。", json.dumps(wolf_view.private["private_events"], ensure_ascii=False))
    villager_view = observation_for(state, player_id(state, Role.VILLAGER))
    self.assertNotIn("先观察票型。", json.dumps(villager_view.to_dict(), ensure_ascii=False))
    state = submit_action(state, Action(wolves[1], "wolf_speak", speech="确认后投同一个目标。"))
    state = advance_phase(state)
    self.assertEqual(Phase.NIGHT_WOLF_CONFIRM, state.phase)
```

- [x] **Step 2: 运行单测确认当前实现失败。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_wolves_negotiate_in_private_before_confirming_target -v
```

Expected: 当前实现因缺少 `wolf_speak` 或新阶段而失败。

- [x] **Step 3: 修改 schema 和规则。**

在 `Phase` 增加 `NIGHT_WOLF_CONFIRM = "night_wolf_confirm"`，保留 `NIGHT_WOLF` 作为私密发言阶段。规则新增 `wolf_speak` 的存活狼人、空目标和发言长度校验；提交时生成仅发给所有存活狼人的 `wolf_negotiation_message` 私有事件。`advance_phase` 在协商完成后清空 pending actions 并进入确认阶段。

- [x] **Step 4: 写并运行确认投票的失败测试。**

覆盖同票、分票、弃票和投票隐藏：

```python
def test_wolf_confirm_votes_are_hidden_and_consensus_forms_attack(self):
    state = self._advance_wolves_to_confirm_phase(seed=7)
    wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
    target = next(player.player_id for player in state.players if player.role != Role.WOLF)
    state = submit_action(state, Action(wolves[0], "wolf_vote", target))
    self.assertNotIn("wolf_vote_revealed", [event.event_type for event in state.events])
    state = submit_action(state, Action(wolves[1], "wolf_vote", target))
    state = advance_phase(state)
    reveal = next(event for event in state.events if event.event_type == "wolf_vote_revealed")
    self.assertFalse(reveal.public)
    self.assertEqual(target, state.night_victim)

def test_wolf_confirm_split_votes_create_no_attack(self):
    state = self._advance_wolves_to_confirm_phase(seed=7)
    wolves = [player.player_id for player in state.players if player.role == Role.WOLF]
    targets = [player.player_id for player in state.players if player.role != Role.WOLF]
    state = submit_action(state, Action(wolves[0], "wolf_vote", targets[0]))
    state = submit_action(state, Action(wolves[1], "wolf_vote", targets[1]))
    state = advance_phase(state)
    self.assertIsNone(state.night_victim)
    self.assertEqual("wolf_attack_failed", state.events[-1].event_type)
```

Run the two tests and confirm they fail before implementation.

- [x] **Step 5: Implement minimum consensus settlement.**

`_resolve_wolf_confirm_phase` collects `wolf_vote`/`noop` from all alive wolves, emits `wolf_vote_revealed` privately to wolves with ballots, counts and consensus, then emits the target-result event privately to wolves plus witch. A unique same target sets `night_victim`; split or incomplete votes sets it to `None`; the next phase is `NIGHT_SEER`.

- [x] **Step 6: Run the focused rule tests.**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_wolves_negotiate_in_private_before_confirming_target hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_wolf_confirm_votes_are_hidden_and_consensus_forms_attack hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_wolf_confirm_split_votes_create_no_attack -v
```

Expected: all new tests pass.

### Task 2: 调度、Policy、可见性与 Prompt

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/policies.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/visibility.py`
- Modify: `hello-agents/tests/test_werewolf_arena.py`

- [x] **Step 1: 写失败测试，确认 engine 会调度两段狼人行动。**

```python
def test_rule_policy_runs_wolf_talk_then_confirm_vote(self):
    state = GameEngine(seed=7).run(max_rounds=1)
    wolf_messages = [event for event in state.events if event.event_type == "wolf_negotiation_message"]
    wolf_votes = [event for event in state.events if event.event_type == "wolf_vote_revealed"]
    self.assertGreaterEqual(len(wolf_messages), 2)
    self.assertGreaterEqual(len(wolf_votes), 1)
```

Also assert that `model_prompts()` declares `wolf_speak` in `NIGHT_WOLF` and `wolf_vote` in `NIGHT_WOLF_CONFIRM`.

- [x] **Step 2: 运行测试确认当前实现失败。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_rule_policy_runs_wolf_talk_then_confirm_vote -v
```

- [x] **Step 3: 实现阶段调度和 Policy。**

更新 `_actors_for_phase()` 使两个狼人阶段都调度存活狼人；`RulePolicy.decide()` 在协商阶段返回 `wolf_speak`，在确认阶段返回第一个合法 `wolf_vote`。增加 `confirm_kill`、`wolf_confirm`、`wolf_target_vote` 别名，并为两个阶段增加目标语义校验。Prompt 明确私聊权限、确认票隐藏和同票成袭击规则。

- [x] **Step 4: 验证 LLM Policy 协议与隐私。**

增加 Scripted adapter 测试覆盖有效 `wolf_speak`、有效 `wolf_vote`、死亡/队友/自指目标和别名；断言村民、女巫及公共视图看不到狼人私聊和个人确认票。运行：

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
```

### Task 4: 公开叙事转换与静态观战页面

**Files:**
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/narrative.py`
- Create: `hello-agents/projects/16-graduation-project/werewolf_arena/spectator.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/storage.py`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [x] **Step 1: 写失败测试，确认公开事件能转成剧场文案。**

```python
def test_public_narrative_ignores_private_events_and_renders_speech_and_votes(self):
    public_speech = Event("e1", 1, Phase.DAY_DISCUSSION, "speech", {"speaker": "alice", "text": "我怀疑 bob。"})
    private_message = Event(
        "e2", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message", {"text": "攻击 bob"},
        public=False, recipients=("alice", "bob"),
    )
    rendered = render_public_events((public_speech, private_message))
    self.assertIn("alice", " ".join(rendered))
    self.assertNotIn("攻击 bob", " ".join(rendered))

def test_spectator_html_escapes_public_speech_and_omits_private_data(self):
    state = replace(initial_game(seed=7), events=(
        Event("e1", 1, Phase.DAY_DISCUSSION, "speech", {"speaker": "alice", "text": "<script>alert(1)</script>"}),
        Event("e2", 1, Phase.NIGHT_WOLF, "wolf_negotiation_message", {"text": "secret"}, public=False, recipients=("alice",)),
    ))
    html = render_spectator_html(state)
    self.assertIn("&lt;script&gt;", html)
    self.assertNotIn("secret", html)
    self.assertNotIn('role="wolf"', html)
```

- [x] **Step 2: 运行测试确认模块尚未实现。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_public_narrative_ignores_private_events_and_renders_speech_and_votes hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_spectator_html_escapes_public_speech_and_omits_private_data -v
```

- [x] **Step 3: 实现纯函数叙事转换。**

`narrative.py` 提供 `narrate_event(event: Event) -> str | None` 和 `render_public_events(events) -> list[str]`。先检查 `event.public`，私有事件直接跳过；已知公开事件生成稳定中文短句；未知公开事件使用安全通用文案，不读取身份或私有字段。

- [x] **Step 4: 实现剧场型静态页面。**

`spectator.py` 提供 `render_spectator_html(state: GameState) -> str`，生成自包含 HTML：顶部状态、中央公开时间线、存活/出局玩家、发言顺序和投票结果。只消费公开事件和玩家 ID/存活状态；所有文本使用 HTML escaping，不能嵌入角色、私有事件或脚本。

- [x] **Step 5: 将页面加入 ArtifactStore。**

在 checkpoint、事件和报告成功写入后，`ArtifactStore.write()` 原子写入 `spectator.html` 并把绝对路径加入 `artifacts`；增加工件存在性测试。

- [x] **Step 6: 运行叙事和存储测试。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
```

### Task 5: 终端实时观战与文档

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- Modify: `hello-agents/projects/16-graduation-project/main.py`
- Modify: `hello-agents/projects/16-graduation-project/README.md`
- Modify: `hello-agents/projects/16-graduation-project/FLOW.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/README.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/ISSUES.md`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/FIXES.md`
- Modify: `hello-agents/projects/16-graduation-project/PRODUCT_READINESS.md`
- Modify: `hello-agents/PROGRESS.md`
- Test: `hello-agents/tests/test_werewolf_arena.py`

- [x] **Step 1: 写失败测试，锁定 `--spectate` 输出。**

```python
def test_spectate_mode_prints_only_public_narrative(self):
    result = subprocess.run(
        [sys.executable, str(PROJECT / "main.py"), "--demo", "--seed", "7", "--max-rounds", "1", "--spectate"],
        capture_output=True, text=True, check=True,
    )
    self.assertIn("天亮", result.stdout)
    self.assertNotIn("wolf_negotiation_message", result.stdout)
    self.assertNotIn("Role.WOLF", result.stdout)
```

- [x] **Step 2: 运行测试确认 CLI 尚未支持该开关。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_spectate_mode_prints_only_public_narrative -v
```

- [x] **Step 3: 增加 GameEngine 公共事件回调和 CLI 开关。**

给 `GameEngine.run()` 增加可选 `on_public_event: Callable[[str], None]`；每个阶段结算后只处理新增的公开事件，调用 `render_public_events` 并逐行发送。`main.py` 增加 `--spectate`，用 `flush=True` 输出叙事；不输出私有事件、Prompt、模型响应、身份或 API Key。

- [x] **Step 4: 更新用户文档和实现记录。**

记录狼人两阶段、私密频道、`spectator.html`、`--spectate` 和本地静态服务命令；明确 WebSocket/API、认证、房间和数据库仍是后续工作。

- [x] **Step 5: 运行专项、全量和格式检查。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
.venv311/bin/python -m unittest discover -s hello-agents/tests -p 'test_*.py'
git diff --check
```

实际结果：第 16 课专项 64 项通过；全量 266 项通过、4 项真实 smoke test 跳过；`git diff --check` 通过。

### Task 6: 最终浏览器验证与交付

**Files:**
- Review: Tasks 1-5 的所有变更文件

- [x] **Step 1: 检查差异和隐私边界。**

```bash
git diff --stat
git diff --check
rg -n "role|wolf_negotiation|wolf_vote_revealed|spectator" hello-agents/projects/16-graduation-project/werewolf_arena hello-agents/tests/test_werewolf_arena.py
```

确认观战页没有嵌入完整 `GameState`，并且只从公开事件生成时间线。

- [x] **Step 2: 打开生成的 spectator 页面。**

使用 seed 7 离线运行，输出到 `hello-agents/projects/16-graduation-project/runs/` 下的独立目录；通过本地静态服务器在浏览器打开 `spectator.html`，检查时间线、发言转义、存活状态、投票公开和私密信息隔离。

- [x] **Step 3: 记录真实测试结果和剩余 Web 工作。**

用实际测试数量更新实现记录；保留 WebSocket/API、身份认证、多房间同步、数据库、人类玩家和完整实时 Web 前端为后续工作。

### Task 3: checkpoint 恢复与事件兼容

**Files:**
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/rules.py`
- Modify: `hello-agents/projects/16-graduation-project/werewolf_arena/engine.py`
- Modify: `hello-agents/tests/test_werewolf_arena.py`

- [x] **Step 1: 写失败测试覆盖确认阶段中断恢复。**

```python
def test_checkpoint_resume_from_wolf_confirmation_matches_continuous_game(self):
    continuous = GameEngine(seed=7).run(max_rounds=2)
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "checkpoint.json"
        interrupted = GameEngine(seed=7).run(
            max_rounds=2,
            interrupt_after_phase=Phase.NIGHT_WOLF_CONFIRM,
            checkpoint_path=checkpoint,
        )
        self.assertEqual("INTERRUPTED", interrupted.status)
        resumed = GameEngine.resume(checkpoint, max_rounds=2)
    self.assertEqual(continuous.to_dict(), resumed.to_dict())
```

- [x] **Step 2: 运行并确认恢复测试失败。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena.WerewolfArenaTests.test_checkpoint_resume_from_wolf_confirmation_matches_continuous_game -v
```

- [x] **Step 3: 更新中断选项、阶段转换和持久化断言。**

确保新 `Phase` 自动出现在 CLI 的 `--interrupt-after-phase` 选项中；`GameState.from_dict()` 可恢复新阶段；在两个狼人阶段之间恢复时不重复私密发言或确认票。

- [x] **Step 4: 运行 checkpoint 和全量专项测试。**

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_arena -v
```
