# 狼人杀 Web 时间线审计垂直切片设计

日期：2026-08-25

## 1. 目标

在现有单局狼人杀规则引擎之上增加一条最小可运行的 Web 闭环，用于开发验证和裁判回放：浏览器创建一个指定 seed 的单房间，服务端自动使用 `RulePolicy` 按阶段推进游戏，页面轮询并展示完整的上帝视角事件时间线、当前 `GameState` 摘要和运行指标。

这条切片优先验证三个边界：

1. Web 层复用现有 `GameEngine` / `rules.py`，不复制狼人协商、女巫、投票或胜负逻辑。
2. 完整状态只保存在服务端；上帝视角页面通过明确的开发/裁判 API 获取，不把状态修改权交给浏览器。
3. 事件以稳定游标增量读取，能够观察阶段推进、规则拒绝、私有事件和最终胜负。

## 2. 范围与非目标

### 本次范围

- 本地单进程服务。
- 内存单房间；同一服务实例最多保留一个活动房间。
- 创建房间、启动自动回放、获取裁判视角状态和增量事件。
- 时间线审计台：阶段、轮次、状态、存活人数、胜负、指标、事件列表和事件详情。
- 默认绑定 `127.0.0.1`，显式标注为开发/裁判工具。
- `RulePolicy` 自动执行，使用 seed 保证可重复。
- 标准库实现，不增加 Web 框架依赖。

### 本次不做

- 真实 LLM 调用、人类玩家 Action 提交、登录鉴权和权限系统。
- 多房间、多人协作、数据库、生产部署和跨进程恢复。
- WebSocket/SSE；第一版采用短轮询。
- 修改 GameState 的控制台操作、手动注入 Action、暂停/恢复控制。
- 面向普通玩家的公开观战页面；公开视图 API 只保留边界和测试，正式 UI 后续实现。

## 3. 方案与架构

采用 Python 标准库 HTTP + 内存单房间方案。它与当前课程项目的 Python 结构一致，避免在第一条切片中引入依赖和部署变量，同时保留后续替换为 FastAPI/SSE 的接口边界。

### 模块职责

- `werewolf_arena/engine.py`：增加一个公开的单阶段推进入口，Web worker 调用它而不是复制 `_advance_one_phase` 的调度逻辑。
- `werewolf_arena/web.py`：包含 `RoomStore`、单房间生命周期、HTTP 路由、JSON 序列化和本地服务入口。
- `werewolf_arena/web.html`：自包含的审计台页面，负责创建/启动演示局、轮询 API、渲染时间线和显示选中事件详情。
- `tests/test_werewolf_web.py`：覆盖房间、worker、API、权限边界、增量游标和最终状态。

`RoomStore` 持有一个 `Room`。`Room` 内部使用 `RLock` 保护 `GameState`，后台 daemon 线程每次推进一个完整阶段，然后等待短暂间隔。房间完成或服务关闭时 worker 退出；进程内不承诺重启恢复。

### 数据流

```text
浏览器
  │ POST /api/rooms
  ▼
RoomStore ──创建──> GameState(NIGHT_WOLF)
  │
  │ POST /api/rooms/{id}/start
  ▼
后台 worker ── GameEngine.step(state)
  │                 │
  │                 └── RulePolicy -> submit_action -> advance_phase
  ▼
Room 快照（状态 + events）
  ▲
  │ GET /api/rooms/{id}/audit?after=N
  │
浏览器每 500ms 拉取增量事件并刷新 UI
```

## 4. API 契约

### `POST /api/rooms`

请求体可选：`{"seed": 7}`。

成功返回 201：

```json
{
  "game_id": "werewolf-7",
  "seed": 7,
  "phase": "night_wolf",
  "status": "RUNNING"
}
```

已有活动房间返回 409；seed 缺失时使用 7；非整数 seed 返回 400。

### `POST /api/rooms/{game_id}/start`

启动自动 `RulePolicy` worker。重复调用是幂等的，返回当前房间摘要。未知房间返回 404。

### `GET /api/rooms/{game_id}/audit?after=N`

返回完整裁判数据：

```json
{
  "game_id": "werewolf-7",
  "state": {"...": "完整 GameState.to_dict()"},
  "events": ["after 游标之后的 Event.to_dict()"],
  "cursor": 12,
  "running": true
}
```

`after` 默认为 0，必须是非负整数。`cursor` 等于当前事件总数，客户端保存它作为下一次请求的游标。

### `GET /api/rooms/{game_id}/public?after=N`

返回同样的增量形状，但只包含 `public == true` 的事件、玩家存活状态和公开摘要；不返回角色、`pending_actions`、私有 recipients 或私有 payload。该端点为后续普通观众页保留，第一版页面不使用它。

### `GET /`

返回审计台 HTML。页面默认只连本地 API，并在标题和说明中明确“开发 / 裁判回放专用”。

## 5. 页面设计

- 顶部：房间 ID、seed、运行状态和“创建演示局 / 开始自动回放”按钮。
- 第一行指标：当前阶段、轮次、存活人数、胜者、事件数、请求/延迟/截断指标。
- 主区域三列：左侧事件时间线，中间选中事件详情，右侧完整状态摘要。
- 时间线按服务端事件顺序展示，事件标签区分公开事实、私有行动、规则拒绝和结算结果。
- 初始自动选中最新事件；点击历史事件只改变前端选中项，不改变服务端状态。
- 轮询失败显示可见错误并保留最后一次成功快照；房间完成后停止频繁刷新但允许继续查看历史。

## 6. 错误处理与安全边界

- HTTP 层统一返回 JSON 错误对象：`{"error": "稳定错误码", "message": "可读说明"}`。
- JSON 格式错误、字段类型错误、负游标返回 400；未知房间返回 404；重复创建返回 409。
- 页面只能调用创建、启动和读取接口，不能提交任意 `GameState` 或直接执行规则函数。
- 裁判 API 和页面只绑定回环地址；文档和 UI 明确禁止对外发布。在没有认证的前提下不做公网监听。
- 服务端序列化完整状态仅用于本地开发/裁判用途；公开端点继续通过 `public` 事件和显式字段白名单隔离私密信息。
- worker 异常会将房间标为错误状态并保留最后快照，HTTP 仍可读取错误信息，避免线程异常静默消失。

## 7. 验收与测试

测试先于实现，按以下顺序建立：

1. `GameEngine.step` 能推进一个阶段，且与现有 `run()` 的阶段语义一致。
2. `RoomStore` 能按 seed 创建单房间、拒绝第二个活动房间，并可安全读取快照。
3. HTTP API 能创建房间、启动 worker、返回增量事件和最终 `FINISHED`/`DRAW` 状态。
4. `audit` 返回角色和私有事件；`public` 不包含角色、私有事件或 pending actions。
5. 相同 seed 的两个独立房间产生相同事件序列；不同 seed 至少能产生不同角色分配或事件序列。
6. 页面 HTML 包含审计台结构、轮询逻辑、错误提示和开发/裁判边界文案。

验证命令：

```bash
.venv311/bin/python -m unittest hello-agents.tests.test_werewolf_web -v
.venv311/bin/python -m unittest discover -s hello-agents/tests
git diff --check
```

## 8. 后续演进

完成这条切片后，下一步可以在不改变 `Room` 快照和 API 序列化边界的前提下加入 checkpoint、真实 LLM worker、SSE、公开观战页和人类玩家 Action。认证、多房间和持久化应作为独立变更设计，不在本切片中顺手引入。
