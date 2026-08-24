# 10 - Agent 通信协议

对应课程：[10-agent-protocols](../../lessons/10-agent-protocols.md)，状态：🔁；回顾 `achieve` 第 23 课。

运行：`python projects/10-agent-protocols/main.py --demo`；`--llm` 解释 MCP、A2A、ANP 的边界。Demo 输出带版本和 task id 的最小任务 envelope。

实验：加入能力版本协商；模拟超时和重复提交；拒绝未授权 capability。

## 三层实现状态

- 概念层：已区分 MCP、A2A、ANP 的通信边界。
- 最小实践层：当前 Demo 已输出带版本和 task id 的本地 envelope。
- 工程实现层：待接入真实协议适配，加入认证、权限、超时、取消、幂等、重放保护和契约测试。
