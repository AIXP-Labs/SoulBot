"""Tests for SOULBOT_CMD integration (Doc 17.3, Doc 26).

Verifies that:
- LlmAgent parses SOULBOT_CMD directives from model responses
- CMD markers are stripped from text delivered to the caller
- Routing info (origin_channel, origin_user, agent_name) is injected
- Commands are executed via CommandExecutor
- CMD results are fed back to LLM as function_response (Doc 26)
- Events pass through normally when no commands exist
"""

import pytest

from soulbot.agents import LlmAgent, InvocationContext, RunConfig
from soulbot.commands.executor import CommandExecutor
from soulbot.commands.parser import ParsedCommand
from soulbot.events.event import Content, Event, FunctionCall, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class CmdMockLlm(BaseLlm):
    """Mock LLM that returns pre-configured responses."""

    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses: list[LlmResponse]):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"cmd-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_cmd_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"cmd-mock-.*", CmdMockLlm)
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(name="test_agent"):
    return LlmAgent(
        name=name,
        model="cmd-mock-model",
        instruction="You are a test agent.",
    )


class RecordingService:
    """Records all method calls for assertion."""

    def __init__(self):
        self.calls: list[dict] = []

    def add(self, **kwargs):
        self.calls.append({"action": "add", **kwargs})
        return {"entry_id": "test_id", "status": "active"}

    def list(self, **kwargs):
        self.calls.append({"action": "list", **kwargs})
        return {"entries": [], "count": 0}


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
# Tests
# ---------------------------------------------------------------------------


class TestRunnerCommandParsing:
    """LlmAgent parses SOULBOT_CMD and feeds results back to LLM (Doc 26)."""

    async def test_cmd_stripped_from_response(self):
        """CMD markers are removed from the event text delivered to caller."""
        CmdMockLlm.set_responses([
            # Round 1: model response with CMD
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'OK! 5 minutes reminder set.'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":300},'
                    '"task":{"id":"remind","message":"Time!"}}-->'
                ))
            ])),
            # Round 2: model sees CMD result and responds
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Reminder confirmed.")
            ])),
        ])
        svc = InMemorySessionService()
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            cmd_executor=executor,
        )
        events = await _collect_events(runner)

        # Doc 26: CMD triggers a second LLM call, so 2 final responses
        final = [e for e in events if e.is_final_response()]
        assert len(final) == 2
        # First final: cleaned CMD text
        text = " ".join(p.text for p in final[0].content.parts if p.text)
        assert "SOULBOT_CMD" not in text
        assert "OK! 5 minutes reminder set." in text

        # CMD result fed back as function_response
        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        fr = fr_events[0].get_function_responses()[0]
        assert fr.name == "schedule.add"

    async def test_cmd_executed(self):
        """Commands are dispatched to CommandExecutor."""
        CmdMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Done!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"t1","message":"hi"}}-->'
                ))
            ]))
        ])
        svc = InMemorySessionService()
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            cmd_executor=executor,
        )
        await _collect_events(runner)

        assert len(recording.calls) == 1
        assert recording.calls[0]["action"] == "add"

    async def test_routing_info_injected(self):
        """origin_channel, origin_user, from_agent, to_agent are injected for schedule.add."""
        CmdMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Set!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"t2","message":"hey"}}-->'
                ))
            ]))
        ])
        svc = InMemorySessionService()
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        agent = _make_agent(name="my_agent")
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            cmd_executor=executor,
        )
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

    async def test_no_cmd_passthrough(self):
        """Events without commands pass through unchanged."""
        CmdMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Just a normal reply, no commands here.")
            ]))
        ])
        svc = InMemorySessionService()
        executor = CommandExecutor()

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            cmd_executor=executor,
        )
        events = await _collect_events(runner)

        final = [e for e in events if e.is_final_response()]
        assert len(final) == 1
        text = " ".join(p.text for p in final[0].content.parts if p.text)
        assert text == "Just a normal reply, no commands here."

    async def test_no_executor_passthrough(self):
        """Without cmd_executor, CMD markers remain in text (no processing)."""
        CmdMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Hello!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"x","message":"y"}}-->'
                ))
            ]))
        ])
        svc = InMemorySessionService()
        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            # No cmd_executor
        )
        events = await _collect_events(runner)

        final = [e for e in events if e.is_final_response()]
        text = " ".join(p.text for p in final[0].content.parts if p.text)
        # CMD markers remain since no executor
        assert "SOULBOT_CMD" in text

    async def test_multiple_commands(self):
        """Multiple commands in one response are all executed."""
        CmdMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Two tasks created!'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"a","message":"first"}}-->'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->'
                ))
            ]))
        ])
        svc = InMemorySessionService()
        recording = RecordingService()
        executor = CommandExecutor()
        executor.register_service("schedule", recording)

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            cmd_executor=executor,
        )
        await _collect_events(runner)

        assert len(recording.calls) == 2
        assert recording.calls[0]["action"] == "add"
        assert recording.calls[1]["action"] == "list"

    async def test_cmd_error_does_not_crash(self):
        """Command execution failure is fed back as error but doesn't crash."""

        class FailingService:
            def add(self, **kwargs):
                raise RuntimeError("Service down")

        CmdMockLlm.set_responses([
            # Round 1: model response with CMD
            LlmResponse(content=Content(role="model", parts=[
                Part(text=(
                    'Trying...'
                    '<!--SOULBOT_CMD:{"service":"schedule","action":"add",'
                    '"trigger":{"type":"once","delay":60},'
                    '"task":{"id":"f","message":"fail"}}-->'
                ))
            ])),
            # Round 2: model sees error result and responds
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Sorry, scheduling failed.")
            ])),
        ])
        svc = InMemorySessionService()
        executor = CommandExecutor()
        executor.register_service("schedule", FailingService())

        agent = _make_agent()
        runner = Runner(
            agent=agent, app_name="test", session_service=svc,
            cmd_executor=executor,
        )
        # Should not raise
        events = await _collect_events(runner)
        final = [e for e in events if e.is_final_response()]
        assert len(final) == 2

        # Error is captured in function_response (Doc 26)
        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        fr = fr_events[0].get_function_responses()[0]
        assert "Service down" in fr.response.get("error", "")
