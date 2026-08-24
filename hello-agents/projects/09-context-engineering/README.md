# 09 - 上下文工程

对应课程：[09-context-engineering](../../lessons/09-context-engineering.md)，状态：🔁；回顾 `achieve` 第 16、22 课。

运行：`python projects/09-context-engineering/main.py --demo`；`--llm` 讨论上下文策略。Demo 按优先级和成本在固定预算中选择信息。

实验：添加摘要项；模拟敏感字段脱敏；比较“只保留最近消息”和“优先保留安全约束”的结果。

## 三层实现状态

- 概念层：已覆盖上下文选择、排序、压缩、预算和注入边界。
- 最小实践层：当前 Demo 已按优先级和成本选择上下文。
- 工程实现层：待接入真实 token 计数、摘要存储、脱敏、注入检测、成本监控和长会话回归测试。
