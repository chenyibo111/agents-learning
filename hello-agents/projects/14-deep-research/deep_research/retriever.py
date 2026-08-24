"""可替换检索器接口和本地 Fixture 实现。"""

from typing import Protocol

from .corpus import fixture_sources
from .schemas import ResearchQuery, Source


class RetrievalError(RuntimeError):
    pass


class Retriever(Protocol):
    def search(self, query: ResearchQuery, *, round_index: int) -> list[Source]: ...


class FixtureRetriever:
    def __init__(self, *, conflict: bool = False, fail_on_round: int | None = None):
        self.conflict = conflict
        self.fail_on_round = fail_on_round

    def search(self, query: ResearchQuery, *, round_index: int) -> list[Source]:
        if self.fail_on_round == round_index:
            raise RetrievalError(f"retrieval_failed_round_{round_index}")
        sources = fixture_sources(conflict=self.conflict)
        if round_index == 1:
            return list(sources[:2])
        return [sources[1], *sources[2:]]


def dedupe_sources(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    result: list[Source] = []
    for source in sources:
        key = source.url or source.source_id
        if key in seen:
            continue
        seen.add(key)
        result.append(source)
    return result
