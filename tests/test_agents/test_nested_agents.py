"""Tests for nested/composite agent scenarios."""

import pytest

from soulbot.agents import (
    BaseAgent,
    InvocationContext,
    LlmAgent,
    LoopAgent,
    ParallelAgent,
    SequentialAgent,
)
from soulbot.events.event import Content, Event, Part
from soulbot.events.event_actions import EventActions
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService, Session


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class MockLlm(BaseLlm):
    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls):
        return [r"mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"mock-.*", MockLlm)
    yield
    ModelRegistry.reset()


@pytest.fixture
def service():
    return InMemorySessionService()


# ---------------------------------------------------------------------------
# Stub agents
# ---------------------------------------------------------------------------


class StubAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(role="model", parts=[Part(text=f"[{self.name}]")]),
        )


class StateWriterAgent(BaseAgent):
    """Writes a value to session state."""

    key: str = "result"
    value: str = ""

    async def _run_async_impl(self, ctx):
        ctx.session.state[self.key] = self.value
        yield Event(
            author=self.name,
            invocation_id=ctx.invocation_id,
            branch=ctx.branch,
            content=Content(role="model", parts=[Part(text=f"wrote {self.key}={self.value}")]),
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSequentialWithLlmAgent:
    @pytest.mark.asyncio
    async def test_llm_agent_in_sequence(self, service):
        """LlmAgent mixed with stub agents in a SequentialAgent."""
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="LLM says hello")])),
        ])

        stub_before = StubAgent(name="pre_step")
        llm_step = LlmAgent(name="llm_step", model="mock-v1", instruction="Say hello")
        stub_after = StubAgent(name="post_step")

        pipeline = SequentialAgent(
            name="pipeline", sub_agents=[stub_before, llm_step, stub_after]
        )
        runner = Runner(agent=pipeline, app_name="test", session_service=service)

        events = []
        async for event in runner.run(user_id="u1", session_id="s1", message="Go"):
            events.append(event)

        non_partial = [e for e in events if not e.partial]
        authors = [e.author for e in non_partial if e.content]
        assert "pre_step" in authors
        assert "llm_step" in authors
        assert "post_step" in authors


class TestSequentialStateSharing:
    @pytest.mark.asyncio
    async def test_state_flows_through_pipeline(self, service):
        """State set by one agent is visible to the next."""
        MockLlm.set_responses([
            LlmResponse(
                content=Content(role="model", parts=[Part(text="LLM response")])
            ),
        ])

        writer = StateWriterAgent(name="writer", key="topic", value="AI")
        llm_step = LlmAgent(
            name="reader",
            model="mock-v1",
            instruction="The topic is {topic}",
        )

        pipeline = SequentialAgent(name="pipe", sub_agents=[writer, llm_step])
        runner = Runner(agent=pipeline, app_name="test", session_service=service)

        async for _ in runner.run(user_id="u1", session_id="s1", message="Start"):
            pass

        session = await service.get_session("test", "u1", "s1")
        assert session.state["topic"] == "AI"


class TestParallelInSequential:
    @pytest.mark.asyncio
    async def test_parallel_inside_sequential(self):
        """Parallel agents inside a sequential pipeline."""
        w1 = StubAgent(name="search_web")
        w2 = StubAgent(name="search_db")

        parallel_search = ParallelAgent(name="search", sub_agents=[w1, w2])
        summarizer = StubAgent(name="summarize")

        pipeline = SequentialAgent(
            name="pipeline", sub_agents=[parallel_search, summarizer]
        )

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=pipeline)

        events = []
        async for event in pipeline.run_async(ctx):
            events.append(event)

        authors = [e.author for e in events if e.content]
        assert "search_web" in authors
        assert "search_db" in authors
        assert "summarize" in authors
        # Summarize should come after both search agents
        summarize_idx = next(
            i for i, e in enumerate(events) if e.author == "summarize"
        )
        search_indices = [
            i
            for i, e in enumerate(events)
            if e.author in ("search_web", "search_db")
        ]
        assert all(si < summarize_idx for si in search_indices)


class TestLoopWithSequential:
    @pytest.mark.asyncio
    async def test_loop_of_sequential_agents(self):
        """Loop containing a sequential pipeline."""

        class IncrementAgent(BaseAgent):
            async def _run_async_impl(self, ctx):
                count = ctx.session.state.get("n", 0)
                ctx.session.state["n"] = count + 1
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=Content(
                        role="model", parts=[Part(text=f"n={count + 1}")]
                    ),
                )

        class CheckDone(BaseAgent):
            async def _run_async_impl(self, ctx):
                n = ctx.session.state.get("n", 0)
                yield Event(
                    author=self.name,
                    invocation_id=ctx.invocation_id,
                    content=Content(role="model", parts=[Part(text=f"check n={n}")]),
                    actions=EventActions(escalate=True) if n >= 3 else EventActions(),
                )

        inc = IncrementAgent(name="increment")
        check = CheckDone(name="check")
        loop = LoopAgent(name="loop", sub_agents=[inc, check], max_iterations=10)

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=loop)

        events = []
        async for event in loop.run_async(ctx):
            events.append(event)

        assert session.state["n"] == 3
        # Should have 3 increments + 3 checks = 6 events
        assert len(events) == 6


class TestDeepNesting:
    @pytest.mark.asyncio
    async def test_three_level_nesting(self):
        """Agents nested 3 levels deep."""
        inner1 = StubAgent(name="inner1")
        inner2 = StubAgent(name="inner2")
        parallel = ParallelAgent(name="par", sub_agents=[inner1, inner2])

        final = StubAgent(name="final")
        mid_seq = SequentialAgent(name="mid", sub_agents=[parallel, final])

        outer_loop = LoopAgent(name="outer", sub_agents=[mid_seq], max_iterations=2)

        session = Session(app_name="test", user_id="u1")
        ctx = InvocationContext(session=session, agent=outer_loop)

        events = []
        async for event in outer_loop.run_async(ctx):
            events.append(event)

        # 2 iterations × (2 parallel + 1 final) = 6 events
        assert len(events) == 6
        content_authors = [e.author for e in events if e.content]
        assert content_authors.count("inner1") == 2
        assert content_authors.count("inner2") == 2
        assert content_authors.count("final") == 2
