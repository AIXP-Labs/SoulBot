"""InMemorySessionService — non-persistent session storage for development."""

from __future__ import annotations

import uuid

from ..events.event import Event
from .base_session_service import BaseSessionService
from .session import Session
from .state import State


class InMemorySessionService(BaseSessionService):
    """Stores sessions in a plain dict.  Data is lost on process restart."""

    def __init__(self) -> None:
        # {app_name: {user_id: {session_id: Session}}}
        self._store: dict[str, dict[str, dict[str, Session]]] = {}

    # -- helpers ------------------------------------------------------------

    def _ensure_path(self, app_name: str, user_id: str) -> dict[str, Session]:
        return self._store.setdefault(app_name, {}).setdefault(user_id, {})

    # -- CRUD ---------------------------------------------------------------

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        *,
        agent_name: str,
        session_id: str | None = None,
        state: dict[str, object] | None = None,
        title: str | None = None,
    ) -> Session:
        bucket = self._ensure_path(app_name, user_id)
        sid = session_id or str(uuid.uuid4())
        session = Session(
            id=sid,
            app_name=app_name,
            user_id=user_id,
            agent_name=agent_name,
            last_agent=agent_name,
            title=title or "",
            state=State(state),
        )
        bucket[sid] = session
        return session

    async def update_session_title(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        title: str,
    ) -> None:
        """Update the title of an existing session."""
        session = await self.get_session(app_name, user_id, session_id)
        if session:
            session.title = title

    async def update_last_agent(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> None:
        """Update the last_agent field on a session."""
        session = await self.get_session(app_name, user_id, session_id)
        if session:
            session.last_agent = agent_name

    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        agent_name: str | None = None,
    ) -> Session | None:
        # Plan 18 / 01: when agent_name provided, require it to match so
        # cross-agent session leak (same cli_name partition) is blocked.
        session = (
            self._store
            .get(app_name, {})
            .get(user_id, {})
            .get(session_id)
        )
        if session is None:
            return None
        if agent_name and session.agent_name and session.agent_name != agent_name:
            return None
        return session

    async def list_sessions(
        self,
        app_name: str,
        user_id: str,
        agent_name: str,
    ) -> list[Session]:
        bucket = self._store.get(app_name, {}).get(user_id, {})
        result = [s for s in bucket.values() if s.agent_name == agent_name]
        return sorted(result, key=lambda s: s.last_update_time, reverse=True)

    async def list_all_sessions(
        self,
        app_name: str,
        user_id: str,
    ) -> list[Session]:
        bucket = self._store.get(app_name, {}).get(user_id, {})
        return sorted(
            bucket.values(),
            key=lambda s: s.last_update_time,
            reverse=True,
        )

    async def delete_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        bucket = self._store.get(app_name, {}).get(user_id, {})
        bucket.pop(session_id, None)

    async def append_event(self, session: Session, event: Event) -> Event:
        return await super().append_event(session, event)
