"""Tests for BaseAgent."""

import pytest

from soulbot.agents import BaseAgent
from soulbot.events import Content, Event, Part


class DummyAgent(BaseAgent):
    """Concrete agent for testing."""

    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            content=Content(role="model", parts=[Part(text=f"Hello from {self.name}")]),
        )


class TestBaseAgent:
    def test_create_agent(self):
        agent = DummyAgent(name="test_agent", description="A test agent")
        assert agent.name == "test_agent"
        assert agent.description == "A test agent"
        assert agent.parent_agent is None
        assert agent.sub_agents == []

    def test_sub_agents_wired(self):
        child1 = DummyAgent(name="child1")
        child2 = DummyAgent(name="child2")
        parent = DummyAgent(name="parent", sub_agents=[child1, child2])

        assert child1.parent_agent is parent
        assert child2.parent_agent is parent
        assert len(parent.sub_agents) == 2

    def test_root_agent_no_parent(self):
        agent = DummyAgent(name="root")
        assert agent.root_agent is agent

    def test_root_agent_with_parent(self):
        child = DummyAgent(name="child")
        parent = DummyAgent(name="parent", sub_agents=[child])
        grandparent = DummyAgent(name="gp", sub_agents=[parent])

        assert child.root_agent is grandparent
        assert parent.root_agent is grandparent
        assert grandparent.root_agent is grandparent

    def test_find_agent(self):
        c1 = DummyAgent(name="c1")
        c2 = DummyAgent(name="c2")
        mid = DummyAgent(name="mid", sub_agents=[c1, c2])
        root = DummyAgent(name="root", sub_agents=[mid])

        assert root.find_agent("c1") is c1
        assert root.find_agent("c2") is c2
        assert root.find_agent("mid") is mid
        assert root.find_agent("root") is root
        assert root.find_agent("nonexistent") is None

    def test_find_agent_from_child(self):
        c1 = DummyAgent(name="c1")
        root = DummyAgent(name="root", sub_agents=[c1])
        # find_agent searches from root
        assert c1.find_agent("root") is root

    def test_find_sub_agent(self):
        c1 = DummyAgent(name="c1")
        c2 = DummyAgent(name="c2")
        parent = DummyAgent(name="parent", sub_agents=[c1, c2])

        assert parent.find_sub_agent("c1") is c1
        assert parent.find_sub_agent("c2") is c2
        assert parent.find_sub_agent("parent") is None
        assert parent.find_sub_agent("nonexistent") is None

    def test_find_sub_agent_nested(self):
        deep = DummyAgent(name="deep")
        mid = DummyAgent(name="mid", sub_agents=[deep])
        root = DummyAgent(name="root", sub_agents=[mid])

        assert root.find_sub_agent("deep") is deep

    @pytest.mark.asyncio
    async def test_run_async_basic(self):
        agent = DummyAgent(name="greeter")
        # InvocationContext is needed — create a minimal one
        from soulbot.agents.invocation_context import InvocationContext
        from soulbot.sessions import Session

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=agent)

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].author == "greeter"
        assert events[0].content.parts[0].text == "Hello from greeter"

    @pytest.mark.asyncio
    async def test_before_callback_skips(self):
        def before_cb(ctx):
            return Content(role="model", parts=[Part(text="blocked")])

        agent = DummyAgent(name="agent", before_agent_callback=before_cb)

        from soulbot.agents.invocation_context import InvocationContext
        from soulbot.sessions import Session

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=agent)

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].content.parts[0].text == "blocked"

    @pytest.mark.asyncio
    async def test_before_callback_none_continues(self):
        def before_cb(ctx):
            return None  # Don't skip

        agent = DummyAgent(name="agent", before_agent_callback=before_cb)

        from soulbot.agents.invocation_context import InvocationContext
        from soulbot.sessions import Session

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=agent)

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 1
        assert events[0].content.parts[0].text == "Hello from agent"

    @pytest.mark.asyncio
    async def test_after_callback_appends(self):
        def after_cb(ctx):
            return Content(role="model", parts=[Part(text="epilogue")])

        agent = DummyAgent(name="agent", after_agent_callback=after_cb)

        from soulbot.agents.invocation_context import InvocationContext
        from soulbot.sessions import Session

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=agent)

        events = []
        async for event in agent.run_async(ctx):
            events.append(event)

        assert len(events) == 2
        assert events[0].content.parts[0].text == "Hello from agent"
        assert events[1].content.parts[0].text == "epilogue"
