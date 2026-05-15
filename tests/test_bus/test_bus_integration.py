"""Tests for EventBus integration with Runner and LlmAgent."""

import pytest

from soulbot.bus.events import BusEvent, AGENT_RESPONSE, SESSION_UPDATED
from soulbot.bus.event_bus import EventBus
from soulbot.agents.llm_agent import LlmAgent
from soulbot.agents.invocation_context import InvocationContext, RunConfig
from soulbot.events.event import Content, Event, Part
from soulbot.models.llm_request import LlmResponse
from soulbot.runners.runner import Runner
from soulbot.sessions.in_memory_session_service import InMemorySessionService
from soulbot.sessions.session import Session


class TestRunnerBusIntegration:
    async def test_runner_accepts_bus(self):
        bus = EventBus()
        agent = LlmAgent(name="test_agent", model="claude-acp/sonnet")
        session_service = InMemorySessionService()

        runner = Runner(
            agent=agent,
            app_name="test",
            session_service=session_service,
            bus=bus,
        )
        assert runner.bus is bus

    async def test_runner_without_bus(self):
        agent = LlmAgent(name="test_agent", model="claude-acp/sonnet")
        session_service = InMemorySessionService()

        runner = Runner(
            agent=agent,
            app_name="test",
            session_service=session_service,
        )
        assert runner.bus is None

    async def test_runner_publishes_session_updated(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe(SESSION_UPDATED, handler)

        agent = LlmAgent(
            name="test_agent",
            model="claude-acp/sonnet",
            before_model_callback=lambda ctx, req: LlmResponse(
                content=Content(role="model", parts=[Part(text="Hello")]),
            ),
        )
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="test",
            session_service=session_service,
            bus=bus,
        )

        events = []
        async for event in runner.run(user_id="u1", session_id="s1", message="Hi"):
            events.append(event)

        assert len(received) == 1
        assert received[0].type == SESSION_UPDATED
        assert received[0].data["session_id"] == "s1"

    async def test_runner_publishes_agent_response(self):
        bus = EventBus()
        received = []

        async def handler(event: BusEvent):
            received.append(event)

        bus.subscribe(AGENT_RESPONSE, handler)

        agent = LlmAgent(
            name="responder",
            model="claude-acp/sonnet",
            before_model_callback=lambda ctx, req: LlmResponse(
                content=Content(role="model", parts=[Part(text="World")]),
            ),
        )
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="test",
            session_service=session_service,
            bus=bus,
        )

        async for _ in runner.run(user_id="u1", session_id="s1", message="Hello"):
            pass

        assert len(received) == 1
        assert received[0].data["agent"] == "responder"
        assert received[0].data["text"] == "World"


class TestInvocationContextBus:
    def test_context_has_bus_field(self):
        session = Session(app_name="test", user_id="u", session_id="s")
        agent = LlmAgent(name="a", model="claude-acp/sonnet")
        bus = EventBus()

        ctx = InvocationContext(
            session=session,
            agent=agent,
            bus=bus,
        )
        assert ctx.bus is bus

    def test_context_bus_default_none(self):
        session = Session(app_name="test", user_id="u", session_id="s")
        agent = LlmAgent(name="a", model="claude-acp/sonnet")

        ctx = InvocationContext(session=session, agent=agent)
        assert ctx.bus is None


class TestLlmAgentBusPublish:
    async def test_llm_agent_publishes_agent_start(self):
        """before_model_callback short-circuits, so only agent.start is published."""
        bus = EventBus()
        event_types = []

        async def collector(event: BusEvent):
            event_types.append(event.type)

        bus.subscribe("*", collector)

        agent = LlmAgent(
            name="test_agent",
            model="claude-acp/sonnet",
            before_model_callback=lambda ctx, req: LlmResponse(
                content=Content(role="model", parts=[Part(text="Answer")]),
            ),
        )

        session = Session(app_name="test", user_id="u", session_id="s")
        ctx = InvocationContext(
            session=session,
            agent=agent,
            bus=bus,
        )

        async for _ in agent.run_async(ctx):
            pass

        assert "agent.start" in event_types
        # before_model_callback short-circuits before llm.request
        assert "llm.request" not in event_types

    async def test_llm_agent_no_bus_no_errors(self):
        """Without bus, events should not be published but no errors either."""
        agent = LlmAgent(
            name="test_agent",
            model="claude-acp/sonnet",
            before_model_callback=lambda ctx, req: LlmResponse(
                content=Content(role="model", parts=[Part(text="Answer")]),
            ),
        )

        session = Session(app_name="test", user_id="u", session_id="s")
        ctx = InvocationContext(
            session=session,
            agent=agent,
            bus=None,
        )

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].content.parts[0].text == "Answer"
