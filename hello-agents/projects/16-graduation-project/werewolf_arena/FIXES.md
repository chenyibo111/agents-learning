# 修复记录

## F-001｜LLM 超时有限重试与安全降级

- 日期：2026-08-25
- 关联问题：`I-001`
- 处理：对超时、网络错误、408/425/429 和 5xx 做有限重试；耗尽后返回不含敏感信息的失败指标，Policy 降级为安全行动。
- 验证：`python3 -m unittest hello-agents/tests/test_werewolf_arena.py -v`；适配器重试和失败测试通过。

## F-002｜非敏感 LLM 进度日志

- 日期：2026-08-25
- 关联问题：`I-001`
- 处理：`--progress` 只输出请求阶段、尝试次数、失败原因和耗时，不输出 API Key、Prompt 或完整响应。
- 验证：隐私审计测试通过，日志中未出现密钥和模型原文。

## F-003｜阶段化行动协议 Prompt

- 日期：2026-08-25
- 关联问题：`I-002`
- 处理：Prompt 明确当前阶段允许的 `action_type`、字段类型、发言长度和 `noop` 语义。
- 验证：`test_model_prompt_declares_phase_specific_action_protocol` 通过。

## F-004｜模型行动别名归一化

- 日期：2026-08-25
- 关联问题：`I-002`
- 处理：在 Policy 边界将 `kill`、`speech`、`night_seer`、`no_action` 等常见别名转换为规则枚举。
- 验证：`test_llm_policy_normalizes_common_action_aliases` 通过。

## F-005｜本地严格行动 Schema 校验

- 日期：2026-08-25
- 关联问题：`I-002`
- 处理：校验对象、必填字段、未知字段、字段类型、发言长度和阶段允许行动；失败时降级且不信任模型 actor_id。
- 验证：`test_llm_policy_rejects_unknown_fields_and_phase_actions` 通过。

## F-006｜跨阶段安全 `noop` 降级

- 日期：2026-08-25
- 关联问题：`I-003`
- 处理：规则引擎接受显式 `noop`，各阶段结算器只跳过对应行动，不凭空生成查验、发言或投票事实。
- 验证：`test_noop_is_a_safe_no_action_in_every_phase` 和超时继续运行测试通过。

## F-007｜真实模式与 Token 成本指标

- 日期：2026-08-25
- 关联问题：`I-004`
- 处理：评测报告接收 `offline` 参数；适配器读取输入/输出每百万 Token 价格并计算 `cost_usd`。
- 验证：`test_evaluation_reports_real_llm_mode`、`test_model_adapter_calculates_cost_and_limits_output_tokens` 通过。

## F-008｜输出上限与低延迟请求参数

- 日期：2026-08-25
- 关联问题：`I-001`
- 处理：增加 `WEREWOLF_LLM_MAX_OUTPUT_TOKENS`，请求使用 `max_tokens`，结构化行动温度降为 0.2；保留可配置超时、重试和退避。
- 验证：适配器 payload、环境配置、重试和延迟指标测试通过。

## F-009｜补齐阶段枚举导入

- 日期：2026-08-25
- 关联问题：`I-005`
- 处理：为 Prompt 构造模块补充 `Phase` 导入。
- 验证：第 16 课专属 29 项测试通过。

## F-010｜LLM 请求级脱敏观测

- 日期：2026-08-25
- 关联问题：`I-006`
- 处理：为每次模型请求生成 UUID，记录 Agent、轮次、阶段、尝试次数、重试次数、状态、Token、耗时、解析行动类型、降级原因及 Prompt/响应 hash；新增 `llm_requests.jsonl`，不保存完整 Prompt、原始响应或密钥。
- 处理：新增 `request_count`、`noop_count`、`abstain_count`、`effective_action_count`、`fallback_count`、`schema_failure_count` 和 `invalid_json_count` 等指标。
- 验证：第 16 课专属 29 项测试通过；请求追踪脱敏和 JSONL 持久化测试通过。

## F-011｜无语义变化的 Prompt 压缩

- 日期：2026-08-25
- 关联问题：`I-008`
- 处理：在权限过滤之后压缩事件，仅保留轮次、阶段、类型和完整 payload；将不可信公开 transcript 从嵌套 JSON 字符串改为数组；移除固定的无信息私有记忆文案，保留真实私有记忆。
- 边界：不做历史摘要，不改变私有信息边界、Action Schema、规则结算或模型输出协议。
- 验证：新增事件事实保留、审计字段移除、数组 transcript 和真实私有记忆保留测试；专项测试通过。

## F-012｜结构化行动输出与投票协议收紧

