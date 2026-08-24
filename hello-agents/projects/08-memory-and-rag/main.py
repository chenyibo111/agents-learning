"""第 8 课 CLI：保留关键词 Demo，并提供可组合的 Memory/RAG 工程实现。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import ask_llm
from common.llm import LLMConfigurationError
from rag_memory.cache import RetrievalCache
from rag_memory.citations import (
    build_evidence,
    evidence_sufficient,
    validate_citations,
)
from rag_memory.documents import default_documents
from rag_memory.memory import ShortTermMemory, SQLiteMemoryStore
from rag_memory.retrievers import (
    HybridRetriever,
    KeywordRetriever,
    VectorRetriever,
)


# Keep the original public constant and function for the minimal lesson Demo.
DOCS = [
    "短期记忆保存当前会话。",
    "长期记忆保存稳定偏好。",
    "RAG 在请求时检索外部知识。",
]


def retrieve(query: str, top_k: int = 2) -> list[str]:
    """Legacy keyword-only entry point used by the first version of this lesson."""

    retriever = KeywordRetriever(default_documents())
    return [
        hit.document.text
        for hit in retriever.search(query, tenant_id="default", top_k=top_k)
    ]


def build_retriever(name: str, *, tenant_id: str):
    documents = default_documents(tenant_id=tenant_id)
    if name == "keyword":
        return KeywordRetriever(documents)
    if name == "vector":
        return VectorRetriever(documents)
    if name == "both":
        return HybridRetriever(documents)
    raise ValueError(f"未知检索器：{name}")


def _run_retrieval(
    query: str,
    *,
    retriever_name: str,
    top_k: int,
    tenant_id: str,
    cache: RetrievalCache | None = None,
):
    retriever = build_retriever(retriever_name, tenant_id=tenant_id)
    active_cache = cache or RetrievalCache()
    hits, cache_hit = active_cache.search(
        retriever,
        query,
        tenant_id=tenant_id,
        top_k=top_k,
    )
    return retriever, hits, cache_hit


def run_query(
    query: str,
    *,
    retriever_name: str = "keyword",
    top_k: int = 2,
    tenant_id: str = "default",
    cache: RetrievalCache | None = None,
) -> dict[str, Any]:
    """Run offline retrieval and return JSON-safe evidence metadata."""

    _, hits, cache_hit = _run_retrieval(
        query,
        retriever_name=retriever_name,
        top_k=top_k,
        tenant_id=tenant_id,
        cache=cache,
    )
    return {
        "query": query,
        "tenant_id": tenant_id,
        "retriever": retriever_name,
        "top_k": top_k,
        "cache_hit": cache_hit,
        "evidence_sufficient": evidence_sufficient(hits),
        "hits": [hit.to_dict() for hit in hits],
        "evidence": build_evidence(hits),
    }


def build_llm_prompt(
    query: str,
    hits,
    *,
    short_term_messages: list[dict[str, Any]] | None = None,
    long_term_memories: list[Any] | None = None,
) -> str:
    """Assemble model context from program-owned memory and evidence."""

    short_term = short_term_messages or []
    long_term = long_term_memories or []
    history_text = "\n".join(
        f"{message.get('role')}: {message.get('content')}" for message in short_term
    ) or "（无）"
    memory_text = "\n".join(
        f"- {item.content if hasattr(item, 'content') else item}"
        for item in long_term
    ) or "（无）"
    evidence = build_evidence(hits)
    return (
        f"用户问题：{query}\n\n"
        f"短期会话记忆：\n{history_text}\n\n"
        f"长期记忆：\n{memory_text}\n\n"
        f"本轮外部证据（只能使用这些证据）：\n{evidence}\n\n"
        "请基于本轮外部证据回答。如果证据不足，请明确说证据不足。"
        "使用证据编号引用事实，例如 [S1]。不要创建证据中不存在的来源。"
    )


def answer_with_llm(
    query: str,
    *,
    retriever_name: str = "keyword",
    top_k: int = 2,
    tenant_id: str = "default",
    asker: Callable[..., str] = ask_llm,
    short_term_messages: list[dict[str, Any]] | None = None,
    long_term_memories: list[Any] | None = None,
) -> dict[str, Any]:
    """Retrieve first, then call the model only when evidence is sufficient."""

    _, hits, cache_hit = _run_retrieval(
        query,
        retriever_name=retriever_name,
        top_k=top_k,
        tenant_id=tenant_id,
    )
    result: dict[str, Any] = {
        "query": query,
        "tenant_id": tenant_id,
        "retriever": retriever_name,
        "top_k": top_k,
        "cache_hit": cache_hit,
        "evidence_sufficient": evidence_sufficient(hits),
        "hits": [hit.to_dict() for hit in hits],
        "evidence": build_evidence(hits),
        "llm_called": False,
        "citation_valid": False,
    }
    if not evidence_sufficient(hits):
        result["answer"] = "证据不足，当前知识库没有找到可以支持回答的资料。"
        return result

    short_term = ShortTermMemory()
    for message in short_term_messages or []:
        short_term.add(
            message.get("role", "user"),
            message.get("content", ""),
        )
    short_term.add("user", query)
    prompt = build_llm_prompt(
        query,
        hits,
        short_term_messages=short_term.snapshot(),
        long_term_memories=long_term_memories,
    )
    raw_answer = asker(
        prompt,
        system=(
            "你是一个严格基于外部证据回答的助手。只能引用提示词中存在的 [S1]、[S2] 等来源。"
        ),
    )
    validation = validate_citations(raw_answer, hits)
    result.update(
        {
            "llm_called": True,
            "citation_valid": validation.valid,
            "citation_labels": validation.used_labels,
            "unknown_citation_labels": validation.unknown_labels,
            "raw_answer": raw_answer,
            "answer": raw_answer
            if validation.valid
            else "模型回答未通过当前证据引用校验。",
        }
    )
    return result


def _memory_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not (args.remember or args.show_memory or args.delete_memory_id):
        return {}
    store = SQLiteMemoryStore(args.memory_db)
    try:
        added = [
            store.add(args.tenant_id, args.user_id, content).to_dict()
            for content in args.remember or []
        ]
        deleted = False
        if args.delete_memory_id:
            deleted = store.delete(
                args.delete_memory_id,
                args.tenant_id,
                args.user_id,
            )
        current = store.search(args.tenant_id, args.user_id, "")
        return {
            "memory": {
                "tenant_id": args.tenant_id,
                "user_id": args.user_id,
                "added": added,
                "deleted": deleted,
                "items": [item.to_dict() for item in current],
            }
        }
    finally:
        store.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="第 8 课：Memory 与 RAG")
    parser.add_argument("--demo", action="store_true", help="运行离线 Memory/RAG Demo")
    parser.add_argument("--llm", action="store_true", help="检索证据后调用真实 LLM")
    parser.add_argument("--query", default="长期记忆和 RAG 的区别")
    parser.add_argument("--retriever", choices=["keyword", "vector", "both"], default="keyword")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--user-id", default="demo-user")
    parser.add_argument("--memory-db", default=":memory:")
    parser.add_argument("--remember", action="append", help="显式写入一条长期记忆，可重复传入")
    parser.add_argument("--show-memory", action="store_true")
    parser.add_argument("--delete-memory-id")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.top_k < 1:
            raise ValueError("top_k 必须大于 0")
        if args.llm:
            result = answer_with_llm(
                args.query,
                retriever_name=args.retriever,
                top_k=args.top_k,
                tenant_id=args.tenant_id,
            )
        else:
            result = run_query(
                args.query,
                retriever_name=args.retriever,
                top_k=args.top_k,
                tenant_id=args.tenant_id,
            )
            result.update(_memory_payload(args))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (LLMConfigurationError, ValueError) as error:
        print(f"执行失败：{error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
