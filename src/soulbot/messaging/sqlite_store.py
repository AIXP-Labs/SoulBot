"""SQLite-backed storage for AgentMessageEntry (Doc 08).

Mirrors scheduler/sqlite_store.py in style. Lives in its own DB file
(soulbot_messages.db) for independent backup and failure isolation
(see Doc 08 §13.1 #4).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from .message_entry import (
    STATUS_DELIVERED,
    AgentMessageEntry,
    TERMINAL_STATUSES,
)

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS agent_messages (
    id            TEXT PRIMARY KEY,
    from_agent    TEXT NOT NULL,
    to_agent      TEXT NOT NULL,
    aisop         TEXT NOT NULL DEFAULT '[]',
    status        TEXT NOT NULL DEFAULT 'pending',
    reply_mode    TEXT NOT NULL DEFAULT 'none',
    parent_id     TEXT,
    depth         INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    delivered_at  TEXT,
    result        TEXT,
    error         TEXT
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_from ON agent_messages(from_agent, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_messages_to ON agent_messages(to_agent, status);",
    "CREATE INDEX IF NOT EXISTS idx_messages_parent ON agent_messages(parent_id);",
    "CREATE INDEX IF NOT EXISTS idx_messages_status_created ON agent_messages(status, created_at);",
]

# B1.1 audit fix (v1.8): single-row table acting as advisory lock for
# multi-process restore() safety. holder_pid + acquired_at let us detect
# stale locks (e.g. crashed worker) and reclaim after STALE_LOCK_SECONDS.
_CREATE_LOCK_TABLE = """
CREATE TABLE IF NOT EXISTS agent_messages_locks (
    name        TEXT PRIMARY KEY,
    holder_pid  INTEGER NOT NULL,
    acquired_at REAL NOT NULL
);
"""
_RESTORE_LOCK_NAME = "restore"
_STALE_LOCK_SECONDS = 600  # 10 minutes


class SqliteMessageStore:
    """SQLite-backed storage for AgentMessageEntry."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save_entry(self, entry: AgentMessageEntry) -> None:
        """INSERT OR REPLACE a single entry."""
        conn = self._connect()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO agent_messages
                   (id, from_agent, to_agent, aisop, status, reply_mode,
                    parent_id, depth, created_at, delivered_at, result, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                self._entry_to_row(entry),
            )
            conn.commit()
        finally:
            conn.close()

    def update_entry(self, entry: AgentMessageEntry) -> None:
        """UPDATE a single entry by id."""
        conn = self._connect()
        try:
            conn.execute(
                """UPDATE agent_messages SET
                   from_agent=?, to_agent=?, aisop=?, status=?, reply_mode=?,
                   parent_id=?, depth=?, created_at=?, delivered_at=?,
                   result=?, error=?
                   WHERE id=?""",
                (
                    entry.from_agent,
                    entry.to_agent,
                    json.dumps(entry.aisop, ensure_ascii=False),
                    entry.status,
                    entry.reply_mode,
                    entry.parent_id,
                    entry.depth,
                    entry.created_at,
                    entry.delivered_at,
                    entry.result,
                    entry.error,
                    entry.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_entry(self, entry_id: str) -> AgentMessageEntry | None:
        """Get a single entry by id."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM agent_messages WHERE id=?", (entry_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    def list_entries(
        self,
        *,
        status: str | None = None,
        from_agent: str | None = None,
        to_agent: str | None = None,
        parent_id: str | None = None,
        limit: int = 100,
    ) -> list[AgentMessageEntry]:
        """List entries with optional filters, ordered by created_at DESC."""
        clauses: list[str] = []
        params: list = []
        if status is not None:
            clauses.append("status=?")
            params.append(status)
        if from_agent is not None:
            clauses.append("from_agent=?")
            params.append(from_agent)
        if to_agent is not None:
            clauses.append("to_agent=?")
            params.append(to_agent)
        if parent_id is not None:
            clauses.append("parent_id=?")
            params.append(parent_id)

        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT * FROM agent_messages{where} ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        conn = self._connect()
        try:
            rows = conn.execute(sql, tuple(params)).fetchall()
            return [self._row_to_entry(r) for r in rows]
        finally:
            conn.close()

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a single entry. Returns True if a row was removed."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM agent_messages WHERE id=?", (entry_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_terminal_before(self, cutoff_iso: str) -> int:
        """Delete entries with terminal status created before cutoff_iso.

        Used by AgentMessageService.cleanup() (Doc 08 §4.11).
        Pending / processing entries are NEVER deleted (audit safety).
        Returns number of rows deleted.

        W1 audit fix (v1.10): also runs ``PRAGMA wal_checkpoint(PASSIVE)``
        opportunistically after deletion to prevent unbounded WAL file
        growth in high-volume deployments. PASSIVE mode never blocks
        readers / writers; if checkpoint cannot complete, it just returns
        without error.
        """
        terminal_list = list(TERMINAL_STATUSES)
        placeholders = ",".join("?" * len(terminal_list))
        conn = self._connect()
        try:
            cursor = conn.execute(
                f"DELETE FROM agent_messages "
                f"WHERE status IN ({placeholders}) AND created_at < ?",
                (*terminal_list, cutoff_iso),
            )
            conn.commit()
            try:
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.OperationalError as exc:
                logger.debug("wal_checkpoint skipped: %s", exc)
            return cursor.rowcount
        finally:
            conn.close()

    def count(self, *, status: str | None = None) -> int:
        """Count entries, optionally filtered by status."""
        conn = self._connect()
        try:
            if status is not None:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM agent_messages WHERE status=?",
                    (status,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS c FROM agent_messages"
                ).fetchone()
            return int(row["c"]) if row else 0
        finally:
            conn.close()

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
            # F5 audit fix (v1.9): integrity check on startup. Logs warning
            # if the WAL/SHM is corrupted so operators see it at boot rather
            # than via cryptic query errors at first read.
            try:
                row = conn.execute("PRAGMA integrity_check").fetchone()
                if row and row[0] != "ok":
                    logger.warning(
                        "SQLite integrity_check returned %r for %s — "
                        "DB may be corrupted. Consider restoring from backup.",
                        row[0], self._db_path,
                    )
            except sqlite3.OperationalError as exc:
                logger.warning(
                    "Could not run PRAGMA integrity_check on %s: %s",
                    self._db_path, exc,
                )
            conn.execute(_CREATE_TABLE)
            conn.execute(_CREATE_LOCK_TABLE)  # B1.1 audit fix
            for idx_sql in _CREATE_INDEXES:
                conn.execute(idx_sql)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Multi-process restore lock (B1.1 audit fix, v1.8)
    # ------------------------------------------------------------------

    def try_acquire_restore_lock(self) -> bool:
        """Attempt to claim the restore advisory lock.

        Returns True if THIS process now owns the lock, False if another
        live process holds it. Stale locks (older than _STALE_LOCK_SECONDS)
        are reclaimed.

        Uses ``BEGIN IMMEDIATE`` to make the read-then-write atomic so
        two workers calling this concurrently don't both win.
        """
        import os
        import time as _time
        my_pid = os.getpid()
        now = _time.time()
        cutoff = now - _STALE_LOCK_SECONDS

        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT holder_pid, acquired_at FROM agent_messages_locks WHERE name=?",
                (_RESTORE_LOCK_NAME,),
            ).fetchone()
            if row is None:
                conn.execute(
                    "INSERT INTO agent_messages_locks (name, holder_pid, acquired_at) "
                    "VALUES (?, ?, ?)",
                    (_RESTORE_LOCK_NAME, my_pid, now),
                )
                conn.commit()
                return True
            if row["acquired_at"] < cutoff:
                # Stale lock — reclaim
                conn.execute(
                    "UPDATE agent_messages_locks SET holder_pid=?, acquired_at=? "
                    "WHERE name=?",
                    (my_pid, now, _RESTORE_LOCK_NAME),
                )
                conn.commit()
                logger.warning(
                    "Reclaimed stale restore lock (was held by pid %s for %.0fs)",
                    row["holder_pid"], now - row["acquired_at"],
                )
                return True
            conn.rollback()
            return False
        except sqlite3.DatabaseError as exc:
            # W4 audit fix (v1.10): broaden to DatabaseError so
            # IntegrityError, ProgrammingError, etc. also degrade
            # gracefully (treat as "held by another holder") instead of
            # crashing service init. OperationalError covers the common
            # `database is locked` path.
            logger.info("restore lock contention: %s; treating as held", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            conn.close()

    def release_restore_lock(self) -> None:
        """Release the restore lock held by this process. Best-effort."""
        import os
        my_pid = os.getpid()
        conn = self._connect()
        try:
            conn.execute(
                "DELETE FROM agent_messages_locks WHERE name=? AND holder_pid=?",
                (_RESTORE_LOCK_NAME, my_pid),
            )
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _entry_to_row(entry: AgentMessageEntry) -> tuple:
        return (
            entry.id,
            entry.from_agent,
            entry.to_agent,
            json.dumps(entry.aisop, ensure_ascii=False),
            entry.status,
            entry.reply_mode,
            entry.parent_id,
            entry.depth,
            entry.created_at,
            entry.delivered_at,
            entry.result,
            entry.error,
        )

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> AgentMessageEntry:
        return AgentMessageEntry(
            id=row["id"],
            from_agent=row["from_agent"],
            to_agent=row["to_agent"],
            aisop=json.loads(row["aisop"]),
            status=row["status"],
            reply_mode=row["reply_mode"],
            parent_id=row["parent_id"],
            depth=int(row["depth"]),
            created_at=row["created_at"],
            delivered_at=row["delivered_at"],
            result=row["result"],
            error=row["error"],
        )


# Re-export for convenience: STATUS_DELIVERED is referenced by service for
# typical "completed" filter queries.
__all__ = ["SqliteMessageStore", "STATUS_DELIVERED"]
