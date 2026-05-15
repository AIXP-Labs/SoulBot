"""SQLite-backed storage for ScheduleEntry (Doc 23)."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from .schedule_service import ScheduleEntry

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    trigger_config TEXT NOT NULL,
    aisop TEXT NOT NULL DEFAULT '[]',
    task TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    origin_channel TEXT NOT NULL DEFAULT '',
    origin_user TEXT NOT NULL DEFAULT '',
    from_agent TEXT NOT NULL DEFAULT '',
    to_agent TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    last_run TEXT,
    run_count INTEGER NOT NULL DEFAULT 0,
    last_result TEXT,
    last_error TEXT
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_sched_status ON schedules(status);",
    "CREATE INDEX IF NOT EXISTS idx_sched_agent ON schedules(from_agent);",
]


class SqliteScheduleStore:
    """SQLite-backed storage for ScheduleEntry."""

    def __init__(self, db_path: str, *, migrate_json: str | None = None) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()
        if migrate_json:
            self._migrate_from_json(migrate_json)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_entry(self, entry: ScheduleEntry) -> None:
        """INSERT OR REPLACE a single entry."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO schedules
                   (id, trigger_config, aisop, task, status,
                    origin_channel, origin_user, from_agent, to_agent,
                    created_at, last_run, run_count, last_result, last_error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._entry_to_row(entry),
            )
            conn.commit()
        finally:
            conn.close()

    def update_entry(self, entry: ScheduleEntry) -> None:
        """UPDATE a single entry by id."""
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE schedules SET
                   trigger_config=?, aisop=?, task=?, status=?,
                   origin_channel=?, origin_user=?, from_agent=?, to_agent=?,
                   created_at=?, last_run=?, run_count=?, last_result=?, last_error=?
                   WHERE id=?""",
                (
                    json.dumps(entry.trigger_config, ensure_ascii=False),
                    json.dumps(entry.aisop, ensure_ascii=False),
                    json.dumps(entry.task, ensure_ascii=False),
                    entry.status,
                    entry.origin_channel,
                    entry.origin_user,
                    entry.from_agent,
                    entry.to_agent,
                    entry.created_at,
                    entry.last_run,
                    entry.run_count,
                    entry.last_result,
                    entry.last_error,
                    entry.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_entry(self, entry_id: str) -> ScheduleEntry | None:
        """Get a single entry by id."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id=?", (entry_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    def list_entries(self, status: str | None = None) -> list[ScheduleEntry]:
        """List entries, optionally filtered by status."""
        conn = self._connect()
        try:
            if status:
                rows = conn.execute(
                    "SELECT * FROM schedules WHERE status=? ORDER BY created_at",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM schedules ORDER BY created_at"
                ).fetchall()
            return [self._row_to_entry(r) for r in rows]
        finally:
            conn.close()

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a single entry. Returns True if found."""
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM schedules WHERE id=?", (entry_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Migration
    # ------------------------------------------------------------------

    def _migrate_from_json(self, json_path: str) -> int:
        """One-time migration: read old JSON -> write to SQLite -> rename .bak."""
        if not os.path.exists(json_path):
            return 0
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read JSON for migration: %s", exc)
            return 0

        count = 0
        for item in data:
            # Backward compat: migrate agent_name -> from_agent/to_agent
            if "agent_name" in item:
                old = item.pop("agent_name")
                item.setdefault("from_agent", old)
                item.setdefault("to_agent", old)
            try:
                entry = ScheduleEntry(**item)
                self.save_entry(entry)
                count += 1
            except Exception as exc:
                logger.warning("Failed to migrate schedule entry: %s", exc)

        # Rename old file to .bak
        try:
            os.rename(json_path, json_path + ".bak")
        except OSError as exc:
            logger.warning("Failed to rename JSON to .bak: %s", exc)

        if count:
            logger.info("Migrated %d schedule entries from JSON to SQLite", count)
        return count

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_table(self) -> None:
        conn = self._connect()
        try:
            conn.execute(_CREATE_TABLE)
            for idx_sql in _CREATE_INDEXES:
                conn.execute(idx_sql)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _entry_to_row(entry: ScheduleEntry) -> tuple:
        return (
            entry.id,
            json.dumps(entry.trigger_config, ensure_ascii=False),
            json.dumps(entry.aisop, ensure_ascii=False),
            json.dumps(entry.task, ensure_ascii=False),
            entry.status,
            entry.origin_channel,
            entry.origin_user,
            entry.from_agent,
            entry.to_agent,
            entry.created_at,
            entry.last_run,
            entry.run_count,
            entry.last_result,
            entry.last_error,
        )

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> ScheduleEntry:
        return ScheduleEntry(
            id=row["id"],
            trigger_config=json.loads(row["trigger_config"]),
            aisop=json.loads(row["aisop"]),
            task=json.loads(row["task"]),
            status=row["status"],
            origin_channel=row["origin_channel"],
            origin_user=row["origin_user"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            created_at=row["created_at"],
            last_run=row["last_run"],
            run_count=row["run_count"],
            last_result=row["last_result"],
            last_error=row["last_error"],
        )
