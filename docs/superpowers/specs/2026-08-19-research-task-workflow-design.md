# 第 29 课：研究任务工作流设计

## 目标

在第 28 课的本地知识库基础上，构建一个可以追踪中间状态的研究任务工作流。工作流依次完成规划、检索、证据提取和证据核验，并同时支持离线 Demo 与真实 LLM 两种运行模式。

## 范围

- 新增 `projects/29-research-task-workflow/` 课程项目。
- 复用第 28 课提供的 Markdown 导入器和关键词/向量检索器。
- 新增统一的研究运行时协议：Demo 运行时返回确定性结果，LLM 运行时通过注入的 OpenAI-compatible 客户端完成规划、提取和核验。
- 使用 LangGraph 编排四个节点：`plan`、`retrieve`、`extract`、`verify`。
- 输出结构化的已核验证据；最终 Markdown 报告留到第 30 课。
- 不修改第 27、28 课的生产代码，不提交 API Key 或 `.env`。

## 状态与数据流

```text
topic
  → plan
  → retrieved_chunks
  → evidence
  → verified_evidence
```

状态至少包含：

- `topic: str`
- `plan: list[str]`
- `retrieved_chunks: list[SearchResult]`
- `evidence: list[EvidenceRecord]`
- `verified_evidence: list[EvidenceRecord]`
- `status: str`
- `events: list[str]`

每个节点只读取必要的输入并返回局部更新；LangGraph 负责把节点返回值合并回状态。

## 运行时边界

`ResearchRuntime` 只负责模型侧的规划、证据提取和核验，不负责自行搜索资料。检索器作为独立依赖注入 `retrieve` 节点，确保模型不能绕过知识库凭空生成来源。

- `DemoRuntime`：不访问网络、不读取凭据，返回固定计划和基于检索结果的确定性证据。
- `LLMRuntime`：通过客户端注入调用模型，要求结构化 JSON，并校验记录字段和类型。

## CLI

```bash
python projects/29-research-task-workflow/main.py --demo --retriever keyword
python projects/29-research-task-workflow/main.py --llm --retriever both
```

CLI 默认使用第 28 课的知识库；向量模式继续受第 28 课的 `chromadb`、`sentence-transformers` 和本地索引约束。

## 错误处理

- 缺少 LangGraph 或向量检索依赖时，返回带安装提示的 `RuntimeError`。
- LLM 返回非法 JSON、错误字段或错误类型时立即抛出 `ValueError`，不把不可信结果写入后续状态。
- 空知识库和未知检索模式在入口处拒绝执行。

## 验收标准

- Demo 模式可在无 API Key、无向量依赖时完成四节点流程。
- 真实 LLM 模式可使用 FakeClient 完成无网络单元测试，并与 Demo 共用工作流节点。
- 节点测试能够验证状态和事件按顺序流转。
- LangGraph 可用时，图执行结果包含 `completed` 状态和已核验证据。
- 全量测试通过，且不泄露任何敏感配置。
