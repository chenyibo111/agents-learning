# Hello-Agents 深入实践课程表

本路线按照 Datawhale Hello-Agents 的章节组织，不删减原项目内容。已经在 `achieve/` 学过的部分会在课程 README 中做回顾标记，并继续学习原项目中的新内容和新实现。

状态说明：

- ✅ 已学过：已有完整基础；
- 🔁 已学基础，继续深入；
- 🆕 未学习；
- ⬆️ 进阶扩展。

当前实际学习进度和每章验证证据以 [PROGRESS.md](PROGRESS.md) 为准；截至 2026-08-24，工程实现已推进到第 15 章，正式讲解已完成第 1～7 章和第 10 章，第 8～9 章及第 11～15 章待正式讲解。

| 章节 | 主题 | achieve 对应内容 | 状态 | 课程笔记 |
|---|---|---|---|---|
| 01 | 初识智能体 | 第 1～3 课 | 🔁 | [课程笔记](lessons/01-agent-basics.md) / [实践](projects/01-agent-basics/README.md) |
| 02 | 智能体发展史 | 无系统对应 | 🆕 | [课程笔记](lessons/02-agent-history.md) / [实践](projects/02-agent-history/README.md) |
| 03 | 大语言模型基础 | 第 1 课部分内容 | 🔁 | [课程笔记](lessons/03-llm-foundation.md) / [实践](projects/03-llm-foundation/README.md) |
| 04 | ReAct、Plan-and-Solve、Reflection | 第 3、17、20 课 | 🔁 | [课程笔记](lessons/04-agent-patterns.md) / [实践](projects/04-agent-patterns/README.md) |
| 05 | Coze、Dify、n8n 低代码平台 | 概念讨论 | 🔁 | [课程笔记](lessons/05-low-code-platforms.md) / [实践](projects/05-low-code-platforms/README.md) |
| 06 | AutoGen、AgentScope、LangGraph | 第 23～26 课 | 🔁 | [课程笔记](lessons/06-agent-frameworks.md) / [实践](projects/06-agent-frameworks/README.md) |
| 07 | 从零构建 Agent 框架 | 第 1～3 课有原理基础 | 🔁 | [课程笔记](lessons/07-build-agent-framework.md) / [实践](projects/07-build-agent-framework/README.md) |
| 08 | Memory 与 RAG | 第 4～16 课 | ✅ | [课程笔记](lessons/08-memory-and-rag.md) / [实践](projects/08-memory-and-rag/README.md) |
| 09 | 上下文工程 | 第 16、22 课 | 🔁 | [课程笔记](lessons/09-context-engineering.md) / [实践](projects/09-context-engineering/README.md) |
| 10 | MCP、A2A、ANP | 第 23 课 | 🔁 | [课程笔记](lessons/10-agent-protocols.md) / [实践](projects/10-agent-protocols/README.md) |
| 11 | Agentic-RL | 无对应课程 | 🆕 | [课程笔记](lessons/11-agentic-rl.md) / [实践](projects/11-agentic-rl/README.md) |
| 12 | Agent 性能评估 | 第 13、22、32 课 | 🔁 | [课程笔记](lessons/12-agent-evaluation.md) / [实践](projects/12-agent-evaluation/README.md) |
| 13 | 智能旅行助手 | 无对应课程 | 🆕 | [课程笔记](lessons/13-travel-assistant.md) / [实践](projects/13-travel-assistant/README.md) |
| 14 | DeepResearch Agent | 第 27～32 课有相近项目 | 🔁 | [课程笔记](lessons/14-deep-research.md) / [实践](projects/14-deep-research/README.md) |
| 15 | 赛博小镇 Agent | 无对应课程 | 🆕 | [课程笔记](lessons/15-cyber-town.md) / [实践](projects/15-cyber-town/README.md) |
| 16 | 毕业设计 | 第 27～32 课 | 🔁 | [课程笔记](lessons/16-graduation-project.md) / [实践](projects/16-graduation-project/README.md) |

> 内容状态：本表中的课程笔记和项目入口已生成；“学习状态”仍表示相对于 `achieve/` 的知识基础，不等于本人已经完成新路线学习。

## 第 5 章起的实现要求

第 5～16 章统一采用“概念层 → 最小实践层 → 工程实现层”。课程材料已经包含三层的目标和验收标准；第 11～15 章的工程层已生成并验证，其余章节会在逐课学习时继续实现。
