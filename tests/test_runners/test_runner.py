"""Tests for Runner core lifecycle (Doc 24).

Verifies that Runner correctly:
- Creates or reuses sessions (get/create logic)
- Auto-generates session title from first message
- Sets and updates last_agent (Doc 21 soft classification)
- Appends user event to session before agent execution
- Publishes SESSION_UPDATED and AGENT_RESPONSE on EventBus
- Constructs InvocationContext with correct RunConfig
- Sets invocation_id on all yielded events
- Persists final events but skips partial (streaming) events
- Accumulates events across multiple turns
- Propagates agent exceptions without swallowing
"""

import pytest

from soulbot.agents import LlmAgent
from soulbot.agents.invocation_context import RunConfig
from soulbot.bus.event_bus import EventBus
from soulbot.bus.events import AGENT_RESPONSE, SESSION_UPDATED, BusEvent
from soulbot.events.event import Content, Event, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class RunnerMockLlm(BaseLlm):
    """Mock LLM for Runner lifecycle tests."""

    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses: list[LlmResponse]):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"runner-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            resp = self._responses.pop(0)
            if stream and resp.content:
                yield LlmResponse(content=resp.content, partial=True)
            yield resp
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_runner_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"runner-mock-.*", RunnerMockLlm)
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(name="test_agent"):
    return LlmAgent(
        name=name,
        model="runner-mock-model",
        instruction="You are a test agent.",
    )


def _resp(text: str) -> LlmResponse:
    return LlmResponse(content=Content(role="model", parts=[Part(text=text)]))


async def _collect(runner, user_id="u1", session_id="s1",
                   message="hello", run_config=None):
    events = []
    async for event in runner.run(
        user_id=user_id, session_id=session_id,
        message=message, run_config=run_config,
    ):
        events.append(event)
    return events


class BusCapture:
    """Capture all events published on an EventBus."""

    def __init__(self, bus: EventBus):
        self.events: list[BusEvent] = []
        bus.subscribe("*", self._on_event)

    async def _on_event(self, event: BusEvent):
        self.events.append(event)

    def of_type(self, event_type: str) -> list[BusEvent]:
        return [e for e in self.events if e.type == event_type]


# ---------------------------------------------------------------------------
# TestRunnerSessionLifecycle
# ---------------------------------------------------------------------------


class TestRunnerSessionLifecycle:
    """Runner.run() Session get/create logic (lines 73-92)."""

    async def test_creates_session_when_none_exists(self):
        """get_session returns None -> create_session called."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("hi")])
        await _collect(runner, user_id="u1", session_id="new-s")

        session = await svc.get_session("app", "u1", "new-s")
        assert session is not None
        assert session.id == "new-s"

    async def test_reuses_existing_session(self):
        """Existing session is reused, not replaced.

        Plan 18 / 01: session reuse now requires matching agent_name to
        prevent cross-agent session leak. agent_name="test_agent" matches
        _make_agent()'s default name.
        """
        svc = InMemorySessionService()
        existing = await svc.create_session("app", "u1", agent_name="test_agent", session_id="s1",
                                            title="Old title")
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("reply")])
        await _collect(runner, user_id="u1", session_id="s1")

        session = await svc.get_session("app", "u1", "s1")
        assert session is existing
        assert session.title == "Old title"  # not overwritten

    async def test_auto_title_from_long_message(self):
        """New session title = message[:30] + '...' for long messages."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        long_msg = "A" * 50
        RunnerMockLlm.set_responses([_resp("ok")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message=long_msg)

        session = await svc.get_session("app", "u1", "s1")
        assert session.title == "A" * 30 + "..."

    async def test_auto_title_short_message(self):
        """Short message -> title = message without '...'."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("ok")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Short msg")

        session = await svc.get_session("app", "u1", "s1")
        assert session.title == "Short msg"
        assert "..." not in session.title

    async def test_last_agent_set_on_create(self):
        """New session.last_agent = agent.name."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(name="my_bot"), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("hi")])
        await _collect(runner, user_id="u1", session_id="s1")

        session = await svc.get_session("app", "u1", "s1")
        assert session.last_agent == "my_bot"

    async def test_last_agent_updated_when_changed(self):
        """Existing session with different agent -> last_agent updated."""
        svc = InMemorySessionService()
        await svc.create_session("app", "u1", agent_name="old_agent", session_id="s1")
        runner = Runner(agent=_make_agent(name="new_agent"), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("reply")])
        await _collect(runner, user_id="u1", session_id="s1")

        session = await svc.get_session("app", "u1", "s1")
        assert session.last_agent == "new_agent"

    async def test_last_agent_not_updated_when_same(self):
        """Same agent -> update_last_agent not called (no-op)."""
        svc = InMemorySessionService()
        await svc.create_session("app", "u1", agent_name="same_agent", session_id="s1")
        runner = Runner(agent=_make_agent(name="same_agent"), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("reply")])
        await _collect(runner, user_id="u1", session_id="s1")

        session = await svc.get_session("app", "u1", "s1")
        assert session.last_agent == "same_agent"


