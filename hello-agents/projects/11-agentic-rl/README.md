# 11 - Agentic-RL

对应课程：[11-agentic-rl](../../lessons/11-agentic-rl.md)，状态：🆕。

运行：`python projects/11-agentic-rl/main.py --demo`；`--llm` 获取概念解释。Demo 只生成小型轨迹并计算奖励，不进行大模型训练，避免把教学概念误认为生产训练框架。

实验：比较正确率奖励和步骤惩罚；构造 reward hacking；记录同一任务的多条轨迹并做相对比较。

## 三层实现状态

- 概念层：已覆盖 SFT、轨迹、奖励和 reward hacking。
- 最小实践层：当前 Demo 已生成小型轨迹并计算奖励。
- 工程实现层：待建立可复现实验集、轨迹存储、奖励版本、训练/评测分离和安全门禁。
