"""Fix 12: baggage (user_id / session_id) survives envelope round-trip.

OTel `baggage` carries key-value hints across context boundaries separately
from span data. Doc 12 v2.3 §7.1 relies on the W3CBaggagePropagator (already
wired into trace_context.inject_current / extract_to_context) rather than a
homegrown baggage module — this test verifies the round-trip works.
"""
from __future__ import annotations

from opentelemetry import baggage
from opentelemetry import context as otel_context

from soulbot.observability.trace_context import extract_to_context, inject_current


def test_baggage_roundtrip_via_carrier():
    """Set baggage → inject → extract → baggage values still present."""
    # Producer side: attach a context containing baggage
    ctx = baggage.set_baggage("user_id", "u-42")
    ctx = baggage.set_baggage("session_id", "s-7", context=ctx)
    token = otel_context.attach(ctx)
    try:
        carrier: dict = {}
        inject_current(carrier)
    finally:
        otel_context.detach(token)

    assert "baggage" in carrier, f"baggage header missing: {carrier}"
    assert "user_id=u-42" in carrier["baggage"]
    assert "session_id=s-7" in carrier["baggage"]

    # Consumer side: extract carrier → read baggage back
    new_ctx = extract_to_context(carrier)
    assert baggage.get_baggage("user_id", context=new_ctx) == "u-42"
    assert baggage.get_baggage("session_id", context=new_ctx) == "s-7"


def test_baggage_absent_carrier_returns_none():
    ctx = extract_to_context({})
    assert baggage.get_baggage("user_id", context=ctx) is None
