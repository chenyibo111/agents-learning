# 第 9 课上下文工程实现设计

## 目标

在 `hello-agents/projects/09-context-engineering` 中，把固定优先级 Demo 扩展为可测试的上下文编译层：在进入 LLM 前完成信息分层、真实 Token 计数、预算选择、敏感字段过滤、提示注入检测、摘要持久化和成本监控，同时保留旧的 `select_context()` 与离线 `--demo`。

## 核心边界

- `ContextItem` 表示一条待进入上下文的信息，包含类型、优先级、来源和是否必选。
- `TokenCounter` 优先使用 `tiktoken` 真实计数；依赖缺失时使用明确标记的确定性估算，不让 Demo 失效。
- `ContextBuilder` 先处理必选项，再按优先级、相关性和新鲜度选择可选项；必选约束无法放入预算时直接报错，不静默丢弃。
- `SensitiveDataFilter` 只负责脱敏，不把原始敏感值写入结果。
- `PromptInjectionDetector` 把外部文本视为数据，返回警告并包裹为不可信内容，不允许其覆盖系统策略。
- `SQLiteSummaryStore` 持久化会话摘要和来源 ID，支持跨进程恢复。
- `CostMonitor` 记录输入/输出 Token、估算成本和剩余预算。

## 数据流

```text
原始 ContextItem
  ↓
敏感字段过滤 + 注入检测
  ↓
TokenCounter 计算每项成本
  ↓
必选项预算门禁
  ↓
可选项按优先级/相关性/新鲜度排序
  ↓
预算截断与 dropped 原因记录
  ↓
ContextBuildResult
  ↓
LLM Prompt + CostMonitor
```

## 选择规则

1. 必选项按照输入顺序保留，任何必选项超预算都抛出 `ContextBudgetError`。
2. 可选项按 `priority` 降序、`relevance` 降序、`recency` 降序排序。
3. 每项使用目标模型 Token 计数；放不下的可选项进入 `dropped_items`。
4. 选中项保留 `source`、`kind` 和脱敏/注入警告元数据。

## 非目标

- 本课不实现 LLM 自动摘要模型；只持久化外部生成或规则生成的摘要，保留未来注入 Summarizer 的接口。
- 本课不强制绑定某个模型的价格；价格通过 `ModelPricing` 注入。
- 本课不把外部内容当作系统指令，也不尝试用正则证明内容绝对安全。

## 验收标准

1. 旧 `select_context()` 和 `--demo` 仍然可运行。
2. ContextBuilder 能按真实 Token 数选择内容，并保留必选安全约束、任务目标和未完成事项。
3. 必选项超预算时失败并给出诊断；可选项超预算时记录淘汰原因。
4. API Key、Cookie、Authorization 等字段会脱敏，原值不出现在构建结果、日志或报告中。
5. 外部文本中的提示注入会产生警告并被标记为不可信数据。
6. 摘要能通过 SQLite 跨实例恢复，来源 ID 保留。
7. 成本监控能计算输入/输出成本并拒绝超预算调用。
8. 长会话回归测试证明核心任务约束、来源和未完成事项不会因压缩/截断丢失。
