"""Tests for Runner history integration (Doc 22) and LlmRequest metadata (Doc 19).

Verifies that Runner correctly:
- Records user messages to history_service
- Records assistant responses to history_service
- Handles None history_service gracefully (backward compatibility)
- Handles history_service failures without crashing
- Preserves LlmRequest.metadata with user_id
- ACPLlm.set_provider_session_store still works
"""

import pytest

from soulbot.agents import LlmAgent
from soulbot.agents.invocation_context import RunConfig
from soulbot.events.event import Content, Part
from soulbot.history import InMemoryChatHistoryService
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmRequest, LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class ConvMockLlm(BaseLlm):
    """Mock LLM that returns pre-configured responses."""

    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses: list[LlmResponse]):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"conv-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            resp = self._responses.pop(0)
            if stream and resp.content:
                yield LlmResponse(content=resp.content, partial=True)
            yield resp
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default reply")])
            )


@pytest.fixture(autouse=True)
def setup_conv_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"conv-mock-.*", ConvMockLlm)
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(name="test_agent"):
    return LlmAgent(
        name=name,
        model="conv-mock-model",
        instruction="You are a test agent.",
    )


def _resp(text: str) -> LlmResponse:
    return LlmResponse(content=Content(role="model", parts=[Part(text=text)]))


async def _collect_events(runner, user_id="u1", session_id="s1",
                          message="hello", run_config=None):
    events = []
    async for event in runner.run(
        user_id=user_id, session_id=session_id,
        message=message, run_config=run_config,
    ):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# TestRunnerHistoryService
# ---------------------------------------------------------------------------


class TestRunnerHistoryService:
    """Runner records messages to history_service (Doc 22)."""

    async def test_user_message_recorded(self):
        ConvMockLlm.set_responses([_resp("Hello back!")])
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        await _collect_events(runner, user_id="u1", message="Hi")

        count = await history.count("u1")
        assert count == 2  # user + assistant
        msgs = await history.get_session_history("s1")
        assert msgs[0].role == "user"
        assert msgs[0].content == "Hi"

    async def test_assistant_message_recorded(self):
        ConvMockLlm.set_responses([_resp("Hello back!")])
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        await _collect_events(runner, user_id="u1", message="Hi")

        msgs = await history.get_session_history("s1")
        assert msgs[1].role == "assistant"
        assert msgs[1].content == "Hello back!"

    async def test_agent_name_recorded(self):
        ConvMockLlm.set_responses([_resp("reply")])
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(name="my_agent"), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        await _collect_events(runner, user_id="u1", message="test")

        msgs = await history.get_session_history("s1")
        assert msgs[0].agent == "my_agent"
        assert msgs[1].agent == "my_agent"

    async def test_session_id_recorded(self):
        ConvMockLlm.set_responses([_resp("reply")])
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        await _collect_events(runner, user_id="u1", session_id="sess-42", message="test")

        msgs = await history.get_session_history("sess-42")
        assert len(msgs) == 2
        assert all(m.session_id == "sess-42" for m in msgs)

    async def test_multiple_turns_accumulated(self):
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        ConvMockLlm.set_responses([_resp("Reply 1")])
        await _collect_events(runner, user_id="u1", message="Msg 1")
        ConvMockLlm.set_responses([_resp("Reply 2")])
        await _collect_events(runner, user_id="u1", message="Msg 2")

        count = await history.count("u1")
        assert count == 4  # 2 turns * 2 messages each

    async def test_user_isolation(self):
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        ConvMockLlm.set_responses([_resp("For Alice")])
        await _collect_events(runner, user_id="alice", session_id="s-alice",
                              message="From Alice")
        ConvMockLlm.set_responses([_resp("For Bob")])
        await _collect_events(runner, user_id="bob", session_id="s-bob",
                              message="From Bob")

        alice_count = await history.count("alice")
        bob_count = await history.count("bob")
        assert alice_count == 2
        assert bob_count == 2

    async def test_no_history_service_passthrough(self):
        """Without history_service, run works normally."""
        ConvMockLlm.set_responses([_resp("Normal reply")])
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
        )
        events = await _collect_events(runner)
        final = [e for e in events if e.is_final_response()]
        assert len(final) == 1

    async def test_history_failure_does_not_crash(self):
        """If history_service raises, run still completes."""

        class FailingHistory:
            async def add_message(self, *a, **kw):
                raise RuntimeError("History crashed")

        ConvMockLlm.set_responses([_resp("Still works")])
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=FailingHistory(),
        )
        events = await _collect_events(runner)
        final = [e for e in events if e.is_final_response()]
        assert len(final) == 1
        text = " ".join(p.text for p in final[0].content.parts if p.text)
        assert text == "Still works"

    async def test_partial_events_not_recorded_as_assistant(self):
        """Streaming partial events should not create extra assistant records."""
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        ConvMockLlm.set_responses([_resp("Final only")])
        await _collect_events(runner, user_id="u1",
                              message="test streaming",
                              run_config=RunConfig(streaming=True))

        msgs = await history.get_session_history("s1")
        assistant_msgs = [m for m in msgs if m.role == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0].content == "Final only"

    async def test_history_with_streaming(self):
        """Streaming mode records only the final response."""
        history = InMemoryChatHistoryService()
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            history_service=history,
        )
        ConvMockLlm.set_responses([_resp("Complete response")])
        await _collect_events(
            runner, user_id="u1", message="stream test",
            run_config=RunConfig(streaming=True),
        )

        msgs = await history.get_session_history("s1")
        assert len(msgs) == 2
        assert msgs[1].content == "Complete response"

    async def test_different_agents_isolated_in_history(self):
        """Different agents record under different agent names."""
        history = InMemoryChatHistoryService()
        svc = InMemorySessionService()

        runner_a = Runner(
            agent=_make_agent(name="agent_a"), app_name="test",
            session_service=svc, history_service=history,
        )
        runner_b = Runner(
            agent=_make_agent(name="agent_b"), app_name="test",
            session_service=svc, history_service=history,
        )

        ConvMockLlm.set_responses([_resp("From A")])
        await _collect_events(runner_a, user_id="u1", session_id="sa", message="to A")
        ConvMockLlm.set_responses([_resp("From B")])
        await _collect_events(runner_b, user_id="u1", session_id="sb", message="to B")

        a_msgs = await history.get_agent_history("u1", "agent_a")
        b_msgs = await history.get_agent_history("u1", "agent_b")
        assert len(a_msgs) == 2
        assert len(b_msgs) == 2

    async def test_history_coexists_with_bus(self):
        from soulbot.bus.event_bus import EventBus

        history = InMemoryChatHistoryService()
        bus = EventBus()
        ConvMockLlm.set_responses([_resp("With bus")])
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            bus=bus,
            history_service=history,
        )
        events = await _collect_events(runner, user_id="u1", message="test")
        assert any(e.is_final_response() for e in events)
        assert await history.count("u1") == 2

    async def test_history_coexists_with_cmd_executor(self):
        from soulbot.commands.executor import CommandExecutor

        history = InMemoryChatHistoryService()
        executor = CommandExecutor()
        ConvMockLlm.set_responses([_resp("With both")])
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            cmd_executor=executor,
            history_service=history,
        )
        events = await _collect_events(runner, user_id="u1", message="test")
        assert any(e.is_final_response() for e in events)
        assert await history.count("u1") == 2


