# Werewolf Arena 整体功能流转

本文说明一次六 Agent 狼人杀对局从命令行启动、信息隔离、规则结算到记录落盘的完整路径。阅读源码时建议按本文给出的顺序打开文件。

## 一局游戏的总链路

```text
main.py
  │  解析参数、选择输出目录与 Policy
  v
GameEngine.run()
  │  创建/恢复 GameState
  │
  ├─ 当前阶段需要行动的玩家
  │      │
  │      v
  ├─ observation_for(GameState, player_id)
  │      │  裁剪为 PlayerObservation
  │      v
  ├─ RulePolicy / LLMPolicy.decide(observation)
  │      │  只返回 Action，不修改状态
  │      v
  ├─ submit_action(GameState, Action)
  │      │  校验身份、阶段、目标、资源与重复行动
  │      v
  ├─ advance_phase(GameState)
  │      │  环境结算死亡、发言、票数与胜负
  │      v
  └─ Event + 新 GameState
          │
          ├─ on_public_event：只将公开事件转换为终端观战叙事
          ├─ CheckpointStore：每阶段保存 checkpoint.json
          ├─ LLMPolicy + RequestTraceStore：LLM 模式增量写 llm_requests.jsonl
          └─ evaluate_game + ArtifactStore：写 report.json、events.jsonl、spectator.html；Web 房间额外写 god_view.html
```

## Web 时间线审计流

```text
浏览器 web.html
  │ POST /api/rooms
  ▼
RoomStore：创建唯一内存 Room + initial_game(seed)
  │ POST /api/rooms/{id}/start
  ▼
后台 worker
  └─ GameEngine.step()
       └─ observation_for → RulePolicy / 六个 LLMPolicy → submit_action → advance_phase
  ▼
Room 快照：完整 GameState + 事件游标 + 脱敏请求游标
  ▲
  └─ GET /api/rooms/{id}/audit?after=N&request_after=M（每 500ms 双游标增量轮询）
```

Web 垂直切片只绑定 `127.0.0.1`，按启动参数选择离线 `RulePolicy` 或真实 `LLMPolicy`，页面是开发/裁判审计台，不接受浏览器提交的 `Action`，也不在进程重启后承诺恢复。模型请求期间 GameState 锁不被网络调用长期占用，审计 API 可以继续读取最近一次已提交快照。`/public` API 使用显式字段白名单和 `event.public` 过滤，保留普通观战页的权限边界。

真实 LLM 房间会为六名玩家创建独立 Policy，共享一个模型适配器；每次逻辑决策通过 `RequestTraceCollector` 生成脱敏摘要，使用独立 `request_cursor` 增量返回并同步写入房间目录的 `llm_requests.jsonl`。页面只渲染 Agent、阶段、请求/决策状态、耗时、Token、费用、截断和降级原因，不渲染 Prompt、原始响应、endpoint 或密钥。

## 玩家 Web 垂直切片

```text
player.html
  │ POST /api/rooms
  │ POST /api/rooms/{id}/sessions {player_id}
  ▼
Room：绑定一个临时本地玩家令牌 + HumanPolicy
  │ POST /api/rooms/{id}/start
  ▼
后台 worker
  ├─ 其他座位：RulePolicy / LLMPolicy 自动决策
  └─ 玩家座位：HumanPolicy 等待浏览器 Action
       ▲                    │
       └─ POST /actions ◄───┘
  │ GET /api/rooms/{id}/player?after=N
  ▼
只返回该玩家的角色、资源、授权私有事件、公开事件和当前允许 Action
```

玩家 Action 进入同一个 `rules._validate_action()` 和 `submit_action()` 路径，不允许客户端直接改变 GameState。当前令牌只用于本地开发试玩，任何人都可以在本地选择座位；生产环境仍需补充登录、房间授权和角色会话绑定。

最重要的边界是：`Policy` 只能读取 `PlayerObservation`，只有 `rules.py` 能改变 `GameState`。因此模型不能自报身份、伪造查验结果或直接宣布胜利。

## 文件职责与阅读顺序

