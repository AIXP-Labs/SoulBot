"""Tests for timeout mechanism on tool / CMD / LLM execution paths."""

import asyncio

import pytest

from soulbot.agents import LlmAgent, InvocationContext, RunConfig
from soulbot.commands.executor import CommandExecutor
from soulbot.events.event import Content, Event, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService
from soulbot.tools.base_tool import BaseTool
from soulbot.tools.function_tool import FunctionTool


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class TimeoutMockLlm(BaseLlm):
    """Mock LLM with configurable delay."""

    _responses: list[LlmResponse] = []
    _delay: float = 0.0

    @classmethod
    def reset(cls):
        cls._responses = []
        cls._delay = 0.0

    @classmethod
    def set_responses(cls, responses, delay=0.0):
        cls._responses = list(responses)
        cls._delay = delay

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"to-mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if TimeoutMockLlm._delay > 0:
            await asyncio.sleep(TimeoutMockLlm._delay)
        if self._responses:
            yield self._responses.pop(0)
        else:
            yield LlmResponse(
                content=Content(role="model", parts=[Part(text="default")])
            )


@pytest.fixture(autouse=True)
def setup_timeout_mock():
    ModelRegistry.reset()
    ModelRegistry.register(r"to-mock-.*", TimeoutMockLlm)
    TimeoutMockLlm.reset()
    yield
    ModelRegistry.reset()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(name="test_agent", tools=None):
    return LlmAgent(
        name=name,
        model="to-mock-model",
        instruction="You are a test agent.",
        tools=tools or [],
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
# Tool timeout tests
# ---------------------------------------------------------------------------


class TestToolTimeout:
    async def test_tool_timeout_returns_error(self):
        """Tool that sleeps too long returns timeout error to LLM."""

        async def slow_tool(x: str = "hi") -> str:
            """A slow tool."""
            await asyncio.sleep(10)
            return "done"

        TimeoutMockLlm.set_responses([
            # Round 1: LLM calls the tool
            LlmResponse(content=Content(role="model", parts=[
                Part(function_call=__import__(
                    "soulbot.events.event", fromlist=["FunctionCall"]
                ).FunctionCall(name="slow_tool", args={"x": "test"}))
            ])),
            # Round 2: LLM sees timeout error
            LlmResponse(content=Content(role="model", parts=[
                Part(text="The tool timed out.")
            ])),
        ])

        agent = _make_agent(tools=[slow_tool])
        runner = Runner(
            agent=agent, app_name="test",
            session_service=InMemorySessionService(),
        )
        events = await _collect_events(
            runner, run_config=RunConfig(tool_timeout=0.1),
        )

        # Find function_response with timeout error
        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        fr = fr_events[0].get_function_responses()[0]
        assert "timed out" in fr.response.get("error", "")

    async def test_tool_no_timeout_default(self):
        """Without tool_timeout, tools execute normally."""

        async def fast_tool(x: str = "hi") -> str:
            """A fast tool."""
            return "result"

        from soulbot.events.event import FunctionCall

        TimeoutMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(function_call=FunctionCall(name="fast_tool", args={"x": "test"}))
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Got result.")
            ])),
        ])

        agent = _make_agent(tools=[fast_tool])
        runner = Runner(
            agent=agent, app_name="test",
            session_service=InMemorySessionService(),
        )
        events = await _collect_events(runner)  # No tool_timeout

        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        fr = fr_events[0].get_function_responses()[0]
        assert "result" in str(fr.response)

    async def test_tool_per_tool_timeout_overrides(self):
        """BaseTool.timeout overrides RunConfig.tool_timeout."""

        async def slow_fn(x: str = "hi") -> str:
            """Slow."""
            await asyncio.sleep(10)
            return "done"

        from soulbot.events.event import FunctionCall

        tool = FunctionTool(slow_fn)
        tool.timeout = 0.1  # per-tool: 100ms

        TimeoutMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(function_call=FunctionCall(name="slow_fn", args={"x": "a"}))
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Timed out.")
            ])),
        ])

        agent = _make_agent(tools=[tool])
        runner = Runner(
            agent=agent, app_name="test",
            session_service=InMemorySessionService(),
        )
        # RunConfig has no tool_timeout, but per-tool timeout kicks in
        events = await _collect_events(runner)

        fr_events = [e for e in events if e.get_function_responses()]
        fr = fr_events[0].get_function_responses()[0]
        assert "timed out" in fr.response.get("error", "")


# ---------------------------------------------------------------------------
# CMD timeout tests
# ---------------------------------------------------------------------------


