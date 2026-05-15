"""Integration tests for LlmAgent and Runner using a mock model."""

import pytest

from soulbot.agents import LlmAgent, InvocationContext, RunConfig
from soulbot.events.event import Content, Event, FunctionCall, Part
from soulbot.models.base_llm import BaseLlm
from soulbot.models.llm_request import LlmRequest, LlmResponse
from soulbot.models.registry import ModelRegistry
from soulbot.runners import Runner
from soulbot.sessions import InMemorySessionService, Session


# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class MockLlm(BaseLlm):
    """A mock LLM that returns pre-configured responses."""

    # Class-level response queue (shared across instances with same model name)
    _responses: list[LlmResponse] = []

    @classmethod
    def set_responses(cls, responses: list[LlmResponse]):
        cls._responses = list(responses)

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"mock-.*"]

    async def generate_content_async(self, llm_request, *, stream=False):
        if self._responses:
            resp = self._responses.pop(0)
        else:
            resp = LlmResponse(
                content=Content(role="model", parts=[Part(text="default mock response")])
            )
        yield resp


@pytest.fixture(autouse=True)
def setup_mock_registry():
    """Register mock LLM before each test, reset after."""
    ModelRegistry.reset()
    ModelRegistry.register(r"mock-.*", MockLlm)
    yield
    ModelRegistry.reset()


@pytest.fixture
def session_service():
    return InMemorySessionService()


# ---------------------------------------------------------------------------
# LlmAgent basic text response
# ---------------------------------------------------------------------------


class TestLlmAgentTextResponse:
    @pytest.mark.asyncio
    async def test_simple_text_response(self, session_service):
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="Hello!")]))
        ])

        agent = LlmAgent(name="greeter", model="mock-v1", instruction="Say hello")
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        async for event in runner.run(user_id="u1", session_id="s1", message="Hi"):
            events.append(event)

        # Should have exactly one non-partial event
        non_partial = [e for e in events if not e.partial]
        assert len(non_partial) == 1
        assert non_partial[0].content.parts[0].text == "Hello!"
        assert non_partial[0].author == "greeter"

    @pytest.mark.asyncio
    async def test_session_has_events(self, session_service):
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="World")]))
        ])

        agent = LlmAgent(name="bot", model="mock-v1")
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        async for _ in runner.run(user_id="u1", session_id="s1", message="Hello"):
            pass

        session = await session_service.get_session("test", "u1", "s1")
        assert session is not None
        # user event + agent event (partial events are skipped by session service)
        assert len(session.events) >= 2
        assert session.events[0].author == "user"


# ---------------------------------------------------------------------------
# Instruction rendering
# ---------------------------------------------------------------------------


class TestInstructionRendering:
    @pytest.mark.asyncio
    async def test_state_variable_substitution(self, session_service):
        """Verify {var} in instructions is replaced from session state."""
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="OK")]))
        ])

        agent = LlmAgent(
            name="bot",
            model="mock-v1",
            instruction="User language is {lang}. Reply in {lang}.",
        )

        # Create session with pre-set state
        session = await session_service.create_session(
            "test", "u1", agent_name="bot", session_id="s1", state={"lang": "Japanese"}
        )

        runner = Runner(agent=agent, app_name="test", session_service=session_service)
        async for _ in runner.run(user_id="u1", session_id="s1", message="Hi"):
            pass

    @pytest.mark.asyncio
    async def test_callable_instruction(self, session_service):
        """Verify callable instructions work."""
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="OK")]))
        ])

        def dynamic_instruction(ctx):
            return f"You are agent for app {ctx.session.app_name}"

        agent = LlmAgent(
            name="bot", model="mock-v1", instruction=dynamic_instruction
        )
        runner = Runner(agent=agent, app_name="myapp", session_service=session_service)
        async for _ in runner.run(user_id="u1", session_id="s1", message="Hi"):
            pass


# ---------------------------------------------------------------------------
# Output key
# ---------------------------------------------------------------------------


