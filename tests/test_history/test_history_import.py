"""Tests for import_history_to_session (Doc 22 Step 7)."""

import pytest

from soulbot.history import (
    InMemoryChatHistoryService,
    import_history_to_session,
)
from soulbot.sessions import InMemorySessionService, Session


@pytest.fixture
def history_svc():
    return InMemoryChatHistoryService()


@pytest.fixture
def session_svc():
    return InMemorySessionService()


class TestImportHistoryToSession:
    async def test_import_creates_events(self, history_svc, session_svc):
        await history_svc.add_message("u1", "agent_a", "old-s", "user", "hello")
        await history_svc.add_message("u1", "agent_a", "old-s", "assistant", "hi!")
        await history_svc.add_message("u1", "agent_a", "old-s", "user", "how are you?")

        session = await session_svc.create_session("app", "u1", agent_name="test", session_id="new-s")
        imported = await import_history_to_session(
            history_svc, session_svc, session, "u1", "agent_a",
        )
        assert imported == 3
        assert len(session.events) == 3

    async def test_import_chronological(self, history_svc, session_svc):
        await history_svc.add_message("u1", "agent_a", "old-s", "user", "first")
        await history_svc.add_message("u1", "agent_a", "old-s", "assistant", "second")
        await history_svc.add_message("u1", "agent_a", "old-s", "user", "third")

        session = await session_svc.create_session("app", "u1", agent_name="test", session_id="new-s")
        await import_history_to_session(
            history_svc, session_svc, session, "u1", "agent_a",
        )
        texts = [e.content.parts[0].text for e in session.events]
        assert texts == ["first", "second", "third"]

    async def test_import_empty_history(self, history_svc, session_svc):
        session = await session_svc.create_session("app", "u1", agent_name="test", session_id="new-s")
        imported = await import_history_to_session(
            history_svc, session_svc, session, "u1", "agent_a",
        )
        assert imported == 0
        assert len(session.events) == 0

    async def test_import_limit(self, history_svc, session_svc):
        for i in range(10):
            await history_svc.add_message("u1", "agent_a", "old-s", "user", f"msg {i}")

        session = await session_svc.create_session("app", "u1", agent_name="test", session_id="new-s")
        imported = await import_history_to_session(
            history_svc, session_svc, session, "u1", "agent_a", limit=5,
        )
        assert imported == 5
        assert len(session.events) == 5

    async def test_import_roles_correct(self, history_svc, session_svc):
        await history_svc.add_message("u1", "agent_a", "old-s", "user", "from user")
        await history_svc.add_message("u1", "agent_a", "old-s", "assistant", "from ai")

        session = await session_svc.create_session("app", "u1", agent_name="test", session_id="new-s")
        await import_history_to_session(
            history_svc, session_svc, session, "u1", "agent_a",
        )

        user_event = session.events[0]
        assert user_event.author == "user"
        assert user_event.content.role == "user"

        ai_event = session.events[1]
        assert ai_event.author == "agent_a"
        assert ai_event.content.role == "model"

    async def test_import_does_not_affect_other_sessions(self, history_svc, session_svc):
        await history_svc.add_message("u1", "agent_a", "old-s", "user", "hello")

        session1 = await session_svc.create_session("app", "u1", agent_name="test", session_id="s1")
        session2 = await session_svc.create_session("app", "u1", agent_name="test", session_id="s2")

        await import_history_to_session(
            history_svc, session_svc, session1, "u1", "agent_a",
        )
        assert len(session1.events) == 1
        assert len(session2.events) == 0
