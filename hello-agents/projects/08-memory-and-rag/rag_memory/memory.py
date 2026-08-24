"""Short-term and SQLite-backed long-term memory implementations."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4

from .contracts import MemoryItem


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[\u4e00-\u9fff]|[a-zA-Z0-9_]+", value.lower()))


class ShortTermMemory:
    """Conversation-local messages; nothing is persisted after process exit."""

    def __init__(self):
        self.messages: list[dict[str, Any]] = []

    def add(self, role: str, content: str, **metadata: Any) -> None:
        if not role.strip():
            raise ValueError("短期记忆消息 role 不能为空")
        message: dict[str, Any] = {"role": role, "content": content}
        message.update(metadata)
        self.messages.append(message)

    def clear(self) -> None:
        self.messages.clear()

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(message) for message in self.messages]


class SQLiteMemoryStore:
    """Tenant/user-scoped long-term memory with explicit deletion."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                kind TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_owner
            ON memories (tenant_id, user_id, created_at)
            """
        )
        self.connection.commit()

    def add(
        self,
        tenant_id: str,
        user_id: str,
        content: str,
        *,
        kind: str = "fact",
        expires_at: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        if not tenant_id.strip() or not user_id.strip():
            raise ValueError("长期记忆必须包含 tenant_id 和 user_id")
        if not content.strip():
            raise ValueError("长期记忆内容不能为空")
        item = MemoryItem(
            id=str(uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            content=content,
            kind=kind,
            created_at=time(),
            expires_at=expires_at,
            metadata=dict(metadata or {}),
        )
        self.connection.execute(
            """
            INSERT INTO memories
                (id, tenant_id, user_id, content, kind, created_at, expires_at, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.tenant_id,
                item.user_id,
                item.content,
                item.kind,
                item.created_at,
                item.expires_at,
                json.dumps(item.metadata, ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return item

    def search(
        self,
        tenant_id: str,
        user_id: str,
        query: str = "",
        *,
        limit: int = 20,
        now: float | None = None,
    ) -> list[MemoryItem]:
        if limit < 1:
            raise ValueError("长期记忆 search limit 必须大于 0")
        current_time = time() if now is None else now
        rows = self.connection.execute(
            """
            SELECT * FROM memories
            WHERE tenant_id = ? AND user_id = ?
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY created_at DESC
            """,
            (tenant_id, user_id, current_time),
        ).fetchall()
        query_tokens = _tokens(query)
        scored: list[tuple[int, float, sqlite3.Row]] = []
        for row in rows:
            overlap = len(query_tokens & _tokens(row["content"])) if query_tokens else 0
            scored.append((overlap, row["created_at"], row))
        scored.sort(key=lambda value: (value[0], value[1]), reverse=True)
        return [self._row_to_item(row) for _, _, row in scored[:limit] if not query or _tokens(query) & _tokens(row["content"])]

    def delete(self, memory_id: str, tenant_id: str, user_id: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM memories WHERE id = ? AND tenant_id = ? AND user_id = ?",
            (memory_id, tenant_id, user_id),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def clear_user(self, tenant_id: str, user_id: str) -> int:
        cursor = self.connection.execute(
            "DELETE FROM memories WHERE tenant_id = ? AND user_id = ?",
            (tenant_id, user_id),
        )
        self.connection.commit()
        return cursor.rowcount

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            content=row["content"],
            kind=row["kind"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            metadata=json.loads(row["metadata_json"]),
        )
