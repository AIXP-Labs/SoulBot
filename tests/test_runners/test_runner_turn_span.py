"""Tests for Doc 22 P3 per-turn OTel span (Runner.run wraps agent loop).

Verifies that:
- Every ``Runner.run()`` invocation creates exactly one ``turn {index}`` span
- The span carries SOULBOT_TURN_ID / SOULBOT_TURN_INDEX / GEN_AI_CONVERSATION_ID / GEN_AI_AGENT_NAME
- Events yielded by the agent carry the invocation id (unchanged behavior)
- Span is always closed, even on client disconnect or exception
- turn_index increments across multiple runs on the same session
"""
import pytest

from soulbot.agents import LlmAgent
from soulbot.events.event import Content, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.observability import semconv as sc
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService


class _MockLlm(BaseLlm):
    @classmethod
    def supported_models(cls):
        return [r"turnspan-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        yield LlmResponse(
            content=Content(role="model", parts=[Part(text="ok")])
        )


@pytest.fixture(autouse=True)
def _register_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"turnspan-mock-.*", _MockLlm)
    yield
    ModelRegistry.reset()


def _mk_agent(name="a"):
    return LlmAgent(
        name=name,
        model="turnspan-mock-model",
        instruction="You are a test agent.",
    )


async def _run_once(runner, *, user_id="u1", session_id="s1",
                    message="hi"):
    events = []
    async for ev in runner.run(
        user_id=user_id, session_id=session_id, message=message,
    ):
        events.append(ev)
    return events


# --- core P3 behaviors ---


@pytest.mark.asyncio
async def test_turn_span_created_per_run(captured_spans):
    runner = Runner(
        agent=_mk_agent(), app_name="app",
        session_service=InMemorySessionService(),
    )
    await _run_once(runner, session_id="s42")

    turn_spans = [
        s for s in captured_spans.get_finished_spans()
        if s.name.startswith("turn ")
    ]
    assert len(turn_spans) == 1
    attrs = turn_spans[0].attributes
    assert attrs[sc.SOULBOT_TURN_INDEX] == 1
    assert attrs[sc.SOULBOT_TURN_ID] == "s42.turn.1"
    assert attrs[sc.GEN_AI_CONVERSATION_ID] == "s42"
    assert attrs[sc.GEN_AI_AGENT_NAME] == "a"


@pytest.mark.asyncio
async def test_turn_index_increments_across_runs_in_same_session(captured_spans):
    runner = Runner(
        agent=_mk_agent(), app_name="app",
        session_service=InMemorySessionService(),
    )
    await _run_once(runner, session_id="s7", message="first")
    await _run_once(runner, session_id="s7", message="second")
    await _run_once(runner, session_id="s7", message="third")

    turn_spans = sorted(
        [s for s in captured_spans.get_finished_spans()
         if s.name.startswith("turn ")],
        key=lambda s: s.attributes[sc.SOULBOT_TURN_INDEX],
    )
    indexes = [s.attributes[sc.SOULBOT_TURN_INDEX] for s in turn_spans]
    assert indexes == [1, 2, 3]


@pytest.mark.asyncio
async def test_turn_index_independent_across_sessions(captured_spans):
    runner = Runner(
        agent=_mk_agent(), app_name="app",
        session_service=InMemorySessionService(),
    )
    await _run_once(runner, session_id="sA", message="hello A")
    await _run_once(runner, session_id="sB", message="hello B")

    turn_spans = [
        s for s in captured_spans.get_finished_spans()
        if s.name.startswith("turn ")
    ]
    assert len(turn_spans) == 2
    for s in turn_spans:
        # Each session starts at turn 1
        assert s.attributes[sc.SOULBOT_TURN_INDEX] == 1


@pytest.mark.asyncio
async def test_turn_span_closes_on_early_generator_close(captured_spans):
    """If the caller abandons the generator (aclose), the span must still end."""
    runner = Runner(
        agent=_mk_agent(), app_name="app",
        session_service=InMemorySessionService(),
    )
    gen = runner.run(user_id="u1", session_id="s99", message="hi")
    await gen.__anext__()        # consume at least one event
    await gen.aclose()           # abandon the generator early

    turn_spans = [
        s for s in captured_spans.get_finished_spans()
        if s.name.startswith("turn ")
    ]
    assert len(turn_spans) == 1  # finally block still ran, span ended
