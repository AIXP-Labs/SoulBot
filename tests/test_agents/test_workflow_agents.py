"""Tests for SequentialAgent, ParallelAgent, and LoopAgent."""

import pytest

from soulbot.agents import (
    BaseAgent,
    InvocationContext,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from soulbot.events.event import Content, Event, Part
from soulbot.events.event_actions import EventActions
from soulbot.sessions import InMemorySessionService, Session


# ---------------------------------------------------------------------------
# Helper: a simple agent that yields one event with its name
# ---------------------------------------------------------------------------


class StubAgent(BaseAgent):
    """Agent that yields a single event containing its name."""

    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(role="model", parts=[Part(text=f"[{self.name}]")]),
        )


class EscalatingAgent(BaseAgent):
    """Agent that yields one event then escalates."""

    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(role="model", parts=[Part(text=f"[{self.name}]")]),
            actions=EventActions(escalate=True),
        )


class CountingAgent(BaseAgent):
    """Agent that increments a counter in session state each time it runs."""

    async def _run_async_impl(self, ctx):
        count = ctx.session.state.get("count", 0)
        count += 1
        ctx.session.state["count"] = count
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(role="model", parts=[Part(text=f"count={count}")]),
        )


class ConditionalEscalateAgent(BaseAgent):
    """Escalates when count >= threshold."""

    threshold: int = 3

    async def _run_async_impl(self, ctx):
        count = ctx.session.state.get("count", 0)
        should_stop = count >= self.threshold
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(
                role="model",
                parts=[Part(text=f"check: count={count}, stop={should_stop}")],
            ),
            actions=EventActions(escalate=True) if should_stop else EventActions(),
        )


@pytest.fixture
def session():
    return Session(app_name="test", user_id="u1")


def make_ctx(session, agent):
    return InvocationContext(session=session, agent=agent)


# ---------------------------------------------------------------------------
# SequentialAgent
# ---------------------------------------------------------------------------


class TestSequentialAgent:
    @pytest.mark.asyncio
    async def test_basic_sequence(self, session):
        a1 = StubAgent(name="step1")
        a2 = StubAgent(name="step2")
        a3 = StubAgent(name="step3")
        seq = SequentialAgent(name="pipeline", sub_agents=[a1, a2, a3])
        ctx = make_ctx(session, seq)

        events = []
        async for event in seq.run_async(ctx):
            events.append(event)

        texts = [e.content.parts[0].text for e in events]
        assert texts == ["[step1]", "[step2]", "[step3]"]

    @pytest.mark.asyncio
    async def test_empty_sequence(self, session):
        seq = SequentialAgent(name="empty", sub_agents=[])
        ctx = make_ctx(session, seq)

        events = []
        async for event in seq.run_async(ctx):
            events.append(event)

        assert events == []

    @pytest.mark.asyncio
    async def test_escalate_stops_pipeline(self, session):
        a1 = StubAgent(name="step1")
        a2 = EscalatingAgent(name="stopper")
        a3 = StubAgent(name="step3")
        seq = SequentialAgent(name="pipeline", sub_agents=[a1, a2, a3])
        ctx = make_ctx(session, seq)

        events = []
        async for event in seq.run_async(ctx):
            events.append(event)

        # step3 should NOT have run
        authors = [e.author for e in events]
        assert "step1" in authors
        assert "stopper" in authors
        assert "step3" not in authors

    @pytest.mark.asyncio
    async def test_shared_state(self, session):
        """Sub-agents share session state."""
        counter = CountingAgent(name="counter")
        seq = SequentialAgent(name="seq", sub_agents=[counter, counter, counter])
        ctx = make_ctx(session, seq)

        events = []
        async for event in seq.run_async(ctx):
            events.append(event)

        texts = [e.content.parts[0].text for e in events]
        assert texts == ["count=1", "count=2", "count=3"]
        assert session.state["count"] == 3


