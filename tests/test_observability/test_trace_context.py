"""Tests for trace_context.py — W3C helpers + inject/extract round-trip.

Covers:
- parse / build traceparent format
- new_trace_id / new_span_id length + hex
- inject_current under an active span writes a parseable traceparent
- extract_to_context round-trips: span inside extracted context shares trace_id
"""
from __future__ import annotations

import re

from opentelemetry import context as otel_context
from opentelemetry import trace

from soulbot.observability.trace_context import (
    build_traceparent,
    extract_to_context,
    inject_current,
    new_span_id,
    new_trace_id,
    parse_traceparent,
)


class TestFormatHelpers:
    def test_new_trace_id_is_32_hex(self):
        tid = new_trace_id()
        assert len(tid) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", tid)

    def test_new_span_id_is_16_hex(self):
        sid = new_span_id()
        assert len(sid) == 16
        assert re.fullmatch(r"[0-9a-f]{16}", sid)

    def test_build_and_parse_roundtrip(self):
        tid = "a" * 32
        sid = "b" * 16
        tp = build_traceparent(tid, sid, sampled=True)
        assert tp == f"00-{tid}-{sid}-01"
        parsed = parse_traceparent(tp)
        assert parsed == ("00", tid, sid, "01")

    def test_build_not_sampled(self):
        tp = build_traceparent("c" * 32, "d" * 16, sampled=False)
        assert tp.endswith("-00")

    def test_parse_rejects_malformed(self):
        assert parse_traceparent("not-a-traceparent") is None
        assert parse_traceparent("") is None
        # Wrong lengths
        assert parse_traceparent("00-abc-def-01") is None

    def test_parse_strips_whitespace(self):
        tp = f"  00-{'a'*32}-{'b'*16}-01  "
        assert parse_traceparent(tp) is not None


class TestInjectExtract:
    """Fix 8/12: round-trip OTel context through envelope carrier."""

    def test_inject_under_active_span(self, otel_trace):
        """inject_current inside a live span must produce a valid traceparent."""
        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("parent"):
            carrier = inject_current()

        assert "traceparent" in carrier, carrier
        parsed = parse_traceparent(carrier["traceparent"])
        assert parsed is not None, carrier["traceparent"]
        # Parent span trace_id should match the one in traceparent
        # (traceparent format: 00-<trace_id>-<span_id>-<flags>)
        _, tid, sid, _ = parsed
        assert len(tid) == 32
        assert len(sid) == 16

    def test_extract_restores_trace_id(self, otel_trace):
        """Envelope carrier → extract → new span shares trace_id with original."""
        tracer = trace.get_tracer("test")

        # Originating side
        with tracer.start_as_current_span("originator") as origin_span:
            origin_trace_id = origin_span.get_span_context().trace_id
            carrier: dict = {}
            inject_current(carrier)

        # Consumer side: extract into a fresh context, start span under it
        ctx = extract_to_context(carrier)
        token = otel_context.attach(ctx)
        try:
            with tracer.start_as_current_span("consumer") as consumer_span:
                consumer_trace_id = consumer_span.get_span_context().trace_id
        finally:
            otel_context.detach(token)

        assert consumer_trace_id == origin_trace_id, (
            "consumer span did not inherit trace_id from envelope"
        )

    def test_empty_carrier_yields_root_context(self):
        """extract_to_context on empty dict produces a usable Context."""
        ctx = extract_to_context({})
        # Context is a Context-like object; attach + detach should not raise
        token = otel_context.attach(ctx)
        otel_context.detach(token)
