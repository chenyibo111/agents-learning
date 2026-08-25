# 狼人杀真实 LLM Web 实时审计设计

日期：2026-08-25

## 1. 目标

在现有本地单房间 Web 审计台上增加真实 LLM 运行模式：服务启动时从 `.env` 加载 OpenAI Chat Completions 兼容配置，为六名玩家创建 `LLMPolicy`，浏览器启动后实时观察游戏事件、LLM 请求摘要、延迟、Token、截断、降级和费用，并在 `runs/` 下保留可复盘工件。

离线 `RulePolicy` 仍是默认模式和测试模式；真实 LLM 只有在显式传入 `--policy llm` 时才启用，避免普通 Web 演示意外产生网络请求和费用。

## 2. 范围与非目标

### 本次范围

- 六名玩家全部使用同一个 `.env` 配置的真实模型适配器和独立 `LLMPolicy`。
- `--policy rule|llm` 两种 Web 启动模式。
- 启动时加载并校验 endpoint、API key、model 和预算参数；配置错误直接阻止服务启动，且不回显密钥。
- 单房间自动 worker；保留现有游戏规则、信息隔离和 `GameEngine` 权威边界。
- 审计 API 返回游戏事件和逻辑请求追踪的两个独立游标。
- 请求摘要增量写入内存和 `llm_requests.jsonl`，不保存 Prompt、原始响应或密钥。
- 每阶段保存 checkpoint/事件/报告；终局额外生成 `god_view.html`，方便裁判回放。
- 页面显示真实 LLM 模式、模型名、请求状态、耗时、Token、费用、截断和降级信息。

### 本次不做

- 不允许浏览器选择任意 endpoint、model 或 API key。
- 不把真实模型配置写入 JSON、HTML、事件 payload 或日志。
- 不改造同步模型适配器为 asyncio，不引入 WebSocket/SSE；继续使用 500ms 短轮询。
- 不增加人类玩家 Action、认证、多房间、数据库或公网部署。
- 不在自动化测试中请求真实模型；真实网关只通过显式人工 smoke test 验证。

## 3. 方案与组件

采用扩展当前 `RoomStore` 的方案，不另起一套 LLM runner。

### Policy 注入

`RoomStore` 增加运行模式和 Policy 工厂：

- `rule`：保持现在的 `GameEngine(seed=seed)`，缺省回退 `RulePolicy`。
- `llm`：服务启动时创建一个 `OpenAICompatibleModelAdapter.from_environment()`；创建房间时为固定六个玩家分别创建 `LLMPolicy(player_id, shared_adapter, on_request=collector.append)`。

共享适配器只由单房间 worker 调用，因此不引入并发模型请求；每个玩家仍有独立 `LLMPolicy`，只接收自己的 `PlayerObservation`。

### 请求追踪收集器

增加房间级线程安全 `RequestTraceCollector`：

- `append(record)`：保存 `LLMPolicy` 已脱敏的单次逻辑请求摘要，并追加到 `RequestTraceStore`；
- `snapshot(after)`：返回指定游标后的记录和当前请求游标；
- 不保存 Prompt、原始响应、Authorization header 或完整异常文本。

每条摘要继续使用现有字段：`agent_id`、`phase`、`attempts`、`request_status`、`decision_status`、`failure_reason`、`fallback_reason`、`input_tokens`、`output_tokens`、`cost_usd`、`latency_ms`、`finish_reason`、`truncated`、`requested_max_tokens` 和 `output_retry_count`。

### 状态与实时性

当前 `Room.step_once()` 持有状态锁执行整个阶段；真实模型请求可能持续数秒，审计轮询不能被它阻塞。因此拆分为：

- `_state_lock`：保护已提交的 `GameState`；
- `_step_lock`：保证同一房间不会并行执行两个阶段；
- `RequestTraceCollector` 自己的锁：模型每次逻辑请求完成后立即可被 API 读取。

worker 在 `_step_lock` 下读取状态，执行 `engine.step()`，再在 `_state_lock` 下提交新状态。模型请求期间 API 可以返回最近一次已提交状态和最新请求追踪；阶段结算完成后状态和事件一起更新。

## 4. 服务启动与 API

### 启动命令

```bash
cd hello-agents/projects/16-graduation-project
python -m werewolf_arena.web \
  --policy llm \
  --port 8767 \
  --seed 7 \
  --max-rounds 4 \
  --step-interval 0.5
```

`OpenAICompatibleModelAdapter.from_environment()` 自动读取仓库根目录和 `hello-agents/.env`，显式导出的环境变量优先。服务默认绑定 `127.0.0.1`。

### `GET /api/rooms`

