"""Tests for SOULBOT_CMD bidirectional feedback (Doc 26).

Verifies that CMD execution results are fed back to the LLM as
``Part(function_response=...)`` events, triggering a second LLM call
where the model can see and reason about CMD results.
"""

import pytest

from soulbot.agents import LlmAgent, InvocationContext, RunConfig
from soulbot.commands.executor import CommandExecutor
from soulbot.events.event import Content, Event, FunctionResponse, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService


# ---------------------------------------------------------------------------
# Mock LLM with call counting
# ---------------------------------------------------------------------------


class FeedbackMockLlm(BaseLlm):
    """Mock LLM that tracks call count and returns pre-configured responses."""

    _responses: list[LlmResponse] = []
    _call_count: int = 0

    @classmethod
    def reset(cls):
        cls._responses = []
        cls._call_count = 0

    @classmethod
    def set_responses(cls, responses: list[LlmResponse]):
        cls._responses = list(responses)
        cls._call_count = 0

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"fb-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        FeedbackMockLlm._call_count += 1
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_feedback_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"fb-mock-.*", FeedbackMockLlm)
    FeedbackMockLlm.reset()
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class RecordingService:
    """Service that records calls and returns configurable data."""

    def __init__(self):
        self.calls: list[dict] = []

    def add(self, **kwargs):
        self.calls.append({"action": "add", **kwargs})
        return {"entry_id": "new_123", "status": "active"}

    def list(self, **kwargs):
        self.calls.append({"action": "list", **kwargs})
        return {
            "entries": [
                {"id": "s_001", "status": "active", "message": "Wake up"},
                {"id": "s_002", "status": "paused", "message": "Check mail"},
            ],
            "count": 2,
        }

    def cancel(self, **kwargs):
        self.calls.append({"action": "cancel", **kwargs})
        return {"cancelled": True}


def _make_agent(name="test_agent"):
    return LlmAgent(
        name=name,
        model="fb-mock-model",
        instruction="You are a test agent.",
    )


def _make_runner(agent=None, cmd_executor=None):
    return Runner(
        agent=agent or _make_agent(),
        app_name="test",
        session_service=InMemorySessionService(),
        cmd_executor=cmd_executor,
    )


