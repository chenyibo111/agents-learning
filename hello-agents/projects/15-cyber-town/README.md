# 15 - 赛博小镇

对应课程：[15-cyber-town](../../lessons/15-cyber-town.md)，状态：🆕。

运行：`python projects/15-cyber-town/main.py --demo`；`--llm` 获取社会模拟设计建议。Demo 推进一个 tick，明确区分共享世界状态和事件日志。

实验：新增交易规则；固定随机 seed 做回放；比较规则 NPC 与 LLM NPC 的成本和行为差异。

## 三层实现状态

- 概念层：已覆盖角色、环境、共享状态、事件和长期记忆。
- 最小实践层：当前 Demo 已推进一个 tick 并输出事件。
- 工程实现层：待加入事件驱动模拟、seed、状态隔离、持久化回放、Policy 插拔和规模评测。