- 日期：2026-08-25
- 关联问题：`I-007` 及本轮运行中的 `invalid_target`
- 处理：新增 `WEREWOLF_LLM_THINKING=auto|enabled|disabled`，默认关闭 thinking；默认 `WEREWOLF_LLM_MAX_OUTPUT_TOKENS` 调整为 2048；投票必须指向当前存活且非自己的玩家，`abstain/noop` 必须使用空目标，否则在 Policy 层安全降级。
- 兼容性：`auto` 不发送供应商专属 thinking 字段，便于不支持该字段的 OpenAI 兼容网关。
- 验证：新增 thinking payload、环境默认值、投票目标和 Prompt 协议测试通过；真实网关截断率仍需 smoke test。

## F-013｜结构化输出一次修复重试

- 日期：2026-08-25
- 关联问题：`I-007`
- 处理：当首次响应出现 `invalid_json` 或 `schema_validation` 时，追加一次短格式修复请求；修复成功则合并两次请求的 Token、费用、耗时和调用次数；修复失败或传输失败则安全降级为 `noop`，不进入无限重试。
- 观测：请求记录增加 `repair_attempted`、`repair_reason` 和 `repair_succeeded`，但不保存原始 Prompt 或响应。
- 验证：新增 JSON 修复成功、Schema 修复成功和修复失败降级测试；第 16 课专项测试通过。

## F-014｜非敏感 Schema 失败分类

- 日期：2026-08-25
- 关联问题：`I-006`
- 处理：将本地行动协议失败映射为稳定分类码，例如 `unknown_field`、`phase_action_type`、`vote_target_not_alive`；首次响应与格式修复响应分别记录 `schema_error_code` 和 `repair_schema_error_code`。
- 隐私边界：只记录分类码，不记录异常原文、完整 Prompt、模型响应或 API Key；无法归类时使用 `schema_validation_error`。
- 验证：第 16 课 42 项测试通过，包含未知字段、非法阶段行动和非法投票目标分类测试。

## F-015｜宽松处理 decision_label

- 日期：2026-08-25
- 关联问题：`I-009`
- 处理：`decision_label` 缺失、`null`、数字、布尔值或其他非字符串统一归一化为空字符串；合法字符串仍保留并限制最多 80 字。
- 边界：不放宽 `action_type`、`target_id`、`speech`、阶段协议和投票目标校验；不改变游戏规则。
- 验证：新增回归测试覆盖缺失、`null`、数字和布尔值；第 16 课专项测试 43 项通过。

## F-016｜补充女巫、隐藏投票与轮换发言规则

- 日期：2026-08-25
- 关联问题：`I-010`
- 处理：没有 `night_victim` 时拒绝 `witch_save`；投票提交阶段只保存 pending action，全部完成后生成包含个人票型和总票数的公开 `vote_revealed` 事件；白天发言按固定座位和轮次轮换首发并跳过死亡玩家；Observation 与 LLM Prompt 暴露发言顺序及投票隐藏语义。
- 验证：新增女巫边界、投票隐私、投票后公开、轮换发言、Prompt 契约和投票指标测试；第 16 课专项测试 48 项通过。

## F-017｜LLM 目标语义提前校验

- 日期：2026-08-25
- 关联问题：`I-011`
- 处理：`LLMPolicy` 在进入规则引擎前校验狼人击杀、预言家查验、女巫毒药和解药目标的存活性、自指限制、狼人队友限制及真实袭击目标一致性；错误输出安全降级为 `noop`。`rules.py` 保留最终校验。
- 验证：Seed 18 的 `wolf_kill` 已有回归复现；新增 4 项目标语义测试通过，第 16 课专项测试 52 项通过，全量测试 254 项通过（4 项跳过）。

## F-018｜狼人协商、确认投票与公开观战叙事

- 日期：2026-08-25
- 关联问题：玩法规则补充与 P0 观战实现。
- 处理：增加 `NIGHT_WOLF_CONFIRM`；狼人先提交私密 `wolf_speak`，再独立提交隐藏 `wolf_vote`，同票才形成袭击；新增公开叙事层、终端 `--spectate` 和自包含 `spectator.html`。
- 隐私边界：观战页和终端只处理公开事件，不展示身份、狼人私聊/确认票、查验结果或女巫药物；投票结果仍在全员提交后公开个人票型和总票数。
- 验证：专项测试覆盖狼人两阶段、私有事件、静态页面转义、CLI 输出和 artifact 生成。

## F-019｜观战 CLI 输出隔离与时间线元数据修复

- 日期：2026-08-25
- 关联问题：`I-012`。
- 处理：`--spectate` 非 JSON 模式不再打印完整 payload；`--json --spectate` 保持 stdout 为合法 JSON。观战时间线直接绑定源公开事件，避免过滤私有事件后轮次/阶段错位。
- 验证：观战隐私、JSON stdout 和源事件轮次/阶段回归测试通过。
