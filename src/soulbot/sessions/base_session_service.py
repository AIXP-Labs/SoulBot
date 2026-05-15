"""BaseSessionService — abstract interface for session persistence."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

from ..events.event import Event
from .session import Session
from .state import State


class BaseSessionService(ABC):
    """Abstract base for session storage backends."""

    @abstractmethod
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
        ...

    @abstractmethod
    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        agent_name: str | None = None,
    ) -> Session | None:
        ...

    @abstractmethod
    async def list_sessions(
        self,
        app_name: str,
        user_id: str,
        agent_name: str,
    ) -> list[Session]:
        ...

    async def list_all_sessions(
        self,
        app_name: str,
        user_id: str,
    ) -> list[Session]:
        """List sessions across all agents."""
        return []

    @abstractmethod
    async def delete_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> None:
        ...

    async def update_last_agent(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
        agent_name: str,
    ) -> None:
        """Update the last_agent field on a session."""

    async def append_event(self, session: Session, event: Event) -> Event:
        """Append an event to *session* and apply its side effects.

        This base implementation handles:
        1. Skipping partial streaming events.
        2. Stripping ``temp:`` keys from the persisted state_delta.
        3. Applying the state_delta to ``session.state``.
        4. Appending the event to ``session.events``.

        Subclasses that override this should call ``super().append_event()``
        or replicate the same logic.
        """
        if event.partial:
            return event

        # Apply state_delta
        if event.actions.state_delta:
            # Strip temp: keys for persistence (but still apply to live state)
            persisted_delta: dict[str, object] = {}
            for key, value in event.actions.state_delta.items():
                session.state.apply_delta({key: value})
                if not key.startswith(State.TEMP_PREFIX):
                    persisted_delta[key] = value
            # Overwrite the delta so only persistable keys remain
            event.actions.state_delta = persisted_delta

        session.events.append(event)
        session.last_update_time = time.time()
        return event
