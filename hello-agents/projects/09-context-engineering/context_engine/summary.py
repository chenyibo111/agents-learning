"""SQLite persistence for auditable conversation summaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sqlite3
from pathlib import Path
from time import time


@dataclass(frozen=True)
class SummaryRecord:
    conversation_id: str
    summary: str
    source_ids: list[str]
    updated_at: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class SQLiteSummaryStore:
    """Upsert and load summaries without losing their source trace."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                conversation_id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                source_ids_json TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self.connection.commit()

    def save(
        self,
        conversation_id: str,
        summary: str,
        *,
        source_ids: list[str] | None = None,
    ) -> SummaryRecord:
        if not conversation_id.strip():
            raise ValueError("conversation_id 不能为空")
        if not summary.strip():
            raise ValueError("summary 不能为空")
        record = SummaryRecord(
            conversation_id=conversation_id,
            summary=summary,
            source_ids=list(source_ids or []),
            updated_at=time(),
        )
        self.connection.execute(
            """
            INSERT INTO summaries (conversation_id, summary, source_ids_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(conversation_id) DO UPDATE SET
                summary=excluded.summary,
                source_ids_json=excluded.source_ids_json,
                updated_at=excluded.updated_at
            """,
            (
                record.conversation_id,
                record.summary,
                json.dumps(record.source_ids, ensure_ascii=False),
                record.updated_at,
            ),
        )
        self.connection.commit()
        return record

    def load(self, conversation_id: str) -> SummaryRecord | None:
        row = self.connection.execute(
            "SELECT * FROM summaries WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        if row is None:
            return None
        return SummaryRecord(
            conversation_id=row["conversation_id"],
            summary=row["summary"],
            source_ids=json.loads(row["source_ids_json"]),
            updated_at=row["updated_at"],
        )

    def close(self) -> None:
        self.connection.close()
