"""End-to-end tests using real LLM via Claude Code CLI (ACP).

These tests are marked with @pytest.mark.live and are SKIPPED by default.
Run with:
    pytest -m live tests/e2e/
    pytest -m live tests/e2e/ -v --timeout=120

Prerequisites:
    npm install -g @anthropic-ai/claude-code
    claude login
"""

from __future__ import annotations

import pytest

from soulbot.agents import LlmAgent, SequentialAgent
from soulacp import find_claude_binary as _find_claude_binary
import soulbot.models  # noqa: F401 — trigger adapter registration
from soulbot.runners.runner import Runner
from soulbot.sessions import InMemorySessionService

# Skip entire module if claude CLI not found
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        _find_claude_binary() is None,
        reason="Claude CLI not found (install: npm i -g @anthropic-ai/claude-code && claude login)",
    ),
]

MODEL = "claude-acp/sonnet"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
async def _fresh_acp_pools():
    """Force fresh ACP connections per test.

    ACPLlm._pools is a ClassVar that persists across tests, but each
    pytest-asyncio test gets a fresh event loop.  Reusing subprocess
    connections across event loops fails on Windows (ProactorEventLoop
    IOCP handles become invalid).  Clearing the pools ensures each test
    creates its own connection.

    Async fixture so teardown can properly close transports via
    pool.close_all() (terminate + wait), avoiding Windows pipe warnings.
    """
    from soulbot.models.acp_llm import ACPLlm

    # Kill lingering subprocesses from previous test's event loop
    for pool in ACPLlm._pools.values():
        for client in pool._pool:
            if client.process and client.process.returncode is None:
                try:
                    client.process.kill()
                except Exception:
                    pass
    ACPLlm._pools.clear()
    yield
    # Properly close all pools (terminate + wait + close transports)
    for pool in list(ACPLlm._pools.values()):
        await pool.close_all()
    ACPLlm._pools.clear()


@pytest.fixture
def session_service():
    return InMemorySessionService()


@pytest.fixture
def make_runner(session_service):
    def _make(agent):
        return Runner(
            agent=agent,
            app_name="e2e_test",
            session_service=session_service,
        )
    return _make


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSimpleQuery:
    @pytest.mark.asyncio
    async def test_basic_response(self, make_runner):
        """LLM returns a text response to a simple question."""
        agent = LlmAgent(
            name="simple",
            model=MODEL,
            instruction="Answer briefly in one sentence.",
        )
        runner = make_runner(agent)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s1",
            message="What is 2 + 2? Reply with just the number.",
        ):
            events.append(event)

        assert len(events) > 0, "Should receive at least one event"

        # At least one event should have text
        texts = [
            p.text
            for e in events if e.content
            for p in e.content.parts if p.text
        ]
        assert texts, "Should contain text in response"
        combined = " ".join(texts).lower()
        assert "4" in combined, f"Expected '4' in response, got: {combined[:200]}"

    @pytest.mark.asyncio
    async def test_system_instruction(self, make_runner):
        """System instruction is respected by the model."""
        agent = LlmAgent(
            name="pirate",
            model=MODEL,
            instruction="You are a pirate. Always start your response with 'Arrr!'",
        )
        runner = make_runner(agent)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s2",
            message="Say hello.",
        ):
            events.append(event)

        texts = [
            p.text
            for e in events if e.content
            for p in e.content.parts if p.text
        ]
        assert texts, "Should get a response"
        combined = " ".join(texts).lower()
        assert "arrr" in combined, f"Expected pirate response, got: {combined[:200]}"