async def _collect_events(runner, message="hello", run_config=None):
    events = []
    async for event in runner.run(
        user_id="u1", session_id="s1",
        message=message, run_config=run_config,
    ):
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCmdFeedback:
    """Doc 26: CMD results fed back as function_response."""

    async def test_cmd_yields_function_response(self):
        """CMD execution produces a function_response event."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='Checking<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="You have 2 tasks.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        events = await _collect_events(_make_runner(cmd_executor=executor))

        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        assert fr_events[0].content.role == "user"

    async def test_cmd_result_name_format(self):
        """function_response.name = 'service.action' format."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Done.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        events = await _collect_events(_make_runner(cmd_executor=executor))

        fr_events = [e for e in events if e.get_function_responses()]
        fr = fr_events[0].get_function_responses()[0]
        assert fr.name == "schedule.list"

    async def test_cmd_success_data(self):
        """Successful CMD result contains service return data."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Here are your tasks.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        events = await _collect_events(_make_runner(cmd_executor=executor))

        fr = [e for e in events if e.get_function_responses()][0]
        resp = fr.get_function_responses()[0].response
        assert resp["count"] == 2
        assert len(resp["entries"]) == 2
        assert resp["entries"][0]["id"] == "s_001"

    async def test_cmd_error_data(self):
        """Failed CMD result contains error message."""

        class FailService:
            def add(self, **kwargs):
                raise RuntimeError("Duplicate ID")

        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Creating...'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"dup","message":"test"}}-->'
                ))
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Creation failed.")
            ])),
        ])
        executor = CommandExecutor()
        executor.register_service("schedule", FailService())

        events = await _collect_events(_make_runner(cmd_executor=executor))

        fr = [e for e in events if e.get_function_responses()][0]
        resp = fr.get_function_responses()[0].response
        assert "error" in resp
        assert "Duplicate ID" in resp["error"]

    async def test_cmd_triggers_second_llm_call(self):
        """CMD presence triggers exactly 2 LLM calls (Round 1 + Round 2)."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Tasks listed.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        await _collect_events(_make_runner(cmd_executor=executor))

        assert FeedbackMockLlm._call_count == 2

    async def test_no_cmd_single_llm_call(self):
        """Without CMD, only 1 LLM call is made."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Just a plain reply.")
            ])),
        ])
        executor = CommandExecutor()

        await _collect_events(_make_runner(cmd_executor=executor))

        assert FeedbackMockLlm._call_count == 1

    async def test_cmd_text_stripped(self):
        """CMD markers are removed from user-visible events."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Reminder set!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":300},'
                    '"task":{"id":"r1","message":"Time!"}}-->'
                ))
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Confirmed.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        events = await _collect_events(_make_runner(cmd_executor=executor))

        # Check all text events for CMD markers
        for event in events:
            if event.content:
                for part in event.content.parts:
                    if part.text:
                        assert "SOULBOT_CMD" not in part.text

    async def test_multi_cmd_multi_response(self):
        """Multiple CMDs in one response produce multiple function_response parts."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Processing...'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"cancel","id":"s_001"}-->'
                ))
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Done processing.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        events = await _collect_events(_make_runner(cmd_executor=executor))

        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1  # One event with multiple parts
        frs = fr_events[0].get_function_responses()
        assert len(frs) == 2
        assert frs[0].name == "schedule.list"
        assert frs[1].name == "schedule.cancel"

    async def test_cmd_routing_injected(self):
        """schedule.add gets routing metadata injected."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Set!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"t1","message":"hey"}}-->'
                ))
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Confirmed.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        agent = _make_agent(name="my_agent")
        runner = _make_runner(agent=agent, cmd_executor=executor)
        await _collect_events(
            runner,
            run_config=RunConfig(context={
                "channel": "telegram",
                "user_id": "789",
            }),
        )

        call = recording.calls[0]
        assert call["origin_channel"] == "telegram"
        assert call["origin_user"] == "789"
        assert call["from_agent"] == "my_agent"
        assert call["to_agent"] == "my_agent"

    async def test_max_llm_calls_prevents_loop(self):
        """max_llm_calls prevents infinite CMD loops."""
        # Every response contains a CMD → infinite loop
        # But max_llm_calls=3 should stop it
        # Each response must be a separate object (shared refs get mutated)
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='Loop<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ]))
            for _ in range(10)
        ])

        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test",
            session_service=InMemorySessionService(),
            cmd_executor=executor,
        )

        with pytest.raises(RuntimeError, match="Exceeded max LLM calls"):
            await _collect_events(
                runner,
                run_config=RunConfig(max_llm_calls=3),
            )

    async def test_no_cmd_executor_passthrough(self):
        """Without cmd_executor, CMD markers remain in text (no processing)."""
        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Hello!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->'
                ))
            ])),
        ])
        # No cmd_executor
        runner = _make_runner()

        events = await _collect_events(runner)

        final = [e for e in events if e.is_final_response()]
        assert len(final) == 1
        text = " ".join(p.text for p in final[0].content.parts if p.text)
        assert "SOULBOT_CMD" in text
        assert FeedbackMockLlm._call_count == 1

    async def test_cmd_bus_event_published(self):
        """CMD execution publishes 'cmd.executed' bus events."""

        class RecordingBus:
            def __init__(self):
                self.events = []

            async def publish(self, event):
                self.events.append(event)

        FeedbackMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Done.")
            ])),
        ])
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)
        bus = RecordingBus()

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test",
            session_service=InMemorySessionService(),
            cmd_executor=executor,
            bus=bus,
        )

        await _collect_events(runner)

        cmd_events = [e for e in bus.events if e.type == "cmd.executed"]
        assert len(cmd_events) == 1
        assert cmd_events[0].data["service"] == "schedule"
        assert cmd_events[0].data["action"] == "list"
        assert cmd_events[0].data["success"] is True
