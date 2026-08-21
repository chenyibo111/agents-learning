"""Keyword and persistent vector retrievers with one result contract."""

from __future__ import annotations

import os
from typing import Any, Protocol, Sequence, TypedDict

from ingest import DocumentChunk, tokenize


class SearchResult(TypedDict, total=False):
    source: str
    chunk_id: str
    text: str
    score: float
    retriever: str
    distance: float


class Retriever(Protocol):
    def search(self, query: str, top_k: int = 3) -> list[SearchResult]: ...


class KeywordRetriever:
    """A transparent lexical baseline with no model or database dependency."""

    def __init__(self, chunks: Sequence[DocumentChunk]):
        self.chunks = list(chunks)
        self.tokenized_chunks = [set(tokenize(chunk["text"])) for chunk in self.chunks]

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        top_k = max(1, int(top_k))
        query_terms = set(tokenize(query))
        if not query_terms:
            return []

        ranked: list[tuple[float, int]] = []
        for index, document_terms in enumerate(self.tokenized_chunks):
            overlap = len(query_terms & document_terms)
            if overlap:
                ranked.append((overlap / len(query_terms), index))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [
            {
                "source": self.chunks[index]["source"],
                "chunk_id": self.chunks[index]["chunk_id"],
                "text": self.chunks[index]["text"],
                "score": float(score),
                "retriever": "keyword",
            }
            for score, index in ranked[:top_k]
        ]


class VectorRetriever:
    """Query a Chroma collection using a SentenceTransformers embedding model."""

    def __init__(self, chunks: Sequence[DocumentChunk], embedding_model: Any, collection: Any):
        self.chunks = list(chunks)
        self.embedding_model = embedding_model
        self.collection = collection

    @classmethod
    def from_local(
        cls,
        chunks: Sequence[DocumentChunk],
        persist_dir: str,
        collection_name: str = "lesson_28_knowledge",
        model_name: str | None = None,
        rebuild: bool = False,
    ) -> "VectorRetriever":
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                "向量检索需要 chromadb 和 sentence-transformers，请先运行："
                "python -m pip install -r projects/28-document-retrieval/requirements.txt"
            ) from error

        model_name = model_name or os.getenv(
            "EMBEDDING_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )
        embedding_model = SentenceTransformer(model_name)
        client = chromadb.PersistentClient(path=persist_dir)
        if rebuild:
            try:
                client.delete_collection(collection_name)
            except Exception:
                pass

        collection = client.get_or_create_collection(name=collection_name)
        if collection.count() != len(chunks):
            embeddings = embedding_model.encode(
                [chunk["text"] for chunk in chunks],
                normalize_embeddings=True,
                show_progress_bar=True,
            )
            collection.upsert(
                ids=[chunk["chunk_id"] for chunk in chunks],
                embeddings=embeddings.tolist(),
                documents=[chunk["text"] for chunk in chunks],
                metadatas=[
                    {
                        "source": chunk["source"],
                        "chunk_id": chunk["chunk_id"],
                        "content_hash": chunk.get("content_hash", ""),
                    }
                    for chunk in chunks
                ],
            )

        return cls(
            chunks=chunks,
            embedding_model=embedding_model,
            collection=collection,
        )

    def search(self, query: str, top_k: int = 3) -> list[SearchResult]:
        top_k = max(1, int(top_k))
        query_embedding = self.embedding_model.encode(
            [query],
            normalize_embeddings=True,
        )[0]
        query_vector = (
            query_embedding.tolist()
            if hasattr(query_embedding, "tolist")
            else list(query_embedding)
        )
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        return [
            {
                "source": metadata["source"],
                "chunk_id": metadata["chunk_id"],
                "text": document,
                "score": float(1 / (1 + distance)),
                "distance": float(distance),
                "retriever": "vector",
            }
            for document, metadata, distance in zip(
                documents, metadatas, distances
            )
        ]
