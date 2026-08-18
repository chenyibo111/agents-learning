# Hello Agents 学习课程表

这是本项目的完整学习计划，按照“基础 Agent → RAG → 可靠工作流 → 框架 → 完整项目”的顺序组织。

本课程参考 Datawhale 的 [Hello-Agents](https://github.com/datawhalechina/hello-agents)，但当前目录中的第 6 课之后包含了针对实践学习补充的自建实验，并不是对原教程章节的一一复制。

状态说明：

- ✅ 已完成课程讲解与代码生成，部分项目已运行验证；
- 🟡 已生成代码，等待学习和运行；
- ⬜ 后续规划。

截至 2026-08-17，课程讲解已完成到第 16 课，第 17 课已生成。

## 阶段 0：学习方法与开发环境

| 编号 | 课程 | 核心内容 | 项目/笔记 | 状态 |
|---|---|---|---|---|
| 00 | 学习方法与实践原则 | 如何边学边做、如何记录实验 | [00-learning-method.md](lessons/00-learning-method.md) | ✅ |

## 阶段 1：Agent 基础循环

| 编号 | 课程 | 核心内容 | 项目/笔记 | 状态 |
|---|---|---|---|---|
| 01 | 手写最小 Agent | Python 调用 LLM、messages、最小请求循环 | [01-minimal-agent](projects/01-minimal-agent/) | ✅ |
| 02 | 交互式 Agent | 持续接收用户输入、退出机制 | [02-interactive-agent](projects/02-interactive-agent/) | ✅ |
| 03 | 多步 Agent 与错误处理 | 工具调用循环、最大步数、异常反馈 | [03-multi-step-agent](projects/03-multi-step-agent/) | ✅ |
| 04 | 对话记忆 | 将历史消息放入上下文 | [04-conversation-memory](projects/04-conversation-memory/) | ✅ |
| 05 | 持久化记忆 | JSON 文件保存与恢复状态 | [05-persistent-memory](projects/05-persistent-memory/) | ✅ |

## 阶段 2：RAG 基础与检索质量

| 编号 | 课程 | 核心内容 | 项目/笔记 | 状态 |
|---|---|---|---|---|
| 06 | RAG 检索增强生成 | 知识库、检索、上下文增强 | [06-rag-agent](projects/06-rag-agent/) | ✅ |
| 07 | 文档切分、Top-K 与来源引用 | Chunk、Top-K、来源信息 | [07-rag-chunking](projects/07-rag-chunking/) | ✅ |
| 08 | 向量相似度检索 | 向量、距离、相似度 | [08-vector-retrieval](projects/08-vector-retrieval/) | ✅ |
| 09 | 神经网络 Embedding 语义检索 | SentenceTransformer、语义向量 | [09-embedding-retrieval](projects/09-embedding-retrieval/) | ✅ |
| 10 | 向量数据库与持久化索引 | Chroma、PersistentClient、索引重建 | [10-vector-store](projects/10-vector-store/) | ✅ |
| 11 | 两阶段检索与 Rerank | 候选召回、语义分数、关键词分数 | [11-rag-rerank](projects/11-rag-rerank/) | ✅ |
| 12 | RAG 可信回答、引用与拒答 | 证据编号、相关性阈值、引用检查 | [12-rag-grounded-answer](projects/12-rag-grounded-answer/) | ✅ |
| 13 | RAG 检索评测与指标 | Hit@K、Precision@K、Recall@K、MRR | [13-rag-evaluation](projects/13-rag-evaluation/) | ✅ |
| 14 | 混合检索与 RRF | 向量检索、BM25、排名融合 | [14-hybrid-retrieval](projects/14-hybrid-retrieval/) | ✅ |
| 15 | 查询改写与多路召回 | Query Rewriting、Multi-Query、RRF | [15-query-rewriting](projects/15-query-rewriting/) | ✅ |
| 16 | 上下文压缩、去重与预算 | Chunk 去重、字符预算、证据保留 | [16-context-compression](projects/16-context-compression/) | ✅ |

## 阶段 3：可靠 Agent 与工作流

| 编号 | 课程 | 核心内容 | 项目/笔记 | 状态 |
|---|---|---|---|---|
| 17 | Agent 状态管理与可恢复工作流 | 状态机、检查点、失败恢复 | [17-agent-state](projects/17-agent-state/) | 🟡 |
| 18 | 结构化输出与结果校验 | JSON Schema、字段校验、自动修复 | [18-structured-output](projects/18-structured-output/) | 🟡 |
| 19 | 可靠工具执行 | 参数校验、重试、超时、幂等性 | [19-reliable-tool-execution](projects/19-reliable-tool-execution/) | 🟡 |
| 20 | 工作流编排 | 顺序、条件、并行、人工确认节点 | [20-workflow-orchestration](projects/20-workflow-orchestration/) | 🟡 |
| 21 | Agent 安全与权限控制 | Prompt Injection、权限边界、敏感操作确认 | [21-agent-security](projects/21-agent-security/) | 🟡 |
| 22 | 可观测性与成本控制 | 日志、Tracing、Token、延迟、失败率 | [22-observability-cost-control](projects/22-observability-cost-control/) | 🟡 |

## 阶段 4：协议、框架与多 Agent

| 编号 | 课程 | 核心内容 | 项目/笔记 | 状态 |
|---|---|---|---|---|
| 23 | Agent 通信与工具协议 | 工具协议、资源协议、协议边界 | 待创建 | ⬜ |
| 24 | 用 smolagents 重写 Agent | 轻量级 Agent 框架对比 | 待创建 | ⬜ |
| 25 | 用 LangGraph 管理状态 | 图工作流、节点、边、持久化 | 待创建 | ⬜ |
| 26 | 多 Agent 协作 | 角色分工、任务委派、结果汇总 | 待创建 | ⬜ |

## 阶段 5：完整项目——个人研究助手

| 编号 | 课程 | 核心内容 | 项目/笔记 | 状态 |
|---|---|---|---|---|
| 27 | 研究助手需求与架构 | 需求拆解、模块边界、数据流 | 待创建 | ⬜ |
| 28 | 资料采集与本地知识库 | 文件导入、网页资料、索引更新 | 待创建 | ⬜ |
| 29 | 研究任务工作流 | 规划、检索、提取、核验 | 待创建 | ⬜ |
| 30 | 带引用的 Markdown 报告 | 引用、证据链、报告模板 | 待创建 | ⬜ |
| 31 | 历史任务与人工确认 | 任务持久化、高风险操作确认 | 待创建 | ⬜ |
| 32 | 最终评测与部署 | 回归测试、监控、部署和项目展示 | 待创建 | ⬜ |

## 每课完成标准

每一课至少完成：

1. 阅读课程说明；
2. 运行项目；
3. 修改一个参数或函数；
4. 记录观察结果；
5. 用自己的话解释核心概念。
