"""Tests for Session model."""

from soulbot.events import Content, Event, Part
from soulbot.sessions import Session, State


class TestSession:
    def test_defaults(self):
        s = Session()
        assert s.id  # auto-generated
        assert s.app_name == ""
        assert s.user_id == ""
        assert isinstance(s.state, State)
        assert s.events == []
        assert s.last_update_time > 0

    def test_custom_values(self):
        s = Session(id="s-123", app_name="myapp", user_id="u-1")
        assert s.id == "s-123"
        assert s.app_name == "myapp"
        assert s.user_id == "u-1"

    def test_state_is_state_instance(self):
        s = Session()
        s.state["key"] = "val"
        assert s.state["key"] == "val"
        assert s.state.has_delta

    def test_events_append(self):
        s = Session()
        e = Event(author="user", content=Content(role="user", parts=[Part(text="hi")]))
        s.events.append(e)
        assert len(s.events) == 1
        assert s.events[0].author == "user"
