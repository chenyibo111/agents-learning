# 09 - 上下文工程

对应课程：[09-context-engineering](../../lessons/09-context-engineering.md)，状态：🔁；回顾 `achieve` 第 16、22 课。

运行离线工程 Demo：

```bash
python projects/09-context-engineering/main.py --demo
python projects/09-context-engineering/main.py --demo --budget 20
```

`--llm` 会将编译后的上下文交给真实 LLM，并记录输入/输出 Token 和估算成本：

```bash
python projects/09-context-engineering/main.py \
  --llm \
  --budget 64 \
  --cost-budget-usd 0.05
```

如果本地没有缓存 `tiktoken` 编码表，程序会自动降级为 `heuristic`，不会为了计算 Token 强制联网。

实验：添加摘要项；模拟敏感字段脱敏；比较“只保留最近消息”和“优先保留安全约束”的结果。

## 三层实现状态

- 概念层：已覆盖上下文选择、排序、压缩、预算和注入边界。
- 最小实践层：当前 Demo 已按优先级和成本选择上下文。
- 工程实现层：已完成真实/降级 Token 计数、上下文编译、摘要 SQLite 存储、敏感字段脱敏、提示注入检测、成本监控和长会话回归测试。

## 工程实现组成

`context_engine/` 包按职责拆分：

- `contracts.py`：上下文项、选中项、淘汰项和构建结果；
- `tokenizer.py`：`tiktoken` 真实计数与离线 heuristic 降级；
- `builder.py`：必选项门禁、优先级选择、预算截断和上下文渲染；
- `filters.py`：API Key、Authorization、Cookie 等敏感字段脱敏，以及提示注入信号检测；
- `summary.py`：带来源 ID 的 SQLite 会话摘要；
- `monitor.py`：模型价格、输入/输出 Token、成本和预算门禁。

工程层不会静默丢弃安全策略、当前任务或未完成事项；必选项无法放入预算时直接失败，并返回诊断信息。
