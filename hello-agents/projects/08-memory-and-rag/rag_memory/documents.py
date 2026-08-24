"""The small deterministic knowledge corpus used by offline lesson runs."""

from __future__ import annotations

from .contracts import Document


def default_documents(*, tenant_id: str = "default") -> list[Document]:
    """Return fresh documents so callers can safely attach their own metadata."""

    return [
        Document(
            id="doc-1",
            source="memory.md",
            chunk_id="memory-1",
            text="短期记忆保存当前会话消息和工具观察。",
            tenant_id=tenant_id,
        ),
        Document(
            id="doc-2",
            source="memory.md",
            chunk_id="memory-2",
            text="长期记忆保存跨会话仍然稳定、有用并且允许保存的用户偏好。",
            tenant_id=tenant_id,
        ),
        Document(
            id="doc-3",
            source="rag.md",
            chunk_id="rag-1",
            text="RAG 在请求时检索外部知识，把带来源的证据放入上下文后再生成回答。",
            tenant_id=tenant_id,
        ),
    ]
