"""Tests for Event data models."""

import pytest

from soulbot.events import Content, Event, EventActions, FunctionCall, FunctionResponse, Part


class TestPart:
    def test_text_part(self):
        p = Part(text="hello")
        assert p.text == "hello"
        assert p.function_call is None
        assert p.function_response is None

    def test_function_call_part(self):
        fc = FunctionCall(name="get_weather", args={"city": "Tokyo"})
        p = Part(function_call=fc)
        assert p.text is None
        assert p.function_call.name == "get_weather"
        assert p.function_call.args == {"city": "Tokyo"}
        assert p.function_call.id  # auto-generated

    def test_function_response_part(self):
        fr = FunctionResponse(name="get_weather", response={"temp": 20})
        p = Part(function_response=fr)
        assert p.function_response.name == "get_weather"
        assert p.function_response.response == {"temp": 20}


class TestContent:
    def test_defaults(self):
        c = Content()
        assert c.role == "model"
        assert c.parts == []

    def test_user_content(self):
        c = Content(role="user", parts=[Part(text="hi")])
        assert c.role == "user"
        assert len(c.parts) == 1
        assert c.parts[0].text == "hi"


class TestEventActions:
    def test_defaults(self):
        ea = EventActions()
        assert ea.state_delta == {}
        assert ea.artifact_delta == {}
        assert ea.transfer_to_agent is None
        assert ea.escalate is None
        assert ea.skip_summarization is None

    def test_state_delta(self):
        ea = EventActions(state_delta={"count": 5})
        assert ea.state_delta["count"] == 5

    def test_transfer(self):
        ea = EventActions(transfer_to_agent="billing_agent")
        assert ea.transfer_to_agent == "billing_agent"


class TestEvent:
    def test_defaults(self):
        e = Event()
        assert e.id  # auto-generated UUID
        assert e.author == ""
        assert e.content is None
        assert e.partial is False
        assert e.actions.state_delta == {}
        assert e.error_code is None

    def test_event_with_content(self):
        content = Content(role="model", parts=[Part(text="Hello!")])
        e = Event(author="greeter", content=content)
        assert e.author == "greeter"
        assert e.content.parts[0].text == "Hello!"

    def test_get_function_calls(self):
        fc1 = FunctionCall(name="tool_a", args={"x": 1})
        fc2 = FunctionCall(name="tool_b", args={"y": 2})
        content = Content(
            role="model",
            parts=[Part(function_call=fc1), Part(text="thinking"), Part(function_call=fc2)],
        )
        e = Event(author="agent", content=content)
        calls = e.get_function_calls()
        assert len(calls) == 2
        assert calls[0].name == "tool_a"
        assert calls[1].name == "tool_b"

    def test_get_function_calls_empty(self):
        e = Event(author="agent", content=Content(parts=[Part(text="done")]))
        assert e.get_function_calls() == []

    def test_get_function_calls_no_content(self):
        e = Event()
        assert e.get_function_calls() == []

    def test_get_function_responses(self):
        fr = FunctionResponse(name="tool_a", response={"result": 42})
        content = Content(role="user", parts=[Part(function_response=fr)])
        e = Event(author="user", content=content)
        responses = e.get_function_responses()
        assert len(responses) == 1
        assert responses[0].response == {"result": 42}

    def test_is_final_response_text(self):
        content = Content(role="model", parts=[Part(text="final answer")])
        e = Event(author="agent", content=content)
        assert e.is_final_response() is True

    def test_is_final_response_function_call(self):
        fc = FunctionCall(name="tool", args={})
        content = Content(role="model", parts=[Part(function_call=fc)])
        e = Event(author="agent", content=content)
        assert e.is_final_response() is False

    def test_is_final_response_partial(self):
        content = Content(role="model", parts=[Part(text="streaming...")])
        e = Event(author="agent", content=content, partial=True)
        assert e.is_final_response() is False

    def test_is_final_response_no_content(self):
        e = Event(author="agent")
        assert e.is_final_response() is False

    def test_serialization_roundtrip(self):
        fc = FunctionCall(name="test", args={"a": 1})
        content = Content(role="model", parts=[Part(function_call=fc)])
        e = Event(
            author="agent",
            content=content,
            actions=EventActions(state_delta={"key": "val"}),
        )
        data = e.model_dump()
        e2 = Event.model_validate(data)
        assert e2.author == "agent"
        assert e2.content.parts[0].function_call.name == "test"
        assert e2.actions.state_delta == {"key": "val"}
