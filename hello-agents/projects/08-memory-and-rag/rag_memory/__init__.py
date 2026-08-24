"""Composable, dependency-light Memory and RAG building blocks for lesson 08."""

from .contracts import Document, MemoryItem, RetrievalHit
from .documents import default_documents

__all__ = ["Document", "MemoryItem", "RetrievalHit", "default_documents"]
