"""SQLite task history and approval storage for lesson 31."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    """Persist task metadata and approval history in SQLite."""

    def __init__(self, database: str | Path = "task_history.sqlite3") -> None:
        self.database = str(database)
        if self.database != ":memory:":
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                query TEXT NOT NULL,
                status TEXT NOT NULL,
                report TEXT NOT NULL DEFAULT '',
                state_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                decision TEXT NOT NULL,
                comment TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(task_id)
            );
            """
        )
        self.connection.commit()

    def create_task(self, task_id: str, query: str) -> None:
        timestamp = _now()
        self.connection.execute(
            """
            INSERT INTO tasks (
                task_id, query, status, report, state_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, query, "created", "", "{}", timestamp, timestamp),
        )
        self.connection.commit()

    def update_task(
        self,
        task_id: str,
        *,
        status: str,
        report: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        current = self._get_task_row(task_id)
        next_report = current["report"] if report is None else report
        next_state = (
            current["state_json"]
            if state is None
            else json.dumps(state, ensure_ascii=False, sort_keys=True)
        )
        self.connection.execute(
            """
            UPDATE tasks
            SET status = ?, report = ?, state_json = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (status, next_report, next_state, _now(), task_id),
        )
        self.connection.commit()

    def record_approval(
        self,
        task_id: str,
        decision: str,
        comment: str = "",
    ) -> None:
        if decision not in {"approved", "rejected"}:
            raise ValueError("decision 必须是 approved 或 rejected")
        self._get_task_row(task_id)
        self.connection.execute(
            """
            INSERT INTO approvals (task_id, decision, comment, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, decision, comment, _now()),
        )
        self.connection.commit()

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = self._get_task_row(task_id)
        approvals = self.connection.execute(
            """
            SELECT decision, comment, created_at
            FROM approvals
            WHERE task_id = ?
            ORDER BY id
            """,
            (task_id,),
        ).fetchall()
        return {
            "task_id": row["task_id"],
            "query": row["query"],
            "status": row["status"],
            "report": row["report"],
            "state": json.loads(row["state_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "approvals": [dict(item) for item in approvals],
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT task_id FROM tasks ORDER BY created_at"
        ).fetchall()
        return [self.get_task(row["task_id"]) for row in rows]

    def close(self) -> None:
        self.connection.close()

    def _get_task_row(self, task_id: str) -> sqlite3.Row:
        row = self.connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"任务不存在：{task_id}")
        return row
