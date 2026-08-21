"""Load Markdown files into source-traceable chunks."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TypedDict


class DocumentChunk(TypedDict, total=False):
    source: str
    chunk_id: str
    text: str
    content_hash: str


def tokenize(text: str) -> list[str]:
    """Tokenize Chinese characters and Latin/numeric terms for keyword search."""
    return re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", text.lower())


def _paragraphs(content: str) -> list[str]:
    paragraphs = []
    for paragraph in re.split(r"\n\s*\n", content):
        cleaned = paragraph.strip()
        if not cleaned:
            continue
        # A heading by itself carries little searchable content.
        if re.fullmatch(r"#{1,6}\s+.+", cleaned):
            continue
        paragraphs.append(cleaned)
    return paragraphs


def load_chunks(directory: str | Path) -> list[DocumentChunk]:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"知识库目录不存在：{root}")

    chunks: list[DocumentChunk] = []
    for path in sorted(root.glob("*.md")):
        paragraphs = _paragraphs(path.read_text(encoding="utf-8"))
        for index, paragraph in enumerate(paragraphs, start=1):
            chunks.append(
                {
                    "source": path.name,
                    "chunk_id": f"{path.stem}-{index}",
                    "text": paragraph,
                    "content_hash": hashlib.sha256(
                        paragraph.encode("utf-8")
                    ).hexdigest()[:12],
                }
            )
    return chunks
