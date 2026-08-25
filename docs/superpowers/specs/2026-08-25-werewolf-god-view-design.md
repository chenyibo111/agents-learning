# 狼人杀上帝视角审计页设计

## 1. 目标

为第 16 课狼人杀项目增加独立的开发验证/裁判回放页面 `god_view.html`。

现有 `spectator.html` 保持普通观众视角：只展示公开事件、公开发言、公开票型和存活状态，不暴露身份或私密行动。`god_view.html` 面向项目开发者和裁判，展示一局游戏的完整状态与事件轨迹，帮助验证规则、模型行动和隐私边界。

本设计只增加数据展示能力，不改变游戏规则、Policy、事件生成顺序或胜负结算。

## 2. 使用边界

- 普通运行默认只生成 `spectator.html`。
- 显式传入 `--god-view` 时，额外生成 `god_view.html`。
- 上帝视角页面只作为本地运行目录中的开发/裁判工件，不进入普通观战入口。
- `checkpoint.json`、`events.jsonl` 和 `god_view.html` 都属于完整审计资料，不能作为普通玩家下载内容。
- 页面内动态文本统一 HTML 转义，模型发言和玩家输入不能注入脚本。

## 3. 页面信息架构

页面采用“顶部状态 + 左侧时间线 + 右侧审计面板”的时间线审计台布局。

### 3.1 顶部状态栏

展示：

- 游戏 ID 和 seed；
- 当前轮次、阶段和游戏状态；
- 存活玩家数；
- 当前狼人目标/袭击结果；
- 规则拒绝数与规则合规状态；
- “上帝视角 · 仅开发/裁判”明显标记。

### 3.2 左侧完整事件时间线

按事件发生顺序展示所有事件，包括：

- 狼人私密协商；
- 狼人确认票和确认票结算；
- 预言家查验；
- 女巫看到袭击目标、救药和毒药；
- 白天发言；
- 投票个人票型和总票数；
- 规则拒绝、阶段转换和胜负结算。

每条事件至少展示轮次、阶段、事件类型、关键摘要、`public`、`recipients` 和规则结果。私有事件使用明显的隐私颜色标记，规则拒绝使用警告标记。

时间线支持按轮次、阶段和事件可见性筛选；点击事件后，右侧显示该事件的详细诊断数据。

### 3.3 右侧玩家和身份面板

展示每名玩家的：

- 玩家 ID；
- 角色和阵营；
- 存活/出局状态；
- 女巫解药/毒药余量；
- 狼人队友关系（如适用）。

### 3.4 右侧规则诊断面板

针对选中的事件展示：

- 规则解释；
- `event_type`；
- `payload`；
- `recipients`；
- `public`；
- 原始 JSON；
- 关联的规则拒绝原因或结算结果。

## 4. 数据流与模块边界

```text
GameState
  ├─ ArtifactStore.write(..., god_view=True)
  │    ├─ spectator.py -> spectator.html（公开事件）
  │    └─ god_view.py  -> god_view.html（完整审计数据）
  └─ report/checkpoint/events 保持现有格式
```

新增 `god_view.py`，负责把完整 `GameState` 转换为自包含 HTML。它可以复用阶段标签、事件摘要和安全转义辅助函数，但不复用普通观众页的公开事件过滤逻辑。

`ArtifactStore.write()` 增加显式 `god_view` 开关；`main.py` 增加 `--god-view`，将开关传递给存储层，并在 artifacts 中返回 `god_view` 路径（仅开关启用时）。

页面采用静态 HTML/CSS/少量内联 JavaScript，不引入前端框架、WebSocket、HTTP API、数据库或登录系统。

## 5. 隐私与安全要求

- `spectator.html` 的现有隐私测试必须继续通过。
- `god_view.html` 允许出现角色、私有事件、狼人确认票、查验结果和女巫资源，但仅在显式开关下生成。
- 两种页面都必须对公开发言、私密协商文本和模型输出做 HTML escaping。
- 上帝视角页面不应自动上传或发送任何运行数据。
- 页面标题、文件名和 CLI 输出明确标识其为开发/裁判视图，减少误分享风险。
- 不把完整 `GameState` 作为普通观战页的脚本变量或网络接口返回值。

## 6. 验收与测试

新增测试覆盖：

1. `--god-view` 生成 `god_view.html` 并在 artifacts 中返回路径；
2. 未传 `--god-view` 时不生成该文件；
3. 上帝视角包含角色、私密事件、查验和药物等完整数据；
4. 普通观众页仍不包含这些私密数据；
5. 上帝视角时间线保留源事件轮次、阶段和顺序；
6. 动态文本经过 HTML escaping；
7. 规则引擎和现有游戏结果不因页面生成发生变化；
8. JSON CLI 输出在开启上帝视角后仍保持合法。

手动验收：

```bash
.venv311/bin/python hello-agents/projects/16-graduation-project/main.py \
  --demo --seed 7 --max-rounds 3 --god-view \
  --output-dir hello-agents/projects/16-graduation-project/runs/manual-seed-7
python3 -m http.server 8766 \
  --directory hello-agents/projects/16-graduation-project/runs/manual-seed-7
```

浏览器打开 `http://127.0.0.1:8766/god_view.html`，检查完整时间线、身份面板、事件诊断和私密字段；同时打开 `spectator.html`，确认普通观众视角没有私密泄露。

## 7. 后续不在本次范围

- WebSocket/SSE 实时上帝视角；
- 多房间和服务端权限；
- 登录、裁判账号和审计操作日志；
- 线上数据库和云端运行工件；
- 通过 URL 参数切换普通视角与上帝视角。