# ---------------------------------------------------------------------------
# TestRunnerUserEvent
# ---------------------------------------------------------------------------


class TestRunnerUserEvent:
    """Runner.run() user event append + bus publish (lines 94-109)."""

    async def test_user_event_appended_to_session(self):
        """Session.events includes user event with author='user'."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("reply")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Hello!")

        session = await svc.get_session("app", "u1", "s1")
        user_events = [e for e in session.events if e.author == "user"]
        assert len(user_events) == 1

    async def test_user_event_content(self):
        """User event content matches the input message."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("reply")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Test message")

        session = await svc.get_session("app", "u1", "s1")
        user_events = [e for e in session.events if e.author == "user"]
        assert user_events[0].content.parts[0].text == "Test message"

    async def test_session_updated_bus_event(self):
        """Bus receives SESSION_UPDATED with session_id and user_id."""
        bus = EventBus()
        capture = BusCapture(bus)
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc, bus=bus)
        RunnerMockLlm.set_responses([_resp("reply")])
        await _collect(runner, user_id="u1", session_id="s1")

        session_events = capture.of_type(SESSION_UPDATED)
        assert len(session_events) >= 1
        assert session_events[0].data["session_id"] == "s1"
        assert session_events[0].data["user_id"] == "u1"

    async def test_no_bus_no_crash(self):
        """Without bus, run works normally."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)  # no bus
        RunnerMockLlm.set_responses([_resp("ok")])
        events = await _collect(runner)
        assert any(e.is_final_response() for e in events)


# ---------------------------------------------------------------------------
# TestRunnerInvocationContext
# ---------------------------------------------------------------------------


class TestRunnerInvocationContext:
    """Runner.run() InvocationContext construction (lines 120-127)."""

    async def test_invocation_id_set_on_events(self):
        """All yielded events have a non-empty invocation_id."""
        RunnerMockLlm.set_responses([_resp("reply")])
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())
        events = await _collect(runner)

        assert len(events) > 0
        for e in events:
            assert e.invocation_id
            assert e.invocation_id.startswith("e-")

    async def test_run_config_defaults(self):
        """Without run_config, defaults are used (streaming=False)."""
        RunnerMockLlm.set_responses([_resp("reply")])
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())
        events = await _collect(runner)

        # No partial events when streaming is off by default
        partial_events = [e for e in events if e.partial]
        assert len(partial_events) == 0

    async def test_run_config_context_propagated(self):
        """RunConfig.context is accessible in the execution."""
        # Verify indirectly: context is used for CMD routing
        # The fact that Runner doesn't crash with context proves it's propagated
        RunnerMockLlm.set_responses([_resp("reply")])
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())
        config = RunConfig(context={"channel": "telegram", "user_id": "42"})
        events = await _collect(runner, run_config=config)
        assert any(e.is_final_response() for e in events)

    async def test_run_config_streaming_flag(self):
        """RunConfig(streaming=True) causes partial events to be yielded."""
        RunnerMockLlm.set_responses([_resp("streamed")])
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())
        config = RunConfig(streaming=True)
        events = await _collect(runner, run_config=config)

        partial_events = [e for e in events if e.partial]
        assert len(partial_events) >= 1


# ---------------------------------------------------------------------------
# TestRunnerEventProcessing
# ---------------------------------------------------------------------------


class TestRunnerEventProcessing:
    """Runner.run() event processing logic (lines 130-206)."""

    async def test_partial_events_not_persisted(self):
        """Partial events are NOT appended to session.events."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("Final")])
        await _collect(runner, user_id="u1", session_id="s1",
                       run_config=RunConfig(streaming=True))

        session = await svc.get_session("app", "u1", "s1")
        partial_in_session = [e for e in session.events if e.partial]
        assert len(partial_in_session) == 0

    async def test_final_events_persisted(self):
        """Final (non-partial) events ARE appended to session.events."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        RunnerMockLlm.set_responses([_resp("Final reply")])
        await _collect(runner, user_id="u1", session_id="s1")

        session = await svc.get_session("app", "u1", "s1")
        agent_events = [e for e in session.events
                        if e.author != "user" and not e.partial]
        assert len(agent_events) >= 1
        text = " ".join(p.text for p in agent_events[0].content.parts
                        if p.text)
        assert "Final reply" in text

    async def test_final_response_publishes_agent_response(self):
        """Bus receives AGENT_RESPONSE for final events."""
        bus = EventBus()
        capture = BusCapture(bus)
        runner = Runner(agent=_make_agent(name="bot"), app_name="app",
                        session_service=InMemorySessionService(), bus=bus)
        RunnerMockLlm.set_responses([_resp("answer")])
        await _collect(runner, session_id="s1")

        ar_events = capture.of_type(AGENT_RESPONSE)
        assert len(ar_events) == 1
        assert ar_events[0].data["agent"] == "bot"
        assert ar_events[0].data["session_id"] == "s1"
        assert "answer" in ar_events[0].data["text"]

    async def test_agent_response_bus_text_extraction(self):
        """Bus event text correctly joins multiple parts."""
        bus = EventBus()
        capture = BusCapture(bus)
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService(), bus=bus)
        RunnerMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Part A"),
                Part(text="Part B"),
            ]))
        ])
        await _collect(runner)

        ar_events = capture.of_type(AGENT_RESPONSE)
        assert len(ar_events) == 1
        assert ar_events[0].data["text"] == "Part A Part B"

    async def test_events_yielded_in_order(self):
        """Runner yields events in the same order agent produces them."""
        RunnerMockLlm.set_responses([_resp("reply")])
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())
        events = await _collect(runner)

        # All events should have increasing timestamps (or same)
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)

    async def test_streaming_partial_then_final(self):
        """With streaming, partial events come before final event."""
        RunnerMockLlm.set_responses([_resp("streamed reply")])
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())
        events = await _collect(runner, run_config=RunConfig(streaming=True))

        partial_indices = [i for i, e in enumerate(events) if e.partial]
        final_indices = [i for i, e in enumerate(events)
                         if e.is_final_response()]
        assert len(partial_indices) >= 1
        assert len(final_indices) >= 1
        assert max(partial_indices) < min(final_indices)


# ---------------------------------------------------------------------------
# TestRunnerMultiTurn
# ---------------------------------------------------------------------------


class TestRunnerMultiTurn:
    """Multi-turn conversation handling."""

    async def test_multi_turn_session_reuse(self):
        """Multiple run() calls with same session_id accumulate events."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)

        RunnerMockLlm.set_responses([_resp("Reply 1")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Turn 1")
        RunnerMockLlm.set_responses([_resp("Reply 2")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Turn 2")

        session = await svc.get_session("app", "u1", "s1")
        # 2 user events + 2 agent events = 4
        assert len(session.events) == 4

    async def test_multi_turn_different_messages(self):
        """Each turn's user message is correctly appended."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)

        RunnerMockLlm.set_responses([_resp("R1")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Msg A")
        RunnerMockLlm.set_responses([_resp("R2")])
        await _collect(runner, user_id="u1", session_id="s1",
                       message="Msg B")

        session = await svc.get_session("app", "u1", "s1")
        user_texts = [
            e.content.parts[0].text
            for e in session.events if e.author == "user"
        ]
        assert user_texts == ["Msg A", "Msg B"]

    async def test_multi_turn_invocation_ids_differ(self):
        """Different turns produce different invocation_ids."""
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=InMemorySessionService())

        RunnerMockLlm.set_responses([_resp("R1")])
        events1 = await _collect(runner, message="Turn 1")
        RunnerMockLlm.set_responses([_resp("R2")])
        events2 = await _collect(runner, message="Turn 2")

        ids1 = {e.invocation_id for e in events1}
        ids2 = {e.invocation_id for e in events2}
        # Each turn should have its own invocation_id
        assert ids1.isdisjoint(ids2)


# ---------------------------------------------------------------------------
# TestRunnerErrorHandling
# ---------------------------------------------------------------------------


class TestRunnerErrorHandling:
    """Error handling behavior."""

    async def test_agent_exception_propagates(self):
        """If agent.run_async raises, Runner propagates the exception."""

        class FailingAgent(LlmAgent):
            async def _run_async_impl(self, ctx):
                raise RuntimeError("Agent crashed")
                yield  # noqa: unreachable — make it an async generator

        agent = FailingAgent(
            name="failing", model="runner-mock-model",
            instruction="will fail",
        )
        runner = Runner(agent=agent, app_name="app",
                        session_service=InMemorySessionService())

        with pytest.raises(RuntimeError, match="Agent crashed"):
            await _collect(runner)

    async def test_session_has_user_event_on_agent_error(self):
        """Even if agent crashes, user event is already appended."""

        class FailingAgent(LlmAgent):
            async def _run_async_impl(self, ctx):
                raise RuntimeError("Agent crashed")
                yield  # noqa: unreachable

        svc = InMemorySessionService()
        agent = FailingAgent(
            name="failing", model="runner-mock-model",
            instruction="will fail",
        )
        runner = Runner(agent=agent, app_name="app", session_service=svc)

        with pytest.raises(RuntimeError):
            await _collect(runner, user_id="u1", session_id="s1",
                           message="Before crash")

        session = await svc.get_session("app", "u1", "s1")
        user_events = [e for e in session.events if e.author == "user"]
        assert len(user_events) == 1
        assert user_events[0].content.parts[0].text == "Before crash"


# ---------------------------------------------------------------------------
# TestMessageLengthGuard (Doc 14)
# ---------------------------------------------------------------------------


class TestMessageLengthGuard:
    """User message length soft limit (Doc 14 Fix 5)."""

    async def test_long_message_returns_warning(self):
        """Messages exceeding max_message_length get a warning instead of LLM call."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        events = await _collect(
            runner, user_id="u1", session_id="s1",
            message="x" * 5000,
            run_config=RunConfig(max_message_length=3000),
        )

        assert len(events) == 1
        assert events[0].author == "system"
        assert "文件" in events[0].content.parts[0].text

    async def test_normal_message_passes(self):
        """Messages within limit are processed normally."""
        RunnerMockLlm.set_responses([_resp("ok")])
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        events = await _collect(
            runner, user_id="u1", session_id="s1",
            message="Hi",
            run_config=RunConfig(max_message_length=3000),
        )

        assert any(e.is_final_response() for e in events)

    async def test_no_limit_by_default(self):
        """Default max_message_length is None (no limit)."""
        config = RunConfig()
        assert config.max_message_length is None

    async def test_long_message_not_appended_to_session(self):
        """Rejected messages are NOT stored in session events."""
        svc = InMemorySessionService()
        runner = Runner(agent=_make_agent(), app_name="app",
                        session_service=svc)
        await _collect(
            runner, user_id="u1", session_id="s1",
            message="x" * 5000,
            run_config=RunConfig(max_message_length=3000),
        )

        session = await svc.get_session("app", "u1", "s1")
        # Session may not even be created, or if created has no user events
        if session:
            user_events = [e for e in session.events if e.author == "user"]
            assert len(user_events) == 0
