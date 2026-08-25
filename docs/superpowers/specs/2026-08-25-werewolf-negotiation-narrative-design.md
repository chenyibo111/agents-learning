# 狼人协商与剧场叙事观战设计

## 背景与目标

当前项目已经具备可回放的六人狼人杀规则内核，但狼人只能直接提交袭击目标，观战者也只能阅读底层 JSON 事件。本次改造先实现一个可测试、可回放的最小闭环，为后续完整 Web 项目保留清晰边界：

1. 狼人拥有私密协商和明确的最终确认投票。
2. 公共观战者看到的是不泄露身份的叙事时间线，而不是上帝视角事件。
3. 每局自动生成浏览器可打开的 `spectator.html`，并支持终端实时叙事。
4. 规则引擎继续是身份、目标、胜负和可见性的唯一权威。

本次不实现 WebSocket、HTTP API、数据库、登录、房间管理或真实多人连接；这些作为后续 Web 化改造的基础设施工作保留。

## 设计决策

### 狼人阶段

保留 `Phase.NIGHT_WOLF` 作为狼人私密协商阶段，新增 `Phase.NIGHT_WOLF_CONFIRM` 作为狼人最终确认投票阶段。完整顺序为：

```text
NIGHT_WOLF
  ├─ 每名存活狼人提交一次 wolf_speak/noop
  └─ 结算后进入 NIGHT_WOLF_CONFIRM

NIGHT_WOLF_CONFIRM
  ├─ 每名存活狼人提交一次 wolf_vote/noop
  └─ 目标一致才设置 night_victim，随后进入 NIGHT_SEER
```

### 私密协商

- `wolf_speak` 只能由存活狼人提交，使用 `speech` 字段，`target_id` 必须为 `null`。
- 发言在提交时生成 `wolf_negotiation_message` 私有事件，收件人是当晚所有存活狼人。
- 后行动的狼人可以在自己的 Observation 中看到此前的狼人私密发言。
- 私密发言不会出现在 `public.events`、公开 JSONL 叙事或 `spectator.html`。
- 女巫、预言家、村民和公共观战者都看不到狼人发言内容。

### 明确确认投票

- `wolf_vote` 只能由存活狼人提交，目标必须是存活、不是自己、不是 `wolf_teammates` 的玩家。
- 投票期间不生成个人公开事件；双方提交完成后生成仅狼人可见的 `wolf_vote_revealed`，包含个人票型、总票数和是否达成共识。
- 达成唯一共识时，再生成仅狼人和女巫可见的 `wolf_target_selected`，让女巫知道当晚袭击目标。
- 分票、弃票或没有完整投票时生成 `wolf_attack_failed`，女巫只知道没有形成袭击目标。
- 规则引擎最终重新校验目标，Policy 的提前校验只负责安全降级，不改变裁判权。

### Policy 与 Prompt

- `RulePolicy` 在 `NIGHT_WOLF` 固定发出一条简短私密建议，在 `NIGHT_WOLF_CONFIRM` 选择第一个合法候选目标。
- `LLMPolicy` 的阶段行动集合分别为 `wolf_speak/noop` 和 `wolf_vote/noop`。
- 常见别名 `confirm_kill`、`wolf_confirm`、`wolf_target_vote` 归一化为 `wolf_vote`。
- Prompt 明确：狼人私聊只对狼人可见；确认投票期间看不到队友的票；目标一致才形成袭击。

### 公开叙事层

新增纯函数式叙事模块，将公开 `Event` 转换为中文短句。它必须先检查 `event.public`，私有事件直接跳过；未知事件也只能使用安全的通用文案，不能读取角色或私有字段。

公开叙事覆盖：

- 夜晚公告和死亡名单；
- 公开发言；
- 投票完成后的个人票型和总票数；
- 出局、平票和胜负；
- 轮次/阶段提示。

### 浏览器观战页

新增自包含 `spectator.html` 工件，使用公开事件和当前存活状态生成“剧场叙事型”页面：

- 顶部显示对局标题、轮次、当前阶段和运行结果；
- 中央按时间顺序显示叙事卡片，发言是主要内容；
- 侧边显示存活/出局玩家和当前发言顺序；
- 投票完成后显示公开票型和总票数；
- 不显示真实身份、狼人私密发言、狼人个人确认票、预言家查验或女巫药物；
- 所有文本经过 HTML escaping，公开发言只能作为文本渲染，不能注入脚本。

`ArtifactStore.write()` 每局写入该页面并在 `artifacts` 返回路径。页面是回放工件，不依赖后端服务；未来 Web 项目可以直接把同一套公开叙事数据接入 WebSocket 或 API。

### 终端观战

CLI 增加 `--spectate` 开关。开启后，`GameEngine` 在每次阶段结算后将本次新增的公开叙事事件输出到 stdout；不输出私有事件、模型 Prompt、原始响应、身份或 API Key。`--json` 仍保持机器可读的最终报告，不因观战输出改变状态。

## 数据流与权限边界

```text
Action(wolf_speak)
  -> rules.submit_action
  -> private wolf_negotiation_message
  -> wolf Observation

Action(wolf_vote)
  -> rules.submit_action
  -> private wolf_vote_revealed
  -> consensus / no attack
  -> private result for wolves + witch

public Events
  -> narrative.py
  -> spectator.html / --spectate
```

完整 `GameState`、`checkpoint.json` 和 `events.jsonl` 仍是受保护审计资料；观战页只使用公开投影，不能通过前端参数切换到上帝视角。

## 错误处理与恢复

- 模型输出无效时，现有一次修复请求和 `noop` 降级机制继续生效。
- `wolf_speak` 或 `wolf_vote` 的非法目标、错误身份、重复行动由规则层拒绝；Policy 能从 Observation 判断的错误提前降级。
- 中断可发生在两个狼人阶段之间；checkpoint 必须保存新的 `Phase` 和 pending actions，恢复后不重复已经生成的私密发言或确认票。
- 观战页面生成失败不能改变游戏状态；`ArtifactStore` 先完成核心 checkpoint/事件/报告，再单独写页面并返回工件路径或非敏感错误。

## 测试验收

必须新增或更新测试：

1. 两名狼人各发言一次，私密事件只对狼人可见。
2. 非狼人 Observation 和公共事件中不包含狼人协商文本。
3. 狼人确认票在双方提交前不可见，完成后只对狼人公开。
4. 同目标形成袭击，分票/弃票不形成袭击，女巫只能看到最终袭击结果。
5. 新阶段的 Policy、RulePolicy、Prompt、别名和非法目标校验正常。
6. 新阶段 checkpoint 中断恢复与连续运行事件完全一致。
7. 叙事函数只输出公开事件，正确处理发言、死亡、票型、平票和胜负。
8. `spectator.html` 包含公开叙事和玩家状态，不包含身份、私密事件内容或未转义 HTML。
9. CLI `--spectate` 输出叙事，`--json`、报告和旧离线运行仍兼容。

## 后续 Web 化扩展点

- 将 `public_narrative_events` 作为 WebSocket/SSE 消息格式。
- 将狼人私密事件绑定到经过认证的玩家会话，而不是静态文件。
- 将 `spectator.html` 拆成前端组件，保留同一套公开字段和权限审计。
- 增加房间、并发、数据库、回放权限和人类玩家输入。
