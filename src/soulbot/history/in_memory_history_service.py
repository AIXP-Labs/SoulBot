"""InMemoryChatHistoryService — non-persistent history for testing."""

from __future__ import annotations

import time
from typing import Optional

from .base_history_service import BaseChatHistoryService, ChatMessage


class InMemoryChatHistoryService(BaseChatHistoryService):
    """Stores chat history in memory. Data is lost on restart.

    Primarily used in unit tests to avoid SQLite I/O.
    """

    def __init__(self) -> None:
        self._messages: list[ChatMessage] = []
        self._next_id: int = 1

    async def add_message(
        self,
        user_id: str,
        agent: str,
        session_id: str,
        role: str,
        content: str,
        l2_json: str = "",
    ) -> None:
        msg = ChatMessage(
            id=self._next_id,
            user_id=user_id,
            agent=agent,
            session_id=session_id,
            role=role,
            content=content,
            l2_json=l2_json,
            created_at=int(time.time()),
        )
        self._messages.append(msg)
        self._next_id += 1

    async def get_session_history(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[ChatMessage]:
        msgs = [m for m in self._messages if m.session_id == session_id]
        msgs.sort(key=lambda m: (m.created_at, m.id))
        return msgs[:limit]

    async def get_agent_history(
        self,
        user_id: str,
        agent: str,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        msgs = [
            m for m in self._messages
            if m.user_id == user_id and m.agent == agent
        ]
        msgs.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        return msgs[:limit]

    async def search(
        self,
        user_id: str,
        agent: str,
        keyword: str,
        *,
        limit: int = 20,
    ) -> list[ChatMessage]:
        kw = keyword.lower()
        msgs = [
            m for m in self._messages
            if m.user_id == user_id and m.agent == agent and kw in m.content.lower()
        ]
        msgs.sort(key=lambda m: (m.created_at, m.id), reverse=True)
        return msgs[:limit]

    async def delete_agent_history(
        self,
        user_id: str,
        agent: str,
    ) -> int:
        before = len(self._messages)
        self._messages = [
            m for m in self._messages
            if not (m.user_id == user_id and m.agent == agent)
        ]
        return before - len(self._messages)

    async def delete_session_history(
        self,
        session_id: str,
    ) -> int:
        before = len(self._messages)
        self._messages = [
            m for m in self._messages
            if m.session_id != session_id
        ]
        return before - len(self._messages)

    async def count(
        self,
        user_id: str,
        agent: Optional[str] = None,
    ) -> int:
        if agent:
            return sum(
                1 for m in self._messages
                if m.user_id == user_id and m.agent == agent
            )
        return sum(1 for m in self._messages if m.user_id == user_id)
