# Memory 与 RAG 工程实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将第 8 课的固定关键词 Demo 扩展为带 Memory、可替换 Retriever、隔离、缓存、引用校验和评测的离线工程实现。

**Architecture:** 在课程项目下新增 `rag_memory` 包，用 contracts 定义文档、记忆和检索命中；memory、retrievers、cache、citations、evaluation 各自保持单一职责。`main.py` 只负责 CLI 编排和 LLM 上下文组装，默认继续使用离线实现。

**Tech Stack:** Python 3.11 标准库、SQLite、unittest、现有 OpenAI-compatible `common.ask_llm`；不新增强制外部依赖。

---

### Task 1: 建立数据契约与固定知识库

**Files:**
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/__init__.py`
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/contracts.py`
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/documents.py`
- Test: `hello-agents/tests/test_memory_and_rag.py`

- [ ] **Step 1: Write the failing tests** for document identity, tenant metadata, retrieval hit serialization, and fixed corpus loading.
- [ ] **Step 2: Run the focused tests and verify RED** because `rag_memory` does not exist.
- [ ] **Step 3: Implement minimal dataclasses** `Document`, `MemoryItem`, `RetrievalHit` and `default_documents()`.
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 2: Implement short-term and SQLite long-term memory

**Files:**
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/memory.py`
- Modify: `hello-agents/tests/test_memory_and_rag.py`

- [ ] **Step 1: Add failing tests** for short-term message order, SQLite round-trip across instances, tenant/user isolation, explicit deletion and expiration filtering.
- [ ] **Step 2: Run the focused memory tests and verify RED.**
- [ ] **Step 3: Implement `ShortTermMemory` and parameterized `SQLiteMemoryStore`.**
- [ ] **Step 4: Run focused memory tests and verify GREEN.**

### Task 3: Implement keyword, vector and hybrid retrievers

**Files:**
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/retrievers.py`
- Modify: `hello-agents/tests/test_memory_and_rag.py`

- [ ] **Step 1: Add failing tests** for top-k ordering, exact tenant filtering, deterministic vector scores, and hybrid rank fusion.
- [ ] **Step 2: Run the focused retriever tests and verify RED.**
- [ ] **Step 3: Implement the shared `Retriever` protocol, `KeywordRetriever`, `VectorRetriever` and `HybridRetriever`.**
- [ ] **Step 4: Run focused retriever tests and verify GREEN.**

### Task 4: Add retrieval cache and citations

**Files:**
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/cache.py`
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/citations.py`
- Modify: `hello-agents/tests/test_memory_and_rag.py`

- [ ] **Step 1: Add failing tests** for cache hits, invalidation on version change, stable evidence labels, valid/forged citation detection and insufficient evidence.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement bounded in-memory cache and citation utilities.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 5: Add offline retrieval evaluation

**Files:**
- Create: `hello-agents/projects/08-memory-and-rag/rag_memory/evaluation.py`
- Modify: `hello-agents/tests/test_memory_and_rag.py`

- [ ] **Step 1: Add failing tests** for Hit@K, Precision@K, Recall@K and MRR on a deterministic dataset.
- [ ] **Step 2: Run focused tests and verify RED.**
- [ ] **Step 3: Implement metric functions and aggregate evaluation.**
- [ ] **Step 4: Run focused tests and verify GREEN.**

### Task 6: Integrate the CLI and real LLM evidence flow

**Files:**
- Modify: `hello-agents/projects/08-memory-and-rag/main.py`
- Modify: `hello-agents/projects/08-memory-and-rag/README.md`
- Modify: `hello-agents/lessons/08-memory-and-rag.md`
- Modify: `hello-agents/PROGRESS.md`
- Modify: `hello-agents/CURRICULUM.md`
- Modify: `hello-agents/tests/test_projects.py`
- Modify: `hello-agents/tests/test_memory_and_rag.py`

- [ ] **Step 1: Add failing CLI tests** for legacy demo compatibility, retriever selection, tenant-aware output, evidence insufficiency and LLM prompt assembly via an injected fake asker.
- [ ] **Step 2: Run focused CLI tests and verify RED.**
- [ ] **Step 3: Integrate the package without deleting the old `retrieve()` entry point; add `--query`, `--retriever`, `--top-k`, `--tenant-id` and explicit memory commands.**
- [ ] **Step 4: Run focused tests and verify GREEN.**
- [ ] **Step 5: Run the full suite, compileall and diff check; update course status with evidence.**

### Task 7: Final verification

**Files:**
- No new production files.

- [ ] **Step 1: Run `python3 -m unittest discover -s hello-agents/tests -p 'test_*.py' -v`.**
- [ ] **Step 2: Run `python3 -m compileall -q hello-agents/projects/08-memory-and-rag`.**
- [ ] **Step 3: Run `git diff --check`.**
- [ ] **Step 4: Confirm no `.env`, API key, SQLite database or cache artifact is staged or modified.**
