"""Lesson 28 entry point for comparing keyword and vector retrieval."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from answer import DemoAnswerer, build_llm_answerer_from_env
from ingest import DocumentChunk, load_chunks
from retrievers import KeywordRetriever, SearchResult, VectorRetriever


DEFAULT_QUERY = "Agent 如何保存状态并恢复工作流？"
KNOWLEDGE_DIR = Path(__file__).with_name("knowledge")
VECTOR_STORE_DIR = Path(__file__).with_name("vector_store")


def _merge_results(groups: Sequence[Sequence[SearchResult]], top_k: int) -> list[SearchResult]:
    merged: dict[str, SearchResult] = {}
    for results in groups:
        for item in results:
            current = merged.get(item["chunk_id"])
            if current is None or item["score"] > current["score"]:
                merged[item["chunk_id"]] = item
    return sorted(
        merged.values(),
        key=lambda item: (-item["score"], item["chunk_id"]),
    )[: max(1, int(top_k))]


def build_retrievers(
    chunks: Sequence[DocumentChunk],
    mode: str,
    persist_dir: Path = VECTOR_STORE_DIR,
    rebuild: bool = False,
) -> list[object]:
    if mode == "keyword":
        return [KeywordRetriever(chunks)]
    if mode == "vector":
        return [VectorRetriever.from_local(chunks, str(persist_dir), rebuild=rebuild)]
    if mode == "both":
        return [
            KeywordRetriever(chunks),
            VectorRetriever.from_local(chunks, str(persist_dir), rebuild=rebuild),
        ]
    raise ValueError(f"未知检索模式：{mode}")


def search(
    retrievers: Sequence[object], query: str, top_k: int = 3
) -> list[SearchResult]:
    groups = [retriever.search(query, top_k) for retriever in retrievers]
    return _merge_results(groups, top_k) if len(groups) > 1 else groups[0]


def run(
    query: str,
    mode: str,
    answerer: object,
    output_fn: Callable[[str], None] = print,
    knowledge_dir: Path = KNOWLEDGE_DIR,
    persist_dir: Path = VECTOR_STORE_DIR,
    rebuild: bool = False,
) -> str:
    chunks = load_chunks(knowledge_dir)
    if not chunks:
        raise ValueError(f"知识库为空：{knowledge_dir}")
    retrievers = build_retrievers(chunks, mode, persist_dir, rebuild)
    results = search(retrievers, query)
    output_fn(
        json.dumps(
            {
                "retriever": mode,
                "result_count": len(results),
                "sources": [f"{item['source']}#{item['chunk_id']}" for item in results],
            },
            ensure_ascii=False,
        )
    )
    answer = answerer.answer(query, results)
    output_fn(answer)
    return answer


def main() -> None:
    parser = argparse.ArgumentParser(description="第28课：两种本地知识库检索器")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--demo", action="store_true", help="离线回答")
    modes.add_argument("--llm", action="store_true", help="使用真实 LLM 回答")
    parser.add_argument("--retriever", choices=["keyword", "vector", "both"], default="keyword")
    parser.add_argument("--query", default=DEFAULT_QUERY, help="检索问题")
    parser.add_argument("--rebuild", action="store_true", help="重建向量索引")
    args = parser.parse_args()

    try:
        answerer = DemoAnswerer() if args.demo else build_llm_answerer_from_env()
        run(args.query, args.retriever, answerer, rebuild=args.rebuild)
    except (RuntimeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