# ---------------------------------------------------------------------------
# TestRunnerBackwardCompat
# ---------------------------------------------------------------------------


class TestRunnerBackwardCompat:
    """Backward compatibility — Runner without history_service behaves identically."""

    async def test_default_none_history(self):
        ConvMockLlm.set_responses([_resp("Reply")])
        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
        )
        assert runner._history_service is None
        events = await _collect_events(runner)
        assert any(e.is_final_response() for e in events)


# ---------------------------------------------------------------------------
# TestLlmRequestMetadata
# ---------------------------------------------------------------------------


class TestLlmRequestMetadata:
    """LlmRequest.metadata field (Doc 19)."""

    def test_metadata_default_empty(self):
        req = LlmRequest()
        assert req.metadata == {}

    def test_metadata_set_and_retrieve(self):
        req = LlmRequest(metadata={"user_id": "u1"})
        assert req.metadata["user_id"] == "u1"

    async def test_user_id_in_metadata_after_run(self):
        """After runner.run, the LLM request should have user_id in metadata."""
        received_metadata = {}

        class MetaCaptureLlm(BaseLlm):
            @classmethod
            def supported_models(cls):
                return [r"conv-mock-.*"]

            async def generate_content_async(self, llm_request, *, stream=False):
                received_metadata.update(llm_request.metadata)
                yield LlmResponse(
                    content=Content(role="model", parts=[Part(text="ok")])
                )

        ModelRegistry.reset()
        ModelRegistry.register(r"conv-mock-.*", MetaCaptureLlm)

        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
        )
        await _collect_events(runner, user_id="user_123", message="test")

        assert received_metadata.get("user_id") == "user_123"

        ModelRegistry.reset()
        ModelRegistry.register(r"conv-mock-.*", ConvMockLlm)


# ---------------------------------------------------------------------------
# TestACPLlmProviderSessionStore
# ---------------------------------------------------------------------------


class TestACPLlmProviderSessionStore:
    """ACPLlm.set_provider_session_store (Doc 19)."""

    def test_default_none(self):
        from soulbot.models.acp_llm import ACPLlm
        ACPLlm.set_provider_session_store(None)
        assert ACPLlm._provider_session_store is None

    def test_set_store(self):
        from soulbot.models.acp_llm import ACPLlm
        mock = object()
        ACPLlm.set_provider_session_store(mock)
        assert ACPLlm._provider_session_store is mock
        ACPLlm.set_provider_session_store(None)

    def test_set_none_clears(self):
        from soulbot.models.acp_llm import ACPLlm
        ACPLlm.set_provider_session_store(object())
        ACPLlm.set_provider_session_store(None)
        assert ACPLlm._provider_session_store is None
