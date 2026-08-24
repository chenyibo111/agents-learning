# 08 - Memory 与 RAG

对应课程：[08-memory-and-rag](../../lessons/08-memory-and-rag.md)，状态：✅；回顾 `achieve` 第 4～16 课。

运行：`python projects/08-memory-and-rag/main.py --demo`；`--llm` 解释记忆与 RAG 边界。Demo 使用固定文档做关键词检索，保证离线可重复。

实验：实现 top-k 参数；加入来源编号；分别测试短期历史、长期偏好和外部文档的权限边界。

## 三层实现状态

- 概念层：已覆盖 Memory、RAG、召回、来源和权限边界。
- 最小实践层：当前 Demo 已用固定文档执行关键词检索。
- 工程实现层：待加入可替换 Retriever/Memory 接口、持久化、向量检索、隔离、删除策略、引用校验和评测。