class TestCmdTimeout:
    async def test_cmd_timeout_returns_error(self):
        """CMD that hangs returns timeout error as function_response."""

        class SlowService:
            async def list(self, **kw):
                await asyncio.sleep(10)
                return {"entries": []}

        TimeoutMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="CMD timed out.")
            ])),
        ])

        executor = CommandExecutor()
        executor.register_service("schedule", SlowService())

        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            cmd_executor=executor,
        )
        events = await _collect_events(
            runner, run_config=RunConfig(cmd_timeout=0.1),
        )

        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        fr = fr_events[0].get_function_responses()[0]
        assert "Timed out" in fr.response.get("error", "")

    async def test_cmd_per_cmd_timeout_in_payload(self):
        """timeout field inside CMD JSON triggers per-command timeout."""

        class SlowService:
            async def add(self, **kw):
                await asyncio.sleep(10)
                return {"entry_id": "s_001", "status": "active"}

        # AI writes timeout:0.1 inside CMD payload
        TimeoutMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"add","timeout":0.1,"trigger":{"type":"once","delay":300}}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="CMD timed out.")
            ])),
        ])

        executor = CommandExecutor()
        executor.register_service("schedule", SlowService())

        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            cmd_executor=executor,
        )
        # No RunConfig.cmd_timeout — per-CMD timeout should kick in
        events = await _collect_events(runner)

        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        fr = fr_events[0].get_function_responses()[0]
        assert "Timed out" in fr.response.get("error", "")

    async def test_cmd_no_timeout_default(self):
        """Without cmd_timeout, CMD executes normally."""

        class FastService:
            def list(self, **kw):
                return {"entries": [], "count": 0}

        TimeoutMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text='OK<!--SOULBOT_CMD:{"service":"schedule","action":"list"}-->')
            ])),
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Listed.")
            ])),
        ])

        executor = CommandExecutor()
        executor.register_service("schedule", FastService())

        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
            cmd_executor=executor,
        )
        events = await _collect_events(runner)  # No cmd_timeout

        fr_events = [e for e in events if e.get_function_responses()]
        fr = fr_events[0].get_function_responses()[0]
        assert fr.response.get("count") == 0


# ---------------------------------------------------------------------------
# LLM timeout tests
# ---------------------------------------------------------------------------


class TestLlmTimeout:
    async def test_llm_timeout_yields_error_event(self):
        """LLM that hangs yields a TIMEOUT error event."""
        TimeoutMockLlm.set_responses([], delay=10)  # 10s delay

        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
        )
        events = await _collect_events(
            runner, run_config=RunConfig(llm_timeout=0.1),
        )

        error_events = [e for e in events if e.error_code == "TIMEOUT"]
        assert len(error_events) == 1
        assert "timed out" in error_events[0].error_message

    async def test_llm_no_timeout_default(self):
        """Without llm_timeout, LLM executes normally."""
        TimeoutMockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Normal response.")
            ])),
        ])

        runner = Runner(
            agent=_make_agent(), app_name="test",
            session_service=InMemorySessionService(),
        )
        events = await _collect_events(runner)  # No llm_timeout

        final = [e for e in events if e.is_final_response()]
        assert len(final) == 1
        assert "Normal response" in final[0].content.parts[0].text


# ---------------------------------------------------------------------------
# Integration: timeout error visible to LLM
# ---------------------------------------------------------------------------


class TestTimeoutVisibleToLlm:
    async def test_timeout_error_visible_to_llm(self):
        """After tool timeout, LLM sees error and can respond gracefully."""

        async def hanging_tool(query: str = "") -> str:
            """A tool that hangs."""
            await asyncio.sleep(10)
            return "never"

        from soulbot.events.event import FunctionCall

        TimeoutMockLlm.set_responses([
            # Round 1: LLM calls the tool
            LlmResponse(content=Content(role="model", parts=[
                Part(function_call=FunctionCall(name="hanging_tool", args={"query": "x"}))
            ])),
            # Round 2: LLM sees timeout error, responds gracefully
            LlmResponse(content=Content(role="model", parts=[
                Part(text="Sorry, the tool took too long.")
            ])),
        ])

        agent = _make_agent(tools=[hanging_tool])
        runner = Runner(
            agent=agent, app_name="test",
            session_service=InMemorySessionService(),
        )
        events = await _collect_events(
            runner, run_config=RunConfig(tool_timeout=0.1),
        )

        # Verify the final response references the timeout
        final = [e for e in events if e.is_final_response()]
        assert any("too long" in (f.content.parts[0].text or "") for f in final)

        # Verify the timeout error was in function_response
        fr_events = [e for e in events if e.get_function_responses()]
        assert len(fr_events) == 1
        assert "timed out" in fr_events[0].get_function_responses()[0].response.get("error", "")