class TestOutputKey:
    @pytest.mark.asyncio
    async def test_output_key_saves_to_state(self, session_service):
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="The answer is 42")]))
        ])

        agent = LlmAgent(
            name="bot", model="mock-v1", output_key="result"
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        async for _ in runner.run(user_id="u1", session_id="s1", message="What?"):
            pass

        session = await session_service.get_session("test", "u1", "s1")
        assert session.state["result"] == "The answer is 42"


# ---------------------------------------------------------------------------
# Tool calling
# ---------------------------------------------------------------------------


class TestToolCalling:
    @pytest.mark.asyncio
    async def test_single_tool_call(self, session_service):
        """LLM calls a tool, gets the result, then returns final text."""
        # First response: tool call
        MockLlm.set_responses([
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[
                        Part(
                            function_call=FunctionCall(
                                name="get_weather",
                                args={"city": "Tokyo"},
                                id="call-1",
                            )
                        )
                    ],
                )
            ),
            # Second response: final text after seeing tool result
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[Part(text="The weather in Tokyo is sunny, 25°C")],
                )
            ),
        ])

        def get_weather(city: str) -> dict:
            """Get weather for a city."""
            return {"city": city, "weather": "sunny", "temp": 25}

        agent = LlmAgent(
            name="weather_bot",
            model="mock-v1",
            instruction="You help with weather queries",
            tools=[get_weather],
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="s1", message="Weather in Tokyo?"
        ):
            events.append(event)

        # Events: tool_call event, tool_response event, final text event
        non_partial = [e for e in events if not e.partial]
        assert len(non_partial) == 3

        # First: the model's function call
        assert non_partial[0].get_function_calls()[0].name == "get_weather"

        # Second: tool response
        responses = non_partial[1].get_function_responses()
        assert len(responses) == 1
        assert responses[0].name == "get_weather"
        assert responses[0].response["city"] == "Tokyo"

        # Third: final text
        assert "Tokyo" in non_partial[2].content.parts[0].text

    @pytest.mark.asyncio
    async def test_auto_wrap_function_as_tool(self, session_service):
        """Verify plain functions are auto-wrapped as FunctionTool."""
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="done")]))
        ])

        def my_tool(x: int) -> int:
            """Double a number."""
            return x * 2

        agent = LlmAgent(name="bot", model="mock-v1", tools=[my_tool])
        # Verify the tool was wrapped
        assert len(agent.tools) == 1
        from soulbot.tools import FunctionTool

        assert isinstance(agent.tools[0], FunctionTool)
        assert agent.tools[0].name == "my_tool"


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


