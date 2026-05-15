"""BaseChatHistoryService — abstract interface for persistent chat history."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single chat message record."""

    id: int = 0
    user_id: str = "default"
    agent: str = ""
    session_id: str = ""
    role: str = ""  # "user" | "assistant"
    content: str = ""
    l2_json: str = ""  # L2 audit JSON (assistant only)
    created_at: int = 0  # unix timestamp (seconds)


class BaseChatHistoryService(ABC):
    """Abstract base for persistent chat history storage.

    Records every message (user + assistant) to a durable store,
    queryable by agent, session, keyword, or time range.
    """

    @abstractmethod
    async def add_message(
        self,
        user_id: str,
        agent: str,
        session_id: str,
        role: str,
        content: str,
        l2_json: str = "",
    ) -> None:
        """Record a single chat message."""
        ...

    @abstractmethod
    async def get_session_history(
        self,
        session_id: str,
        *,
        limit: int = 100,
    ) -> list[ChatMessage]:
        """Return messages for a specific session (chronological order)."""
        ...

    @abstractmethod
    async def get_agent_history(
        self,
        user_id: str,
        agent: str,
        *,
        limit: int = 50,
    ) -> list[ChatMessage]:
        """Return recent messages for a user+agent pair (newest first)."""
        ...

    @abstractmethod
    async def search(
        self,
        user_id: str,
        agent: str,
        keyword: str,
        *,
        limit: int = 20,
    ) -> list[ChatMessage]:
        """Search messages by keyword (newest first)."""
        ...

    @abstractmethod
    async def delete_agent_history(
        self,
        user_id: str,
        agent: str,
    ) -> int:
        """Delete all messages for a user+agent pair. Returns count deleted."""
        ...

    @abstractmethod
    async def delete_session_history(
        self,
        session_id: str,
    ) -> int:
        """Delete all messages for a session. Returns count deleted."""
        ...

    @abstractmethod
    async def count(
        self,
        user_id: str,
        agent: Optional[str] = None,
    ) -> int:
        """Count messages for a user, optionally filtered by agent."""
        ...
