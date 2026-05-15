"""SQLite store for heartbeat execution history (heartbeat.db)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS heartbeat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    fired_at TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT '',
    skipped INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_hb_agent ON heartbeat_history(agent_name);",
    "CREATE INDEX IF NOT EXISTS idx_hb_fired ON heartbeat_history(fired_at);",
]


class HeartbeatStore:
    """SQLite-backed heartbeat execution history."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _ensure_table(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(_CREATE_TABLE)
            for idx in _CREATE_INDEXES:
                conn.execute(idx)
            conn.commit()

    def record(
        self,
        agent_name: str,
        entry_id: str,
        result: str = "",
        skipped: bool = False,
    ) -> None:
        """Record a heartbeat execution."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO heartbeat_history (agent_name, entry_id, fired_at, result, skipped) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    agent_name,
                    entry_id,
                    datetime.now().isoformat(),
                    result,
                    1 if skipped else 0,
                ),
            )
            conn.commit()

    def query(
        self,
        agent_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query heartbeat history.

        Args:
            agent_name: Filter by agent name (None = all agents).
            limit: Max number of records.
            offset: Skip first N records.

        Returns:
            List of history records as dicts.
        """
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            if agent_name:
                rows = conn.execute(
                    "SELECT * FROM heartbeat_history WHERE agent_name = ? "
                    "ORDER BY id DESC LIMIT ? OFFSET ?",
                    (agent_name, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM heartbeat_history "
                    "ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()

        return [dict(r) for r in rows]

    def count(self, agent_name: str | None = None) -> int:
        """Count heartbeat records."""
        with sqlite3.connect(self._db_path) as conn:
            if agent_name:
                row = conn.execute(
                    "SELECT COUNT(*) FROM heartbeat_history WHERE agent_name = ?",
                    (agent_name,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM heartbeat_history",
                ).fetchone()
            return row[0] if row else 0