class TestCallbacks:
    @pytest.mark.asyncio
    async def test_before_model_callback_override(self, session_service):
        """before_model_callback returning a response skips the model call."""
        # Set response that should NOT be used
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="from model")]))
        ])

        def before_model(ctx, request):
            return LlmResponse(
                content=Content(role="model", parts=[Part(text="intercepted")])
            )

        agent = LlmAgent(
            name="bot", model="mock-v1", before_model_callback=before_model
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        async for event in runner.run(user_id="u1", session_id="s1", message="Hi"):
            events.append(event)

        non_partial = [e for e in events if not e.partial]
        assert non_partial[0].content.parts[0].text == "intercepted"

    @pytest.mark.asyncio
    async def test_after_model_callback_modify(self, session_service):
        """after_model_callback can modify the model response."""
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="original")]))
        ])

        def after_model(ctx, response):
            return LlmResponse(
                content=Content(role="model", parts=[Part(text="modified")])
            )

        agent = LlmAgent(
            name="bot", model="mock-v1", after_model_callback=after_model
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        async for event in runner.run(user_id="u1", session_id="s1", message="Hi"):
            events.append(event)

        non_partial = [e for e in events if not e.partial]
        assert non_partial[0].content.parts[0].text == "modified"

    @pytest.mark.asyncio
    async def test_before_tool_callback_skip(self, session_service):
        """before_tool_callback returning a dict skips tool execution."""
        MockLlm.set_responses([
            LlmResponse(
                content=Content(
                    role="model",
                    parts=[Part(function_call=FunctionCall(name="my_tool", args={"x": 1}, id="c1"))],
                )
            ),
            LlmResponse(content=Content(role="model", parts=[Part(text="done")])),
        ])

        call_count = 0

        def my_tool(x: int) -> int:
            """A tool."""
            nonlocal call_count
            call_count += 1
            return x * 2

        def before_tool(ctx, name, args):
            return {"result": "cached_value"}

        agent = LlmAgent(
            name="bot",
            model="mock-v1",
            tools=[my_tool],
            before_tool_callback=before_tool,
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        async for _ in runner.run(user_id="u1", session_id="s1", message="Go"):
            pass

        assert call_count == 0  # Tool was NOT actually called


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_model_error_response(self, session_service):
        MockLlm.set_responses([
            LlmResponse(error_code="RATE_LIMIT", error_message="Too many requests")
        ])

        agent = LlmAgent(name="bot", model="mock-v1")
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        async for event in runner.run(user_id="u1", session_id="s1", message="Hi"):
            events.append(event)

        error_events = [e for e in events if e.error_code]
        assert len(error_events) == 1
        assert error_events[0].error_code == "RATE_LIMIT"

    @pytest.mark.asyncio
    async def test_max_llm_calls_exceeded(self, session_service):
        """Verify the agent stops after max_llm_calls."""
        # Keep returning tool calls to force loop
        def make_tool_response():
            return LlmResponse(
                content=Content(
                    role="model",
                    parts=[Part(function_call=FunctionCall(name="echo", args={"msg": "x"}, id="c"))],
                )
            )

        # Set more responses than max_llm_calls
        MockLlm.set_responses([make_tool_response() for _ in range(10)])

        def echo(msg: str) -> str:
            """Echo."""
            return msg

        agent = LlmAgent(name="bot", model="mock-v1", tools=[echo])
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        with pytest.raises(RuntimeError, match="Exceeded max LLM calls"):
            async for event in runner.run(
                user_id="u1",
                session_id="s1",
                message="Go",
                run_config=RunConfig(max_llm_calls=3),
            ):
                events.append(event)


# ---------------------------------------------------------------------------
# Sliding window — max_history_events
# ---------------------------------------------------------------------------


class TestSlidingWindow:
    """Verify _build_contents respects RunConfig.max_history_events."""

    @pytest.mark.asyncio
    async def test_old_events_dropped(self, session_service):
        """Only the most recent max_history_events events appear in the prompt."""
        # Pre-populate a session with many events
        session = await session_service.create_session(
            "test", "u1", agent_name="bot", session_id="sw1",
        )
        for i in range(20):
            role = "user" if i % 2 == 0 else "model"
            session.events.append(Event(
                author="user" if role == "user" else "bot",
                invocation_id="inv",
                content=Content(role=role, parts=[Part(text=f"msg-{i}")]),
            ))

        assert len(session.events) == 20

        # Track what contents _build_request produces
        captured_contents: list = []
        original_set = MockLlm.set_responses

        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="ok")]))
        ])

        agent = LlmAgent(name="bot", model="mock-v1")
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        # Run with max_history_events=6: should only see last 6 of the 20
        # pre-existing events + 1 new user event = 7 total events in session,
        # but sliding window picks last 6 from the 21 total.
        async for _ in runner.run(
            user_id="u1", session_id="sw1", message="latest",
            run_config=RunConfig(max_history_events=6),
        ):
            pass

        # Session should have 21 events total (20 pre + 1 new user + 1 agent response = 22)
        session = await session_service.get_session("test", "u1", "sw1")
        assert len(session.events) == 22  # all events are preserved in session

    @pytest.mark.asyncio
    async def test_sliding_window_disabled(self, session_service):
        """max_history_events=0 means no limit."""
        session = await session_service.create_session(
            "test", "u1", agent_name="bot", session_id="sw2",
        )
        for i in range(10):
            session.events.append(Event(
                author="user",
                invocation_id="inv",
                content=Content(role="user", parts=[Part(text=f"msg-{i}")]),
            ))

        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="ok")]))
        ])

        agent = LlmAgent(name="bot", model="mock-v1")
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        # max_history_events=0 disables the limit
        async for _ in runner.run(
            user_id="u1", session_id="sw2", message="go",
            run_config=RunConfig(max_history_events=0),
        ):
            pass

        # All events should be present (no truncation)
        session = await session_service.get_session("test", "u1", "sw2")
        assert len(session.events) == 12  # 10 pre + 1 user + 1 agent

    @pytest.mark.asyncio
    async def test_default_max_history(self):
        """Default max_history_events is 100."""
        config = RunConfig()
        assert config.max_history_events == 100


# ---------------------------------------------------------------------------
# current_turn mode — ACP session memory optimization
# ---------------------------------------------------------------------------


