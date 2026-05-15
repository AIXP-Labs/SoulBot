"""DatabaseSessionService — SQLite-backed persistent session storage.

Requires the ``aiosqlite`` package::

    pip install aiosqlite
    # or
    pip install soulbot[sqlite]
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from ..events.event import Event
from .base_session_service import BaseSessionService
from .session import Session
from .state import State


class DatabaseSessionService(BaseSessionService):
    """Persists sessions in a SQLite database via aiosqlite."""

    def __init__(self, db_path: str = "sessions.db") -> None:
        self.db_path = db_path
        self._initialized = False

    async def _get_db(self):
        try:
            import aiosqlite
        except ImportError as exc:
            raise ImportError(
                "aiosqlite is required for DatabaseSessionService. "
                "Install with: pip install aiosqlite  (or pip install soulbot[sqlite])"
            ) from exc
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        if not self._initialized:
            await self._create_tables(db)
            self._initialized = True
        return db

    async def _create_tables(self, db) -> None:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT NOT NULL,
                app_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT '{}',
                last_update_time REAL NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL DEFAULT 0,
                last_agent TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (app_name, user_id, id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                session_app TEXT NOT NULL,
                session_user TEXT NOT NULL,
                session_id TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (session_app, session_user, session_id)
                    REFERENCES sessions(app_name, user_id, id)
                    ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session
            ON events(session_app, session_user, session_id, created_at)
        """)
        # Migrate old databases: add columns if missing
        for col, typedef in [
            ("title", "TEXT NOT NULL DEFAULT ''"),
            ("created_at", "REAL NOT NULL DEFAULT 0"),
            ("last_agent", "TEXT NOT NULL DEFAULT ''"),
            ("agent_name", "TEXT NOT NULL DEFAULT ''"),
        ]:
            try:
                await db.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col} {typedef}"
                )
            except Exception:
                pass  # Column already exists

        # Index for agent-partitioned queries (Doc 11)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_agent
            ON sessions(app_name, user_id, agent_name, last_update_time DESC)
        """)

        # Migrate old data: copy agent name from app_name to last_agent
        # (only needed once — when last_agent is empty but app_name holds agent names)
        await self._migrate_app_name_to_last_agent(db)

        # Migrate: backfill agent_name from last_agent (Doc 11)
        await self._migrate_last_agent_to_agent_name(db)

        await db.commit()

    async def _migrate_app_name_to_last_agent(self, db) -> None:
        """One-time migration: populate last_agent from old app_name values.

        Old DBs stored agent names (e.g. ``"hello_agent"``) in ``app_name``.
        After Doc 21, ``app_name`` stores ``cli_name`` instead.
        This copies the old agent name into ``last_agent`` for sessions
        that haven't been migrated yet.
        """
        try:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM sessions WHERE last_agent = '' AND app_name != ''"
            )
            row = await cursor.fetchone()
            if row and row[0] > 0:
                # Check if any app_name looks like an old agent name (not a cli_name)
                # cli_names end with _cli; agent names typically don't
                cursor2 = await db.execute(
                    "SELECT DISTINCT app_name FROM sessions "
                    "WHERE last_agent = '' AND app_name NOT LIKE '%\\_cli' ESCAPE '\\'"
                )
                old_names = [r[0] for r in await cursor2.fetchall()]
                if old_names:
                    await db.execute(
                        "UPDATE sessions SET last_agent = app_name "
                        "WHERE last_agent = '' AND app_name NOT LIKE '%\\_cli' ESCAPE '\\'"
                    )
        except Exception:
            pass  # Best-effort migration

    async def _migrate_last_agent_to_agent_name(self, db) -> None:
        """One-time migration: backfill agent_name from last_agent (Doc 11)."""
        try:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM sessions WHERE agent_name = '' AND last_agent != ''"
            )
            row = await cursor.fetchone()
            if row and row[0] > 0:
                await db.execute(
                    "UPDATE sessions SET agent_name = last_agent WHERE agent_name = ''"
                )
        except Exception:
            pass  # Best-effort migration

    # -- CRUD ---------------------------------------------------------------

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        *,
        agent_name: str,
        session_id: Optional[str] = None,
        state: Optional[dict[str, object]] = None,
        title: Optional[str] = None,
    ) -> Session:
        db = await self._get_db()
        try:
            sid = session_id or str(uuid.uuid4())
            now = time.time()
            state_json = json.dumps(state or {}, ensure_ascii=False)
            session_title = title or ""
            await db.execute(
                "INSERT INTO sessions "
                "(id, app_name, user_id, agent_name, state, last_update_time, title, created_at, last_agent) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, app_name, user_id, agent_name, state_json, now, session_title, now, agent_name),
            )
            await db.commit()
            return Session(
                id=sid,
                app_name=app_name,
                user_id=user_id,
                agent_name=agent_name,
                last_agent=agent_name,
                title=session_title,
                created_at=now,
                state=State(state),
                last_update_time=now,
            )
        finally:
            await db.close()

    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        agent_name: str | None = None,
    ) -> Optional[Session]:
        # Plan 18 / 01: optional agent_name filter prevents cross-agent
        # session leak when multiple agents share the same cli_name partition.
        db = await self._get_db()
        try:
            if agent_name:
                cursor = await db.execute(
                    "SELECT * FROM sessions WHERE app_name=? AND user_id=? AND id=? AND agent_name=?",
                    (app_name, user_id, session_id, agent_name),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM sessions WHERE app_name=? AND user_id=? AND id=?",
                    (app_name, user_id, session_id),
                )
            row = await cursor.fetchone()
            if row is None:
                return None

            # Load events
            ev_cursor = await db.execute(
                "SELECT data FROM events "
                "WHERE session_app=? AND session_user=? AND session_id=? "
                "ORDER BY created_at",
                (app_name, user_id, session_id),
            )
            event_rows = await ev_cursor.fetchall()

            state_dict = json.loads(row["state"])
            events = [Event.model_validate_json(r["data"]) for r in event_rows]

            return Session(
                id=row["id"],
                app_name=row["app_name"],
                user_id=row["user_id"],
                agent_name=row["agent_name"] if "agent_name" in row.keys() else "",
                last_agent=row["last_agent"],
                title=row["title"],
                created_at=row["created_at"],
                state=State(state_dict),
                events=events,
                last_update_time=row["last_update_time"],
            )
        finally:
            await db.close()

    def _session_from_row(self, r) -> Session:
        """Build a Session (without events) from a DB row."""
        return Session(
            id=r["id"],
            app_name=r["app_name"],
            user_id=r["user_id"],
            agent_name=r["agent_name"] if "agent_name" in r.keys() else "",
            last_agent=r["last_agent"],
            title=r["title"],
            created_at=r["created_at"],
            state=State(json.loads(r["state"])),
            last_update_time=r["last_update_time"],
        )

    async def list_sessions(
        self,
        app_name: str,
        user_id: str,
        agent_name: str,
    ) -> list[Session]:
        db = await self._get_db()
        try:
            cursor = await db.execute(
                "SELECT id, app_name, user_id, agent_name, last_agent, state, "
                "last_update_time, title, created_at "
                "FROM sessions WHERE app_name=? AND user_id=? AND agent_name=? "
                "ORDER BY last_update_time DESC",
                (app_name, user_id, agent_name),
            )
            rows = await cursor.fetchall()
            return [self._session_from_row(r) for r in rows]
        finally:
            await db.close()

    async def list_all_sessions(
        self,
        app_name: str,
        user_id: str,
    ) -> list[Session]:
        db = await self._get_db()
        try:
            cursor = await db.execute(
                "SELECT id, app_name, user_id, agent_name, last_agent, state, "
                "last_update_time, title, created_at "
                "FROM sessions WHERE app_name=? AND user_id=? "
                "ORDER BY last_update_time DESC",
                (app_name, user_id),
            )
            rows = await cursor.fetchall()
            return [self._session_from_row(r) for r in rows]
        finally:
            await db.close()

    async def delete_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        db = await self._get_db()
        try:
            await db.execute(
                "DELETE FROM events WHERE session_app=? AND session_user=? AND session_id=?",
                (app_name, user_id, session_id),
            )
            await db.execute(
                "DELETE FROM sessions WHERE app_name=? AND user_id=? AND id=?",
                (app_name, user_id, session_id),
            )
            await db.commit()
        finally:
            await db.close()

    async def update_session_title(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        title: str,
    ) -> None:
        """Update the title of an existing session."""
        db = await self._get_db()
        try:
            await db.execute(
                "UPDATE sessions SET title=? WHERE app_name=? AND user_id=? AND id=?",
                (title, app_name, user_id, session_id),
            )
            await db.commit()
        finally:
            await db.close()

    async def update_last_agent(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> None:
        """Update the last_agent of an existing session."""
        db = await self._get_db()
        try:
            await db.execute(
                "UPDATE sessions SET last_agent=? WHERE app_name=? AND user_id=? AND id=?",
                (agent_name, app_name, user_id, session_id),
            )
            await db.commit()
        finally:
            await db.close()

    async def append_event(self, session: Session, event: Event) -> Event:
        # Apply in-memory side effects via parent
        event = await super().append_event(session, event)
        if event.partial:
            return event

        db = await self._get_db()
        try:
            # Persist event
            await db.execute(
                "INSERT INTO events (id, session_app, session_user, session_id, data, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.id,
                    session.app_name,
                    session.user_id,
                    session.id,
                    event.model_dump_json(),
                    event.timestamp,
                ),
            )
            # Update session state + timestamp
            now = time.time()
            await db.execute(
                "UPDATE sessions SET state=?, last_update_time=? "
                "WHERE app_name=? AND user_id=? AND id=?",
                (
                    json.dumps(dict(session.state), ensure_ascii=False),
                    now,
                    session.app_name,
                    session.user_id,
                    session.id,
                ),
            )
            await db.commit()
            session.last_update_time = now
        finally:
            await db.close()

        return event
