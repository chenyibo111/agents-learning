# 16 - Werewolf Arena：六 Agent 狼人杀毕业项目

对应课程：[16-graduation-project](../../lessons/16-graduation-project.md)。本项目将第 15 课的社会模拟升级为一个可回放、可评测的六人局狼人杀环境：2 名狼人、1 名预言家、1 名女巫、2 名村民。

项目的关键边界是：模型或规则 Policy 只能读取自己的 `PlayerObservation` 并提出 `Action`；`GameEngine` 和 `rules.py` 才是身份、夜晚结算、投票和胜负的唯一权威。

面向稍成熟可玩产品的已实现能力、缺口与优先级见：[PRODUCT_READINESS.md](PRODUCT_READINESS.md)。

系统内各模块如何协作、状态如何流转、运行记录如何保存，见：[FLOW.md](FLOW.md)。

## 运行

在仓库根目录执行：

```powershell
.\.venv\Scripts\python.exe hello-agents\projects\16-graduation-project\main.py --demo --json --seed 7 --max-rounds 3
.\.venv\Scripts\python.exe hello-agents\projects\16-graduation-project\main.py --demo --json --output-dir .tmp\werewolf
.\.venv\Scripts\python.exe hello-agents\projects\16-graduation-project\main.py --resume .tmp\werewolf\checkpoint.json --max-rounds 3 --json
```

默认是六个离线规则 Agent，不联网。`--output-dir` 生成：

- `checkpoint.json`：完整、版本化的引擎状态；
- `events.jsonl`：按事件存放的审计轨迹；
- `report.json`：胜负、规则合规、隐私、模型成本和决策观测指标报告；
- `llm_requests.jsonl`：仅在 LLM 模式生成的脱敏请求级追踪，不包含完整 Prompt、原始响应或 API Key。

未传 `--output-dir` 时，以上工件会自动生成在项目目录的 `runs/<时间戳>-seed-<seed>-<随机标识>/` 下；`runs/` 已被 Git 忽略，避免对局记录混入源码提交。

## 游戏规则

每个夜晚依次发生：

1. 两名狼人各自选择非狼人目标；目标一致才形成袭击。
2. 预言家查验一名存活玩家，结果仅自己可见。
3. 女巫看到袭击目标，可一次性使用解药或毒药，也可不行动。
4. 环境结算死亡，但默认不公开死亡身份。

白天所有存活玩家各发言一次、再公开投票；最高票者出局，平票无人出局。所有狼人死亡则好人胜利；存活狼人不少于好人时狼人胜利；达到 `--max-rounds` 仍未结束时判为平局。

## 模块结构

- `schemas.py`：角色、阶段、玩家、行动、事件、观察和可持久化 GameState。
- `visibility.py`：从上帝视角状态生成最小授权的 PlayerObservation，并将公共发言标记为不可信数据。
- `rules.py`：行动校验、夜晚结算、投票、死亡与胜负规则。
- `policies.py`：确定性 RulePolicy、离线 ScriptedModelAdapter、LLMPolicy 与 OpenAI Chat Completions 兼容适配器。
- `engine.py`：阶段调度、最大轮次限制、中断恢复。
- `storage.py`：原子 checkpoint、JSONL 轨迹与评测报告。
- `evaluation.py`：规则拒绝、发言、投票、隐私泄露和模型成本指标。

## 真实模型模式

设置以下环境变量后使用 `--policy llm`：

```powershell
$env:WEREWOLF_LLM_ENDPOINT = "https://your-provider.example/v1/chat/completions"
$env:WEREWOLF_LLM_API_KEY = "your-secret"
$env:WEREWOLF_LLM_MODEL = "your-model"
$env:WEREWOLF_LLM_TIMEOUT_SECONDS = "30"
$env:WEREWOLF_LLM_MAX_RETRIES = "1"
$env:WEREWOLF_LLM_RETRY_BACKOFF_SECONDS = "0.5"
$env:WEREWOLF_LLM_MAX_OUTPUT_TOKENS = "2048"
$env:WEREWOLF_LLM_THINKING = "disabled" # auto / enabled / disabled
$env:WEREWOLF_LLM_INPUT_PRICE_PER_MILLION = "0"
$env:WEREWOLF_LLM_OUTPUT_PRICE_PER_MILLION = "0"
.\.venv\Scripts\python.exe hello-agents\projects\16-graduation-project\main.py --demo --policy llm --max-rounds 3 --json
```

六名玩家会使用独立的 Policy 上下文，但共享同一个可配置模型适配器。模型必须返回 JSON：`action_type`、`target_id`、`speech`、`decision_label`。Prompt 会按阶段声明允许的行动，Policy 会将常见别名（如 `kill`、`speech`）归一化，并在规则层之前执行核心字段、长度、阶段和投票目标 Schema 校验；`decision_label` 只是可选辅助元数据，缺失、`null` 或非字符串会归一化为空字符串。投票必须指向存活且不是自己的玩家；弃票或 `noop` 不得携带目标。格式或核心 Schema 失败时最多追加一次短修复请求，仍失败才使用安全 `noop`；其他合法但目标错误的行动仍由规则引擎拒绝；密钥不会写进 checkpoint、事件或报告。

LLM 适配器默认关闭 thinking，并将结构化行动输出上限设为 2048；`WEREWOLF_LLM_THINKING=auto` 会省略供应商专属字段，`enabled` 可恢复思考模式。适配器对超时、网络错误、HTTP 408/425/429 和 5xx 做有限重试；401/其他 4xx 不重试。重试耗尽后返回安全的 `noop`，并在 `decision_label`、`model_failures` 和 stderr 进度日志中保留非敏感失败原因，整局不会因为单个模型请求超时而崩溃。`max_tokens` 限制模型输出上限，价格环境变量按百万 Token 计算 `cost_usd`。`--progress` 只输出请求阶段、尝试次数、错误码和耗时，不输出 Prompt、响应或 API Key。

LLM 模式还会为每个 Agent 的每次逻辑请求追加一条脱敏记录，包含 `agent_id`、`phase`、`request_status`、`decision_status`、耗时、Token、解析后的行动类型、降级原因和 hash。完整请求/响应不会落盘。

## 已覆盖的验收场景

- 固定 seed 的 2 狼人、1 预言家、1 女巫、2 村民分配；
- 村民、狼人、预言家和女巫之间的私有信息隔离；
- 狼人协同行动、女巫救人、非法行动和平票；
- LLM 非 JSON、未知字段或非法阶段行动降级为可结算的 `noop`；
- LLM 常见行动别名归一化、阶段协议和本地 Schema 校验；
- 连续运行与 checkpoint 恢复结果一致；
- 胜负、规则合规、隐私与成本指标输出。

## 限制与下一步

当前版本是单进程、回合制核心，没有 Web UI；狼人没有独立私聊协商阶段，默认规则 Policy 仅用于稳定回归，并不代表高水平游戏策略。不同玩家的白天观察依赖前序公开事件，因此当前阶段调度保持串行；后续可在保持同一阶段语义的前提下增加狼人协商、并行独立请求、Prompt 版本实验、Elo/胜率评测和可视化回放。

测试：

```powershell
.\.venv\Scripts\python.exe -m unittest hello-agents\tests\test_werewolf_arena.py -v
```
