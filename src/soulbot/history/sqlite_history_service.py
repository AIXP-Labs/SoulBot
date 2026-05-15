"""SqliteChatHistoryService — SQLite-backed persistent chat history."""

from __future__ import annotations

import logging
import time
from typing import Optional

from .base_history_service import BaseChatHistoryService, ChatMessage

logger = logging.getLogger(__name__)

_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL DEFAULT 'default',
    agent TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    l2_json TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL
);
"""

_MIGRATE_L2 = "ALTER TABLE chat_history ADD COLUMN l2_json TEXT NOT NULL DEFAULT ''"

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_chat_agent ON chat_history(user_id, agent, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history(session_id, created_at);",
]


class SqliteChatHistoryService(BaseChatHistoryService):
    """Stores chat history in a SQLite database.

    Args:
        db_path: Path to the SQLite database file.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._initialized = False

    async def _ensure_db(self):
        """Lazily create tables on first access."""
        if self._initialized:
            return
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            for idx_sql in _CREATE_INDEXES:
                await db.execute(idx_sql)
            # Migrate: add l2_json column if missing
            try:
                await db.execute(_MIGRATE_L2)
            except Exception:
                pass  # column already exists
            await db.commit()
        self._initialized = True

    async def add_message(
        self,
        user_id: str,
        agent: str,
        session_id: str,
        role: str,
        content: str,
        l2_json: str = "",
    ) -> None:
        await self._ensure_db()
        import aiosqlite

        now = int(time.time())
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO chat_history (user_id, agent, session_id, role, content, l2_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, agent, session_id, role, content, l2_json, now),
            )
            await db.commit()

    async def get_session_history(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[ChatMessage]:
        await self._ensure_db()
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, user_id, agent, session_id, role, content, created_at "
                "FROM chat_history WHERE session_id=? "
                "ORDER BY created_at ASC, id ASC LIMIT ?",
                (session_id, limit),
            )
            rows = await cursor.fetchall()
        return [_row_to_message(r) for r in rows]

    async def get_agent_history(
        self,
        user_id: str,
        agent: str,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        await self._ensure_db()
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, user_id, agent, session_id, role, content, created_at "
                "FROM chat_history WHERE user_id=? AND agent=? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, agent, limit),
            )
            rows = await cursor.fetchall()
        return [_row_to_message(r) for r in rows]

    async def search(
        self,
        user_id: str,
        agent: str,
        keyword: str,
        *,
        limit: int = 20,
    ) -> list[ChatMessage]:
        await self._ensure_db()
        import aiosqlite

        pattern = f"%{keyword}%"
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT id, user_id, agent, session_id, role, content, created_at "
                "FROM chat_history WHERE user_id=? AND agent=? AND content LIKE ? "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (user_id, agent, pattern, limit),
            )
            rows = await cursor.fetchall()
        return [_row_to_message(r) for r in rows]

    async def delete_agent_history(
        self,
        user_id: str,
        agent: str,
    ) -> int:
        await self._ensure_db()
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM chat_history WHERE user_id=? AND agent=?",
                (user_id, agent),
            )
            await db.commit()
            return cursor.rowcount

    async def delete_session_history(
        self,
        session_id: str,
    ) -> int:
        await self._ensure_db()
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM chat_history WHERE session_id=?",
                (session_id,),
            )
            await db.commit()
            return cursor.rowcount

    async def count(
        self,
        user_id: str,
        agent: Optional[str] = None,
    ) -> int:
        await self._ensure_db()
        import aiosqlite

        if agent:
            sql = "SELECT COUNT(*) FROM chat_history WHERE user_id=? AND agent=?"
            params = (user_id, agent)
        else:
            sql = "SELECT COUNT(*) FROM chat_history WHERE user_id=?"
            params = (user_id,)

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(sql, params)
            row = await cursor.fetchone()
            return row[0] if row else 0


def _row_to_message(row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        user_id=row["user_id"],
        agent=row["agent"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        l2_json=row["l2_json"] if "l2_json" in row.keys() else "",
        created_at=row["created_at"],
    )
