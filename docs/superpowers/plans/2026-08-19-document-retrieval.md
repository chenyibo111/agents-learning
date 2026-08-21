# Document Retrieval Implementation Plan

> **For agentic workers:** Implement with tests first. Do not commit unless the user explicitly requests it.

**Goal:** Add lesson 28 with a local knowledge base and two interchangeable retrievers: a dependency-free keyword retriever and a persistent Chroma vector retriever.

**Architecture:** Markdown files are normalized into source-traceable chunks. Both retrievers implement the same `Retriever` protocol and return the same result shape. The CLI selects Demo or LLM answer generation independently from `keyword`, `vector`, or `both` retrieval. Real LLM tests use a fake OpenAI-compatible client; vector tests use fake embeddings and a fake collection.

**Tech Stack:** Python 3.11+, Markdown files, Chroma, SentenceTransformers, OpenAI-compatible `openai` client, `python-dotenv`, `unittest`.

---

### Task 1: Define document chunks and retriever behavior

**Files:**
- Create: `projects/28-document-retrieval/ingest.py`
- Create: `projects/28-document-retrieval/retrievers.py`
- Test: `tests/test_document_retrieval.py`

- [ ] Test Markdown paragraph loading, source and chunk IDs, and empty-directory errors.
- [ ] Test keyword search ranking and stable source metadata.
- [ ] Test vector search through injected fake embeddings and collection without importing optional packages.
- [ ] Implement the common `Retriever` protocol and both retrievers.

### Task 2: Add Demo/LLM answer generation

**Files:**
- Create: `projects/28-document-retrieval/answer.py`
- Create: `projects/28-document-retrieval/main.py`
- Create: `projects/28-document-retrieval/requirements.txt`
- Modify: `tests/test_document_retrieval.py`

- [ ] Test deterministic Demo answers and fake-client LLM answers.
- [ ] Add `--demo` and `--llm` modes plus `--retriever keyword|vector|both`.
- [ ] Keep API configuration limited to LLM mode and reject placeholder keys.
- [ ] Ensure retrieved results retain source and chunk IDs in the answer context.

### Task 3: Add sample knowledge and lesson materials

**Files:**
- Create: `projects/28-document-retrieval/knowledge/*.md`
- Create: `projects/28-document-retrieval/README.md`
- Create: `lessons/28-document-retrieval.md`
- Modify: `CURRICULUM.md`
- Modify: `README.md`
- Modify: `ROADMAP.md`

- [ ] Explain the same Retriever interface with keyword and vector implementations.
- [ ] Document Chroma persistence, embedding model requirements, and index rebuild behavior.
- [ ] Document macOS/zsh commands and the fact that vector mode may download/cache an embedding model on first use.
- [ ] Mark lesson 27 complete and lesson 28 in progress.

### Task 4: Verify

- [ ] Run focused retrieval tests.
- [ ] Run keyword Demo without network or API credentials.
- [ ] Run full repository tests.
- [ ] Run syntax, diff, and credential scans.
- [ ] Leave changes uncommitted.