# ---------------------------------------------------------------------------
# ParallelAgent
# ---------------------------------------------------------------------------


class TestParallelAgent:
    @pytest.mark.asyncio
    async def test_basic_parallel(self, session):
        a1 = StubAgent(name="worker1")
        a2 = StubAgent(name="worker2")
        a3 = StubAgent(name="worker3")
        par = ParallelAgent(name="parallel", sub_agents=[a1, a2, a3])
        ctx = make_ctx(session, par)

        events = []
        async for event in par.run_async(ctx):
            events.append(event)

        authors = {e.author for e in events}
        assert authors == {"worker1", "worker2", "worker3"}

    @pytest.mark.asyncio
    async def test_branch_isolation(self, session):
        """Each sub-agent should get a unique branch."""
        a1 = StubAgent(name="w1")
        a2 = StubAgent(name="w2")
        par = ParallelAgent(name="par", sub_agents=[a1, a2])
        ctx = make_ctx(session, par)

        events = []
        async for event in par.run_async(ctx):
            events.append(event)

        branches = {e.branch for e in events}
        assert "par.w1" in branches
        assert "par.w2" in branches

    @pytest.mark.asyncio
    async def test_empty_parallel(self, session):
        par = ParallelAgent(name="empty", sub_agents=[])
        ctx = make_ctx(session, par)

        events = []
        async for event in par.run_async(ctx):
            events.append(event)

        assert events == []

    @pytest.mark.asyncio
    async def test_error_in_sub_agent(self, session):
        """If a sub-agent raises, other agents should still run."""

        class FailingAgent(BaseAgent):
            async def _run_async_impl(self, ctx):
                raise RuntimeError("boom")
                yield  # pragma: no cover

        good = StubAgent(name="good")
        bad = FailingAgent(name="bad")
        par = ParallelAgent(name="par", sub_agents=[good, bad])
        ctx = make_ctx(session, par)

        events = []
        async for event in par.run_async(ctx):
            events.append(event)

        # Should have good agent's event + error event for bad agent
        assert any(e.author == "good" for e in events)
        assert any(e.error_code == "PARALLEL_ERROR" for e in events)


# ---------------------------------------------------------------------------
# LoopAgent
# ---------------------------------------------------------------------------


class TestLoopAgent:
    @pytest.mark.asyncio
    async def test_basic_loop(self, session):
        counter = CountingAgent(name="counter")
        checker = ConditionalEscalateAgent(name="checker", threshold=3)
        loop = LoopAgent(
            name="loop", sub_agents=[counter, checker], max_iterations=10
        )
        ctx = make_ctx(session, loop)

        events = []
        async for event in loop.run_async(ctx):
            events.append(event)

        # Should run 3 iterations: count goes 1→2→3, then checker escalates
        assert session.state["count"] == 3
        assert any(e.actions and e.actions.escalate for e in events)

    @pytest.mark.asyncio
    async def test_max_iterations(self, session):
        counter = CountingAgent(name="counter")
        loop = LoopAgent(name="loop", sub_agents=[counter], max_iterations=5)
        ctx = make_ctx(session, loop)

        events = []
        async for event in loop.run_async(ctx):
            events.append(event)

        assert session.state["count"] == 5
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_immediate_escalate(self, session):
        escalator = EscalatingAgent(name="stop")
        after = StubAgent(name="never")
        loop = LoopAgent(name="loop", sub_agents=[escalator, after], max_iterations=5)
        ctx = make_ctx(session, loop)

        events = []
        async for event in loop.run_async(ctx):
            events.append(event)

        # Should stop after first sub-agent escalates
        assert len(events) == 1
        assert events[0].author == "stop"

    @pytest.mark.asyncio
    async def test_empty_loop(self, session):
        loop = LoopAgent(name="loop", sub_agents=[], max_iterations=3)
        ctx = make_ctx(session, loop)

        events = []
        async for event in loop.run_async(ctx):
            events.append(event)

        assert events == []
