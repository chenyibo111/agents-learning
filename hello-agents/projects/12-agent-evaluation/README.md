# 12 - Agent 评测

对应课程：[12-agent-evaluation](../../lessons/12-agent-evaluation.md)，状态：🔁；回顾 `achieve` 第 13、22、32 课。

运行：`python projects/12-agent-evaluation/main.py --demo`；`--llm` 讨论评测设计。Demo 计算成功率、平均步数和安全违规数。

实验：增加成本指标；把安全违规设为发布门禁；将失败轨迹保存为下一版回归样例。

## 三层实现状态

- 概念层：已覆盖成功率、轨迹、成本、延迟、安全和 Judge 边界。
- 最小实践层：当前 Demo 已计算成功率、平均步数和安全违规数。
- 工程实现层：待加入版本化数据集、轨迹回放、报告、人工校准、模型对比和 CI 发布门禁。
