"""Chat history — persistent storage for all conversation messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base_history_service import BaseChatHistoryService, ChatMessage
from .in_memory_history_service import InMemoryChatHistoryService
from .sqlite_history_service import SqliteChatHistoryService

if TYPE_CHECKING:
    from ..sessions.base_session_service import BaseSessionService
    from ..sessions.session import Session

__all__ = [
    "BaseChatHistoryService",
    "ChatMessage",
    "InMemoryChatHistoryService",
    "SqliteChatHistoryService",
    "import_history_to_session",
]


async def import_history_to_session(
    history_service: BaseChatHistoryService,
    session_service: BaseSessionService,
    session: Session,
    user_id: str,
    agent: str,
    *,
    limit: int = 20,
) -> int:
    """Import recent chat history into *session* as events.

    Fetches the most recent messages from *history_service* and appends
    them to *session* via *session_service*.  This provides LLM context
    from previous sessions without automatic injection.

    Returns the number of messages imported.
    """
    from ..events.event import Content, Event, Part

    messages = await history_service.get_agent_history(
        user_id, agent, limit=limit,
    )
    if not messages:
        return 0

    imported = 0
    for m in reversed(messages):  # newest-first → chronological
        event = Event(
            author=agent if m.role == "assistant" else "user",
            content=Content(
                role="model" if m.role == "assistant" else "user",
                parts=[Part(text=m.content)],
            ),
        )
        await session_service.append_event(session, event)
        imported += 1
    return imported
