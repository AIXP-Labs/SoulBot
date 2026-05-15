"""Tests for InMemorySessionService."""

import pytest

from soulbot.events import Content, Event, EventActions, Part
from soulbot.sessions import InMemorySessionService, State


@pytest.fixture
def service():
    return InMemorySessionService()


class TestInMemorySessionService:
    @pytest.mark.asyncio
    async def test_create_session(self, service):
        s = await service.create_session("app1", "user1", agent_name="test")
        assert s.app_name == "app1"
        assert s.user_id == "user1"
        assert s.id  # auto-generated

    @pytest.mark.asyncio
    async def test_create_session_custom_id(self, service):
        s = await service.create_session("app1", "user1", agent_name="test", session_id="custom-id")
        assert s.id == "custom-id"

    @pytest.mark.asyncio
    async def test_create_session_with_state(self, service):
        s = await service.create_session("app1", "user1", agent_name="test", state={"lang": "en"})
        assert s.state["lang"] == "en"

    @pytest.mark.asyncio
    async def test_get_session(self, service):
        s = await service.create_session("app1", "user1", agent_name="test", session_id="s1")
        got = await service.get_session("app1", "user1", "s1")
        assert got is not None
        assert got.id == "s1"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service):
        result = await service.get_session("app1", "user1", "nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, service):
        await service.create_session("app1", "user1", agent_name="test", session_id="s1")
        await service.create_session("app1", "user1", agent_name="test", session_id="s2")
        await service.create_session("app1", "user2", agent_name="test", session_id="s3")

        sessions = await service.list_sessions("app1", "user1", agent_name="test")
        assert len(sessions) == 2
        ids = {s.id for s in sessions}
        assert ids == {"s1", "s2"}

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, service):
        sessions = await service.list_sessions("app1", "user1", agent_name="test")
        assert sessions == []

    @pytest.mark.asyncio
    async def test_delete_session(self, service):
        await service.create_session("app1", "user1", agent_name="test", session_id="s1")
        await service.delete_session("app1", "user1", "s1")
        result = await service.get_session("app1", "user1", "s1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session_nonexistent(self, service):
        # Should not raise
        await service.delete_session("app1", "user1", "nope")

    @pytest.mark.asyncio
    async def test_append_event_basic(self, service):
        session = await service.create_session("app1", "user1", agent_name="test")
        event = Event(
            author="agent",
            content=Content(role="model", parts=[Part(text="hi")]),
        )
        result = await service.append_event(session, event)
        assert result is event
        assert len(session.events) == 1
        assert session.events[0].author == "agent"

    @pytest.mark.asyncio
    async def test_append_event_applies_state_delta(self, service):
        session = await service.create_session("app1", "user1", agent_name="test")
        event = Event(
            author="agent",
            actions=EventActions(state_delta={"count": 5, "name": "test"}),
        )
        await service.append_event(session, event)
        assert session.state["count"] == 5
        assert session.state["name"] == "test"

    @pytest.mark.asyncio
    async def test_append_event_strips_temp_keys(self, service):
        session = await service.create_session("app1", "user1", agent_name="test")
        event = Event(
            author="agent",
            actions=EventActions(
                state_delta={"keep": "yes", "temp:scratch": "tmp"}
            ),
        )
        await service.append_event(session, event)
        # temp keys applied to live state
        assert session.state["temp:scratch"] == "tmp"
        assert session.state["keep"] == "yes"
        # But stripped from persisted delta
        assert "temp:scratch" not in event.actions.state_delta
        assert "keep" in event.actions.state_delta

    @pytest.mark.asyncio
    async def test_append_event_skips_partial(self, service):
        session = await service.create_session("app1", "user1", agent_name="test")
        event = Event(
            author="agent",
            partial=True,
            content=Content(parts=[Part(text="stream chunk")]),
        )
        result = await service.append_event(session, event)
        assert result is event
        assert len(session.events) == 0  # partial not appended

    @pytest.mark.asyncio
    async def test_append_event_updates_timestamp(self, service):
        session = await service.create_session("app1", "user1", agent_name="test")
        old_time = session.last_update_time
        event = Event(author="agent", content=Content(parts=[Part(text="x")]))
        await service.append_event(session, event)
        assert session.last_update_time >= old_time
