# Hello-Agents 课程笔记

每个章节 README 使用以下结构：

```text
学习状态
achieve 对应课程
已经掌握的内容
本章新增内容
完整讲解
项目结构
运行方式
实验任务
三层实现
测试与验收
```

已学内容会做回顾，不会因为标记为已学而删除 Hello-Agents 原章节的完整内容。

## 第 5 章起的统一实现标准

从第 5 章开始，每一课都必须按三层推进，课程笔记和项目 README 都要明确当前完成到哪一层：

1. **概念层**：讲清原理、系统边界、架构选择、适用场景和常见风险；
2. **最小实践层**：使用标准库或固定数据实现离线 Demo，能重复运行、观察状态和验证主流程；
3. **工程实现层**：补充真实接口或框架、结构化状态、错误恢复、权限/成本/观测、持久化和专属测试。需要外部服务时必须保留离线替代方案。

只有完成三层并通过验收，才算完成该课。已有的简单 Demo 只代表最小实践层，不代表工程实现层已经完成。

## 章节索引

1. [初识智能体](01-agent-basics.md)
2. [智能体发展史](02-agent-history.md)
3. [大语言模型基础](03-llm-foundation.md)
4. [经典 Agent 范式](04-agent-patterns.md)
5. [低代码平台](05-low-code-platforms.md)
6. [Agent 框架实践](06-agent-frameworks.md)
7. [从零构建 Agent 框架](07-build-agent-framework.md)
8. [Memory 与 RAG](08-memory-and-rag.md)
9. [上下文工程](09-context-engineering.md)
10. [Agent 通信协议](10-agent-protocols.md)
11. [Agentic-RL](11-agentic-rl.md)
12. [Agent 性能评估](12-agent-evaluation.md)
13. [智能旅行助手](13-travel-assistant.md)
14. [DeepResearch Agent](14-deep-research.md)
15. [赛博小镇 Agent](15-cyber-town.md)
16. [毕业设计](16-graduation-project.md)

## 推荐阅读顺序

先读本章的“与 achieve 的边界”，确认哪些知识只需回顾；再读完整讲解，最后运行项目的 `--demo`。离线 Demo 用固定数据验证流程，真实 LLM 只替换模型适配层，不改变核心状态流转。每次实验都应记录输入、状态变化、输出和失败时的行为。