class TestCurrentTurnMode:
    """Verify include_contents='current_turn' only sends the latest turn."""

    @pytest.mark.asyncio
    async def test_only_latest_user_message_sent(self, session_service):
        """Old conversation history is NOT included in the prompt."""
        # Pre-populate session with 10 old turns
        session = await session_service.create_session(
            "test", "u1", agent_name="bot", session_id="ct1",
        )
        for i in range(10):
            role = "user" if i % 2 == 0 else "model"
            session.events.append(Event(
                author="user" if role == "user" else "bot",
                invocation_id="old-inv",
                content=Content(role=role, parts=[Part(text=f"old-msg-{i}")]),
            ))

        # Capture what gets sent to the LLM
        captured_request: list[LlmRequest] = []
        orig_generate = MockLlm.generate_content_async

        async def spy_generate(self_llm, llm_request, *, stream=False):
            captured_request.append(llm_request)
            async for r in orig_generate(self_llm, llm_request, stream=stream):
                yield r

        MockLlm.generate_content_async = spy_generate

        try:
            MockLlm.set_responses([
                LlmResponse(content=Content(role="model", parts=[Part(text="ok")]))
            ])

            agent = LlmAgent(
                name="bot", model="mock-v1",
                include_contents="current_turn",
            )
            runner = Runner(agent=agent, app_name="test", session_service=session_service)

            async for _ in runner.run(
                user_id="u1", session_id="ct1", message="latest-only",
            ):
                pass

            # The LLM should have received only 1 content (the latest user message)
            assert len(captured_request) == 1
            contents = captured_request[0].contents
            assert len(contents) == 1
            assert contents[0].parts[0].text == "latest-only"

            # But session still has all events (10 old + 1 user + 1 agent = 12)
            session = await session_service.get_session("test", "u1", "ct1")
            assert len(session.events) == 12
        finally:
            MockLlm.generate_content_async = orig_generate

    @pytest.mark.asyncio
    async def test_current_turn_includes_tool_events(self, session_service):
        """Tool call/response events in the current turn ARE included."""
        # Pre-populate with old history
        session = await session_service.create_session(
            "test", "u1", agent_name="bot", session_id="ct2",
        )
        for i in range(4):
            session.events.append(Event(
                author="user",
                invocation_id="old",
                content=Content(role="user", parts=[Part(text=f"old-{i}")]),
            ))

        captured_requests: list[LlmRequest] = []
        orig_generate = MockLlm.generate_content_async

        async def spy_generate(self_llm, llm_request, *, stream=False):
            captured_requests.append(llm_request)
            async for r in orig_generate(self_llm, llm_request, stream=stream):
                yield r

        MockLlm.generate_content_async = spy_generate

        try:
            MockLlm.set_responses([
                # First: tool call
                LlmResponse(
                    content=Content(
                        role="model",
                        parts=[Part(function_call=FunctionCall(
                            name="echo", args={"msg": "hi"}, id="c1",
                        ))],
                    )
                ),
                # Second: final text (after tool result)
                LlmResponse(
                    content=Content(role="model", parts=[Part(text="done")])
                ),
            ])

            def echo(msg: str) -> str:
                """Echo."""
                return msg

            agent = LlmAgent(
                name="bot", model="mock-v1",
                include_contents="current_turn",
                tools=[echo],
            )
            runner = Runner(agent=agent, app_name="test", session_service=session_service)

            async for _ in runner.run(
                user_id="u1", session_id="ct2", message="call-tool",
            ):
                pass

            # First LLM call: only the user message
            assert len(captured_requests[0].contents) == 1
            assert captured_requests[0].contents[0].parts[0].text == "call-tool"

            # Second LLM call: user message + tool_call + tool_response
            # (all from the current turn, no old history)
            second_contents = captured_requests[1].contents
            assert len(second_contents) == 3  # user + tool_call + tool_response
            assert second_contents[0].parts[0].text == "call-tool"
            # No old messages should be present
            all_texts = []
            for c in second_contents:
                for p in c.parts:
                    if p.text:
                        all_texts.append(p.text)
            assert not any("old-" in t for t in all_texts)
        finally:
            MockLlm.generate_content_async = orig_generate

    @pytest.mark.asyncio
    async def test_empty_session_current_turn(self, session_service):
        """current_turn mode works on a fresh session (no prior events)."""
        MockLlm.set_responses([
            LlmResponse(content=Content(role="model", parts=[Part(text="hi")]))
        ])

        agent = LlmAgent(
            name="bot", model="mock-v1",
            include_contents="current_turn",
        )
        runner = Runner(agent=agent, app_name="test", session_service=session_service)

        events = []
        async for event in runner.run(
            user_id="u1", session_id="ct3", message="hello",
        ):
            events.append(event)

        non_partial = [e for e in events if not e.partial]
        assert len(non_partial) == 1
        assert non_partial[0].content.parts[0].text == "hi"