| 顺序 | 文件 | 解决的问题 |
|---:|---|---|
| 1 | `schemas.py` | 定义身份、阶段、玩家、行动、事件、观察和完整状态。 |
| 2 | `visibility.py` | 把上帝视角状态裁剪为每名玩家的最小授权视图。 |
| 3 | `policies.py` | 将 Observation 转成 Action；可选规则、脚本或真实 LLM。 |
| 4 | `rules.py` | 校验 Action 并结算夜晚、白天、死亡、投票和胜负。 |
| 5 | `engine.py` | 按阶段调度六个玩家、保存 checkpoint、支持恢复。 |
| 6 | `storage.py` | 原子写入完整状态、JSONL 轨迹和报告。 |
| 7 | `evaluation.py` | 汇总胜负、事件数、违规数、隐私与成本指标。 |
| 8 | `main.py` | 将命令行参数和以上模块组装为可运行程序。 |
| 9 | `web.py` / `web.html` | 本地单房间 worker、裁判/公开 API 和时间线审计台。 |
| 10 | `test_werewolf_arena.py` / `test_werewolf_web.py` | 用具体场景验证规则、恢复、Web API 和页面契约不会回归。 |

## 新建对局与恢复对局

### 新建对局

```powershell
.\.venv\Scripts\python.exe hello-agents\projects\16-graduation-project\main.py --demo --seed 7 --max-rounds 3
```

1. `main.py` 根据 `seed` 创建 `GameEngine`。
2. `GameEngine` 调用 `initial_game(seed)`，把 2 狼人、预言家、女巫、2 村民分配给固定玩家 ID。
3. 未传 `--output-dir` 时，`ArtifactStore.default_run_directory()` 创建：

```text
projects/16-graduation-project/runs/
  20260825-123045-123456-seed-7-a1b2c3d4/
    checkpoint.json
    events.jsonl
    report.json
    llm_requests.jsonl  # 仅 LLM 模式，脱敏请求级追踪
```

4. `checkpoint.json` 会在每个阶段之后更新；LLM 模式的请求摘要在决策完成后增量写入 `llm_requests.jsonl`；最终 `ArtifactStore` 再写入报告和事件工件。

### 恢复对局

```powershell
.\.venv\Scripts\python.exe hello-agents\projects\16-graduation-project\main.py --resume <run-dir>\checkpoint.json --max-rounds 3
```

1. `CheckpointStore.load()` 将 JSON 恢复为 `GameState`。
2. 引擎将 `INTERRUPTED` 改回 `RUNNING`，保留已经完成的事件与待结算状态。
3. 默认继续写回原 checkpoint 所在的对局目录，不创建新的分叉目录。

## 阶段状态机

```text
NIGHT_WOLF
  ├─ 两只狼人分别提交私密 wolf_speak，所有狼人可见
       ↓
NIGHT_WOLF_CONFIRM
  ├─ 两只狼人独立提交隐藏 wolf_vote
  ├─ 目标一致：记录私有 night_victim
  └─ 分票或弃票：记录私有 wolf_attack_failed，不形成袭击
       ↓
NIGHT_SEER
  ├─ 预言家提交 inspect
  └─ 环境写入仅预言家可见的 inspection_result
       ↓
NIGHT_WITCH
  ├─ 女巫看到 night_victim、解药和毒药余量
  ├─ 有 night_victim：提交 witch_save / witch_poison / noop
  ├─ 无 night_victim：只能提交 witch_poison / noop
  └─ 环境结算死亡，公开 night_announcement（不公开身份）
       ↓
DAY_DISCUSSION
  ├─ 按固定座位轮换首发，死亡玩家跳过
  ├─ 每名存活玩家提交一条 speak
  └─ 发言立即成为公开 speech Event
       ↓
DAY_VOTE
  ├─ 每名存活玩家独立提交 vote 或 abstain
  ├─ 提交期间不公开个人票型
  ├─ 全员提交后一次性公开 ballots 和 counts
  ├─ 唯一最高票：execution
  └─ 最高票并列：vote_tied
       ↓
CHECK_WINNER
  ├─ 狼人全灭：good 胜
  ├─ 存活狼人 >= 存活好人：wolves 胜
  └─ 否则 round_number + 1，回到 NIGHT_WOLF
```

当 `round_number > max_rounds` 时，`engine.py` 调用 `finish_draw()` 终止为平局，防止失控的 LLM 对局无限调用。

## 信息如何隔离

```text
完整 GameState（仅引擎）
  ├─ 所有人真实身份
  ├─ 所有私有事件
  ├─ 女巫药物
  ├─ 预言家查验
  └─ 狼人目标
          │
          v  observation_for()
PlayerObservation（仅单个 Agent）
  ├─ 公共：存活名单、公开事件、阶段
  └─ 私有：自己的身份、自己的事件、自己的资源
```

