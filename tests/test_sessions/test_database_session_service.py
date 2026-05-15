"""Tests for DatabaseSessionService (SQLite)."""

import pytest

# Skip all tests if aiosqlite is not installed
aiosqlite = pytest.importorskip("aiosqlite")

from soulbot.events.event import Content, Event, Part
from soulbot.events.event_actions import EventActions
from soulbot.sessions.database_session_service import DatabaseSessionService


@pytest.fixture
async def service(tmp_path):
    db_path = str(tmp_path / "test_sessions.db")
    svc = DatabaseSessionService(db_path=db_path)
    return svc


class TestDatabaseSessionService:
    @pytest.mark.asyncio
    async def test_create_session(self, service):
        session = await service.create_session("app", "u1", agent_name="test", session_id="s1")
        assert session.id == "s1"
        assert session.app_name == "app"
        assert session.user_id == "u1"

    @pytest.mark.asyncio
    async def test_create_session_auto_id(self, service):
        session = await service.create_session("app", "u1", agent_name="test")
        assert session.id  # Should have an auto-generated UUID

    @pytest.mark.asyncio
    async def test_create_with_state(self, service):
        session = await service.create_session("app", "u1", agent_name="test", state={"key": "val"})
        assert session.state["key"] == "val"

    @pytest.mark.asyncio
    async def test_get_session(self, service):
        await service.create_session("app", "u1", agent_name="test", session_id="s1")
        session = await service.get_session("app", "u1", "s1")
        assert session is not None
        assert session.id == "s1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, service):
        session = await service.get_session("app", "u1", "nope")
        assert session is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, service):
        await service.create_session("app", "u1", agent_name="test", session_id="s1")
        await service.create_session("app", "u1", agent_name="test", session_id="s2")
        await service.create_session("app", "u2", agent_name="test", session_id="s3")

        sessions = await service.list_sessions("app", "u1", agent_name="test")
        assert len(sessions) == 2
        ids = {s.id for s in sessions}
        assert ids == {"s1", "s2"}

    @pytest.mark.asyncio
    async def test_delete_session(self, service):
        await service.create_session("app", "u1", agent_name="test", session_id="s1")
        await service.delete_session("app", "u1", "s1")
        assert await service.get_session("app", "u1", "s1") is None

    @pytest.mark.asyncio
    async def test_append_event(self, service):
        session = await service.create_session("app", "u1", agent_name="test", session_id="s1")
        event = Event(
            author="user",
            content=Content(role="user", parts=[Part(text="Hello")]),
        )
        await service.append_event(session, event)

        # Reload session from DB
        loaded = await service.get_session("app", "u1", "s1")
        assert len(loaded.events) == 1
        assert loaded.events[0].content.parts[0].text == "Hello"

    @pytest.mark.asyncio
    async def test_append_event_with_state(self, service):
        session = await service.create_session("app", "u1", agent_name="test", session_id="s1")
        event = Event(
            author="agent",
            content=Content(role="model", parts=[Part(text="Hi")]),
            actions=EventActions(state_delta={"count": 1}),
        )
        await service.append_event(session, event)

        # Reload and check state was persisted
        loaded = await service.get_session("app", "u1", "s1")
        assert loaded.state["count"] == 1

    @pytest.mark.asyncio
    async def test_partial_events_not_persisted(self, service):
        session = await service.create_session("app", "u1", agent_name="test", session_id="s1")
        partial = Event(
            author="agent",
            content=Content(role="model", parts=[Part(text="stream...")]),
            partial=True,
        )
        await service.append_event(session, partial)

        loaded = await service.get_session("app", "u1", "s1")
        assert len(loaded.events) == 0

    @pytest.mark.asyncio
    async def test_multiple_events_order(self, service):
        session = await service.create_session("app", "u1", agent_name="test", session_id="s1")

        for i in range(5):
            event = Event(
                author=f"agent_{i}",
                content=Content(role="model", parts=[Part(text=f"msg {i}")]),
            )
            await service.append_event(session, event)

        loaded = await service.get_session("app", "u1", "s1")
        assert len(loaded.events) == 5
        texts = [e.content.parts[0].text for e in loaded.events]
        assert texts == [f"msg {i}" for i in range(5)]

    @pytest.mark.asyncio
    async def test_delete_cascades_events(self, service):
        session = await service.create_session("app", "u1", agent_name="test", session_id="s1")
        event = Event(
            author="user",
            content=Content(role="user", parts=[Part(text="Hi")]),
        )
        await service.append_event(session, event)
        await service.delete_session("app", "u1", "s1")

        # Session and its events should be gone
        assert await service.get_session("app", "u1", "s1") is None
