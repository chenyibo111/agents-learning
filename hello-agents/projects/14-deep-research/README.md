# 14 - DeepResearch Agent

对应课程：[14-deep-research](../../lessons/14-deep-research.md)，状态：🔁；回顾 `achieve` 第 27～32 课。

运行：`python projects/14-deep-research/main.py --demo`；`--llm` 讨论研究闭环。Demo 用本地来源、证据和结论对象演示引用链，不访问互联网。

实验：加入来源去重；制造冲突证据并标记不确定性；保存中断状态后继续第二轮检索。

## 三层实现状态

- 概念层：已覆盖拆题、来源、证据、矛盾核对和引用。
- 最小实践层：当前 Demo 已用本地来源和 claims 演示引用链。
- 工程实现层：待加入检索器适配、去重、证据 schema、引用审计、多轮预算、检查点和回归测试。