返回当前房间摘要和非敏感运行配置：`game_id`、`seed`、`policy_mode`、`model`、`pricing_configured`、阶段、状态和运行标志。不得包含 endpoint、API key 或完整环境变量。

### `POST /api/rooms`

请求只允许可选 `seed`，Policy 模式由服务启动参数决定，客户端不能切换到任意模型。真实 LLM 模式下如果服务启动时配置已通过校验，则创建房间返回 201。

### `POST /api/rooms/{game_id}/start`

启动当前房间的自动 worker，重复调用幂等。worker 使用六个真实 `LLMPolicy`，每阶段依次调用模型并进入同一 `submit_action` / `advance_phase` 规则路径。

### `GET /api/rooms/{game_id}/audit?after=N&request_after=M`

返回：

```json
{
  "game_id": "werewolf-7",
  "policy_mode": "llm",
  "model": "configured-model",
  "state": {"...": "完整 GameState.to_dict()"},
  "events": ["after 之后的事件"],
  "cursor": 22,
  "llm_requests": ["request_after 之后的脱敏请求摘要"],
  "request_cursor": 12,
  "running": true,
  "worker_error": null,
  "artifacts": {"run_dir": "...", "checkpoint": "..."}
}
```

两个游标独立递增：页面保存 `cursor` 和 `request_cursor`，下一次分别传回；事件游标不会因为请求追踪数量变化而偏移。

`/public` 继续只返回公开事件和公开状态，不返回角色、pending actions、LLM 请求摘要、费用明细或私有 payload。

## 5. 工件与失败处理

房间创建时生成 `runs/<timestamp>-seed-<seed>-<id>/`，请求追踪立即写入其中。每个阶段完成后更新：

- `checkpoint.json`：完整状态，可供本地裁判恢复；
- `events.jsonl`：完整事件轨迹；
- `llm_requests.jsonl`：脱敏逻辑请求摘要。

房间终局或 worker 出错时额外刷新：

- `report.json`：使用 `evaluate_game(state, offline=False)`；
- `spectator.html`：公开静态观战页；
- `god_view.html`：完整开发/裁判回放页。

现有 `LLMPolicy` 的安全策略保持不变：超时、网络/HTTP 失败、非法 JSON、Schema 失败和输出截断在模型边界处理；必要时安全降级为 `noop`，`GameState` 继续由规则引擎结算。worker 只有在未预期异常时才进入 `ERROR`，并保留最后快照和 `worker_error` 的稳定分类说明。

## 6. 页面设计

保留现有三列时间线审计台，并增加真实模型区：

- 顶部显示 `REAL LLM`、模型名、房间 seed 和工件目录标识；
- KPI 保留阶段、轮次、存活、状态、事件游标，并增加请求游标、总请求、总耗时、Token、费用和降级数；
- 左侧继续显示完整事件时间线；
- 中间事件详情保持 payload、rule、recipients；
- 右侧状态快照下增加“LLM 请求流”，按请求显示 Agent、阶段、成功/降级、耗时、Token、截断和失败分类；
- 页面轮询失败时保留最后快照并显示错误；模型请求进行中时显示“等待模型响应”，不允许前端提交 Action。

页面只展示脱敏请求摘要，不展示 Prompt、原始响应、API key 或 Authorization header。

## 7. 测试与验收

所有自动化测试使用 fake/scripted adapter，不发出网络请求：

1. `RoomStore(policy_mode="rule")` 行为与现有离线 Web 完全一致。
2. `RoomStore(policy_mode="llm", model_adapter=ScriptedModelAdapter(...))` 为六名玩家创建 LLMPolicy，并产生请求追踪。
3. 请求追踪游标可独立增量读取；状态事件游标不受请求数量影响。
4. API 返回 `policy_mode/model` 和请求摘要，但不返回密钥、Prompt、原始响应或私有请求到 `/public`。
5. 模型调用阻塞时，审计 API 仍能在超时范围内返回最近状态和已完成请求摘要。
6. 阶段结束后请求指标进入 `GameState.metrics`，完成后 `runs/` 包含完整工件。
7. 缺少 endpoint/key/model 时 `--policy llm` 启动失败且输出不包含密钥。
8. 页面包含真实 LLM 标识、请求流、双游标轮询和错误保留逻辑。
9. 真实 smoke test 手工执行至少一个 seed，记录请求数、截断率、平均/P95 延迟和成本；自动化测试不依赖该网络结果。

## 8. 后续演进

该切片完成后，下一步可以增加 SSE/WebSocket、真实玩家 Action 和房间授权；这些功能应继续复用 `Room` 的状态锁、Policy 注入和脱敏事件边界，不直接把完整 checkpoint 暴露给普通观众。
