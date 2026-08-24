# 第 8 课 Memory 与 RAG 工程实现设计

## 目标

在 `hello-agents/projects/08-memory-and-rag` 中，把现有固定文档关键词 Demo 扩展为可离线运行、可替换组件的 Memory 与 RAG 示例，同时保留原有 `--demo` 和真实 `--llm` 入口。

## 范围

- 用稳定的数据契约表示文档、记忆和检索命中结果。
- 提供短期会话记忆和 SQLite 长期记忆。
- 提供关键词检索、纯 Python 向量检索和混合检索三种实现。
- 所有长期记忆和文档检索都带 `tenant_id`，禁止跨租户读取或删除。
- 提供检索结果缓存，并在文档或记忆变更时失效。
- 给检索结果生成稳定来源编号，并校验回答引用是否来自本轮证据。
- 提供离线 Hit@K、Precision@K、Recall@K、MRR 评测。
- 检索不到足够证据时输出“证据不足”，不调用 LLM 编造来源。

## 非目标

- 本课不引入外部向量数据库或必须联网下载的 Embedding 模型。
- 不把长期记忆自动写入用户数据；记忆写入由显式 API/CLI 触发。
- 不把模型输出当作来源；来源始终来自代码管理的文档记录。

## 架构

```text
main.py
  ├── ShortTermMemory
  ├── SQLiteMemoryStore
  ├── Retriever (keyword/vector/hybrid)
  ├── RetrievalCache
  ├── CitationValidator
  └── Evaluation
```

`Retriever` 接口接收查询、租户和 `top_k`，返回带文档 ID、来源、片段 ID 和分数的 `RetrievalHit`。关键词和向量实现共享同一套分词结果；向量实现使用标准库构造确定性的词频向量，便于离线教学，接口保留未来接入真实 Embedding 的位置。混合检索使用 RRF 融合两路排名。

`SQLiteMemoryStore` 使用参数化 SQL，主键为随机 UUID；查询和删除必须同时匹配 `tenant_id` 与 `user_id`。短期记忆只保留当前进程的消息，不与长期记忆表混用。

## 数据流

```text
query
  ↓
tenant filter → retriever → cache
  ↓
top-k hits → evidence formatter → citation validator
  ↓
short-term messages + long-term memories + evidence
  ↓
LLM answer
```

## CLI 兼容性

保留：

```bash
python main.py --demo
python main.py --llm
```

新增：

```bash
python main.py --query "长期记忆和 RAG 的区别" --retriever both --top-k 2
python main.py --demo --tenant-id tenant-a
```

所有默认命令不写入真实 API Key、SQLite 文件或外部服务。

## 验收标准

1. 离线 Demo 返回命中结果、来源、分数和缓存状态。
2. 关键词、向量和混合检索实现同一个接口。
3. SQLite 长期记忆能跨 store 实例恢复，并拒绝跨租户读取/删除。
4. 引用校验能识别合法引用、伪造引用和证据不足。
5. 评测输出四项检索指标。
6. 真实 LLM 模式收到带来源编号的证据上下文，并对低分结果走证据不足分支。
7. 新增测试与原有测试全部通过，`compileall` 和 `git diff --check` 通过。