附加授权：狼人看到队友；预言家看到自己的查验；女巫在女巫阶段看到当晚袭击目标。其他身份不能看到这些信息。

`events.jsonl` 和 `checkpoint.json` 为完整审计资料，包含私有事件；它们只能给开发者/服务器使用，不能直接提供给普通玩家或旁观者。

`spectator.html` 和 `--spectate` 只消费 `event.public == true` 的事件，并按原始事件的轮次和阶段渲染时间线；它们不序列化完整 `GameState`。

`god_view.html` 在 CLI 显式传入 `--god-view` 或 Web 房间运行阶段后生成，消费完整 `GameState`，展示身份、私有事件、recipients、payload 和规则诊断；它只适用于本地开发/裁判回放。

## Rule Policy 与 LLM Policy 的差别

```text
RulePolicy
  Observation -> 固定规则 -> Action

LLMPolicy
  Observation -> system/user prompt -> ModelAdapter -> JSON -> Action
```

两者最后都会进入同一个 `submit_action()`。LLMPolicy 会先将格式和可由玩家视图判断的目标语义错误降级为 `noop`；规则层仍会复核身份、阶段、资源和目标，任何未被 Policy 捕获的非法行动只能得到 `action_rejected`，无法绕过游戏规则。

真实模型模式通过环境变量配置：

```text
WEREWOLF_LLM_ENDPOINT
WEREWOLF_LLM_API_KEY
WEREWOLF_LLM_MODEL
WEREWOLF_LLM_TIMEOUT_SECONDS
WEREWOLF_LLM_MAX_RETRIES
WEREWOLF_LLM_RETRY_BACKOFF_SECONDS
WEREWOLF_LLM_THINKING
WEREWOLF_LLM_MAX_OUTPUT_TOKENS
WEREWOLF_LLM_MAX_OUTPUT_TOKENS_LIMIT
WEREWOLF_LLM_MAX_OUTPUT_RETRIES
WEREWOLF_LLM_INPUT_PRICE_PER_MILLION
WEREWOLF_LLM_OUTPUT_PRICE_PER_MILLION
```

默认 `--policy rule` 完全离线；只有显式传入 `--policy llm` 才可能产生网络调用和费用。

Web 真实模型启动示例：

```bash
cd hello-agents/projects/16-graduation-project
python -m werewolf_arena.web --policy llm --port 8767 --seed 7 --max-rounds 4 --step-interval 0.5
```

每个阶段推进后，Web 房间的 `runs/<timestamp>-seed-<seed>-<id>/` 会更新 `checkpoint.json`、`events.jsonl`、`report.json`、`spectator.html`、`god_view.html`；LLM 模式再追加 `llm_requests.jsonl`。`Room.snapshot()` 的 `artifacts.run_dir` 指向该目录，便于裁判回放定位同一局。

## 工件与评测流

```text
GameState + Events
  ├─ checkpoint.json：恢复整局
  ├─ events.jsonl：逐事件回放和调试
  └─ evaluate_game()
  ├─ report.json
  ├─ spectator.html：公开事件剧场回放
  └─ god_view.html：CLI 显式开关或 Web 房间自动生成的完整审计回放
        └─ llm_requests.jsonl（LLM 模式）
             ├─ winner / rounds
             ├─ speech_count / vote_count
             ├─ rejected_action_count
             ├─ model_calls / tokens / cost / latency
             ├─ rule_compliance
             └─ privacy_audit
```

`privacy_audit` 会扫描公开事件中是否出现私有记忆、狼人队友、查验结果、女巫药物或身份字段。它是防御性检查；真正的安全边界仍是 `visibility.py` 的最小授权投影。

## 建议的阅读与调试路线

1. 先运行一次离线 Demo，查看 `runs/` 下的 `report.json` 与 `events.jsonl`。
2. 打开 `schemas.py`，理解 `GameState / Action / Event / PlayerObservation` 的区别。
3. 阅读 `visibility.py`，确认不同身份实际能看到什么。
4. 阅读 `rules.py` 的 `submit_action()` 和 `advance_phase()`，理解规则如何强制执行。
5. 最后阅读 `policies.py`，再把 `RulePolicy` 替换或对比为 `LLMPolicy`。
6. 修改规则后先添加或调整 `test_werewolf_arena.py` 中的行为测试，再运行 Demo。