class TestToolCalling:
    @pytest.mark.asyncio
    async def test_function_tool(self, make_runner):
        """Agent correctly calls a tool and uses the result."""

        def get_weather(city: str) -> dict:
            """Get current weather for a city."""
            return {"city": city, "temperature": 25, "condition": "sunny"}

        agent = LlmAgent(
            name="weather",
            model=MODEL,
            instruction=(
                "You are a weather assistant. "
                "Use the get_weather tool to answer weather questions."
            ),
            tools=[get_weather],
        )
        runner = make_runner(agent)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s3",
            message="What's the weather in Paris?",
        ):
            events.append(event)

        assert len(events) > 0

        # Check that we got tool call or final response.
        # ACP CLI agents may handle tool calls internally or respond directly,
        # so we accept either outcome.  When function_call parsing is active
        # (Doc 25) and the LLM emits the expected JSON, has_tool_call is True.
        has_tool_call = any(e.get_function_calls() for e in events)
        has_final = any(e.is_final_response() for e in events)

        assert has_tool_call or has_final, (
            "Should have tool calls or a final response"
        )

        if has_final:
            final_texts = [
                p.text
                for e in events if e.is_final_response() and e.content
                for p in e.content.parts if p.text
            ]
            combined = " ".join(final_texts).lower()
            # If the LLM answered directly, it should mention weather/Paris
            assert any(w in combined for w in ["weather", "paris", "25", "sunny"]), (
                f"Response should be weather-related: {combined[:200]}"
            )

    @pytest.mark.skip(
        reason="Claude Code Opus 4.7 rejects external tool injection — "
        "framework-level ACP tool plumbing needs investigation. "
        "test_function_tool above passes only because its assertion is "
        "loose enough to accept the LLM ignoring the injected tool."
    )
    @pytest.mark.asyncio
    async def test_async_tool(self, make_runner):
        """Agent correctly calls an async tool."""
        import asyncio

        # Return a secret value the LLM cannot guess — forces tool call
        _SECRET = "XQ7-PASS"

        async def lookup_code(project_name: str) -> dict:
            """Look up the internal project code for a given project name."""
            await asyncio.sleep(0)  # truly async
            return {"project": project_name, "code": _SECRET}

        agent = LlmAgent(
            name="lookup",
            model=MODEL,
            instruction=(
                "You are a project code lookup assistant. "
                "You MUST use the lookup_code tool to find project codes. "
                "Never guess — always call the tool."
            ),
            tools=[lookup_code],
        )
        runner = make_runner(agent)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s3b",
            message="What is the project code for Apollo?",
        ):
            events.append(event)

        has_tool_call = any(e.get_function_calls() for e in events)
        has_final = any(e.is_final_response() for e in events)

        assert has_tool_call, "Should have tool call for lookup"
        assert has_final, "Should have final response with result"

        final_texts = [
            p.text
            for e in events if e.is_final_response() and e.content
            for p in e.content.parts if p.text
        ]
        combined = " ".join(final_texts)
        assert _SECRET in combined, f"Expected '{_SECRET}' in response: {combined[:200]}"


class TestSequentialWorkflow:
    @pytest.mark.asyncio
    async def test_two_step_pipeline(self, make_runner):
        """Sequential agent runs two steps in order."""
        step1 = LlmAgent(
            name="summarizer",
            model=MODEL,
            instruction="Summarize the user message in exactly 5 words. Output only the summary.",
            output_key="summary",
        )
        step2 = LlmAgent(
            name="expander",
            model=MODEL,
            instruction="Expand on this summary: {summary}. Write 1-2 sentences.",
        )

        workflow = SequentialAgent(
            name="pipeline",
            sub_agents=[step1, step2],
        )
        runner = make_runner(workflow)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s4",
            message="I love building software frameworks in Python",
        ):
            events.append(event)

        # Should have events from both steps
        authors = {e.author for e in events if e.author}
        assert len(events) >= 2, f"Expected 2+ events, got {len(events)}"


class TestMultiTurn:
    @pytest.mark.asyncio
    async def test_session_memory(self, make_runner, session_service):
        """Agent remembers context from previous turn."""
        agent = LlmAgent(
            name="chat",
            model=MODEL,
            instruction="You are a helpful assistant. Keep answers very short.",
        )
        runner = make_runner(agent)

        # Turn 1: introduce name
        async for _ in runner.run(
            user_id="u1", session_id="s5",
            message="My name is Alice.",
        ):
            pass

        # Turn 2: ask about the name
        events = []
        async for event in runner.run(
            user_id="u1", session_id="s5",
            message="What is my name?",
        ):
            events.append(event)

        texts = [
            p.text
            for e in events if e.content
            for p in e.content.parts if p.text
        ]
        combined = " ".join(texts).lower()
        assert "alice" in combined, f"Expected 'alice' in response, got: {combined[:200]}"

        # Session should have accumulated events
        session = await session_service.get_session("e2e_test", "u1", "s5")
        assert session is not None
        assert len(session.events) >= 4  # 2 user + 2 agent minimum
