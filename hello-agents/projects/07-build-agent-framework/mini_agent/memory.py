"""Conversation memory and a small SQLite checkpoint store."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
from time import time
from typing import Any
from uuid import uuid4

from .contracts import AgentEvent, Message


@dataclass
class Memory:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    task: str = ""
    status: str = "running"
    step: int = 0
    messages: list[Message] = field(default_factory=list)
    events: list[AgentEvent] = field(default_factory=list)
    completed_steps: list[int] = field(default_factory=list)
    total_usage_tokens: int = 0
    error: str = ""

    def add_message(self, message: Message) -> None:
        self.messages.append(message)

    def add_event(self, event: AgentEvent) -> None:
        self.events.append(event)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task": self.task,
            "status": self.status,
            "step": self.step,
            "messages": [message.to_dict() for message in self.messages],
            "events": [event.to_dict() for event in self.events],
            "completed_steps": list(self.completed_steps),
            "total_usage_tokens": self.total_usage_tokens,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Memory":
        return cls(
            run_id=payload["run_id"],
            task=payload.get("task", ""),
            status=payload.get("status", "running"),
            step=int(payload.get("step", 0)),
            messages=[Message(**item) for item in payload.get("messages", [])],
            events=[AgentEvent(**item) for item in payload.get("events", [])],
            completed_steps=[int(item) for item in payload.get("completed_steps", [])],
            total_usage_tokens=int(payload.get("total_usage_tokens", 0)),
            error=payload.get("error", ""),
        )


class SQLiteCheckpointStore:
    """Persist a complete Memory snapshot for local resume experiments."""

    def __init__(self, path: str | Path):
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                run_id TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self.connection.commit()

    def save(self, memory: Memory) -> None:
        self.connection.execute(
            """
            INSERT INTO checkpoints(run_id, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                payload=excluded.payload,
                updated_at=excluded.updated_at
            """,
            (
                memory.run_id,
                json.dumps(memory.to_dict(), ensure_ascii=False),
                time(),
            ),
        )
        self.connection.commit()

    def load(self, run_id: str) -> Memory:
        row = self.connection.execute(
            "SELECT payload FROM checkpoints WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(f"找不到 checkpoint：{run_id}")
        return Memory.from_dict(json.loads(row["payload"]))

    def close(self) -> None:
        self.connection.close()
