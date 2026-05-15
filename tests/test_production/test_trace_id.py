"""Tests for trace ID generation — auto-generate and passthrough."""

import pytest

from soulbot.server.middleware import generate_trace_id


class TestTraceId:
    def test_auto_generate(self):
        tid = generate_trace_id(None)
        assert len(tid) == 8
        # Should be hex characters
        int(tid, 16)

    def test_passthrough(self):
        tid = generate_trace_id("my-trace-123")
        assert tid == "my-trace-123"

    def test_empty_string_generates_new(self):
        tid = generate_trace_id("")
        assert len(tid) == 8

    def test_unique(self):
        ids = {generate_trace_id(None) for _ in range(100)}
        assert len(ids) == 100

    def test_preserves_custom_format(self):
        tid = generate_trace_id("req-abc-def")
        assert tid == "req-abc-def"
