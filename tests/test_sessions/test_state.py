"""Tests for State class."""

import pytest

from soulbot.sessions.state import State


class TestState:
    def test_empty_state(self):
        s = State()
        assert len(s) == 0
        assert s.get("missing") is None

    def test_init_with_data(self):
        s = State({"a": 1, "b": 2})
        assert s["a"] == 1
        assert s["b"] == 2
        assert len(s) == 2

    def test_setitem_tracks_delta(self):
        s = State()
        s["x"] = 10
        assert s["x"] == 10
        assert s.has_delta
        assert s._delta == {"x": 10}

    def test_getitem_missing_raises(self):
        s = State()
        with pytest.raises(KeyError):
            _ = s["nope"]

    def test_get_default(self):
        s = State()
        assert s.get("missing", 42) == 42

    def test_contains(self):
        s = State({"key": "val"})
        assert "key" in s
        assert "other" not in s

    def test_commit_delta(self):
        s = State()
        s["a"] = 1
        s["b"] = 2
        delta = s.commit_delta()
        assert delta == {"a": 1, "b": 2}
        assert not s.has_delta
        # Values remain in _value
        assert s["a"] == 1
        assert s["b"] == 2

    def test_commit_delta_empty(self):
        s = State({"x": 1})
        delta = s.commit_delta()
        assert delta == {}

    def test_apply_delta(self):
        s = State({"a": 1})
        s.apply_delta({"a": 10, "b": 20})
        assert s["a"] == 10
        assert s["b"] == 20

    def test_apply_delta_delete(self):
        s = State({"a": 1, "b": 2})
        s.apply_delta({"a": None})
        assert "a" not in s
        assert s["b"] == 2

    def test_iter(self):
        s = State({"x": 1, "y": 2})
        keys = set(iter(s))
        assert keys == {"x", "y"}

    def test_repr(self):
        s = State({"a": 1})
        assert "a" in repr(s)

    def test_prefixes(self):
        assert State.APP_PREFIX == "app:"
        assert State.USER_PREFIX == "user:"
        assert State.TEMP_PREFIX == "temp:"

    def test_scoped_keys(self):
        s = State()
        s["app:global_count"] = 100
        s["user:name"] = "Alice"
        s["temp:scratch"] = "tmp"
        s["local_key"] = "val"

        assert s["app:global_count"] == 100
        assert s["user:name"] == "Alice"
        assert s["temp:scratch"] == "tmp"
        assert s["local_key"] == "val"

        delta = s.commit_delta()
        assert len(delta) == 4

    def test_multiple_writes_same_key(self):
        s = State()
        s["x"] = 1
        s["x"] = 2
        s["x"] = 3
        assert s["x"] == 3
        delta = s.commit_delta()
        assert delta == {"x": 3}
