# 08 - Memory 与 RAG

对应课程：[08-memory-and-rag](../../lessons/08-memory-and-rag.md)，状态：✅；回顾 `achieve` 第 4～16 课。

运行：

```bash
python projects/08-memory-and-rag/main.py --demo
python projects/08-memory-and-rag/main.py \
  --demo \
  --query "长期记忆和 RAG 的区别" \
  --retriever both \
  --top-k 2 \
  --tenant-id tenant-a
```

`--llm` 会先检索证据，再把带 `[S1]`、`[S2]` 来源编号的上下文交给真实 LLM；没有足够证据时不会调用模型。

```bash
python projects/08-memory-and-rag/main.py \
  --llm \
  --query "长期记忆和 RAG 的区别" \
  --retriever keyword
```

显式写入和查看长期记忆：

```bash
python projects/08-memory-and-rag/main.py \
  --demo \
  --memory-db /tmp/lesson08-memory.sqlite3 \
  --tenant-id tenant-a \
  --user-id user-1 \
  --remember "喜欢中文回答" \
  --show-memory
```

实验：实现 top-k 参数；加入来源编号；分别测试短期历史、长期偏好和外部文档的权限边界。

## 三层实现状态

- 概念层：已覆盖 Memory、RAG、召回、来源和权限边界。
- 最小实践层：当前 Demo 已用固定文档执行关键词检索。
- 工程实现层：已完成可替换 Retriever/Memory 接口、SQLite 长期记忆、纯 Python 向量检索、混合检索、租户隔离、删除/过期策略、缓存、引用校验和评测。

## 工程实现组成

`rag_memory/` 包按职责拆分：

- `contracts.py`：`Document`、`MemoryItem`、`RetrievalHit` 数据契约；
- `memory.py`：短期记忆和 SQLite 长期记忆；
- `retrievers.py`：关键词、确定性向量和 RRF 混合检索；
- `cache.py`：按租户、查询、top-k 和索引版本缓存；
- `citations.py`：证据编号、引用校验和证据不足判断；
- `evaluation.py`：Hit@K、Precision@K、Recall@K、MRR。

本课的 `VectorRetriever` 是不依赖外部模型的词频向量实现，目的是让离线测试稳定；它提供了未来接入真实 Embedding/向量数据库时可以复用的接口，不等同于神经网络语义 Embedding。
