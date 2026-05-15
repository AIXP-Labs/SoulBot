"""Fix 15: record_speaker_selection writes a span with candidate events.

Because OTel's global TracerProvider may already be set by a prior test, we
verify behavior by introspecting the OTel tracer the helper binds to (via
monkeypatching ``selection._tracer``) rather than through global exporters.
"""
from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from soulbot.observability import selection as sel_mod
from soulbot.observability.selection import record_speaker_selection


def _swap_tracer(monkeypatch):
    """Swap selection._tracer with a local one bound to an InMemorySpanExporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.selection")
    monkeypatch.setattr(sel_mod, "_tracer", tracer)
    monkeypatch.setattr(sel_mod, "_OTEL_AVAILABLE", True)
    return exporter


def test_records_winner_and_candidates(monkeypatch):
    exporter = _swap_tracer(monkeypatch)

    record_speaker_selection(
        candidates=[
            {"name": "alice", "score": 0.9, "reason": "highest expertise"},
            {"name": "bob", "score": 0.5, "reason": "tiebreaker"},
        ],
        winner="alice",
        strategy="highest_score",
        round_index=3,
        coordinator="moderator",
    )

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    s = spans[0]
    assert s.name == "speaker_selection"
    assert s.attributes["gen_ai.operation.name"] == "speaker_selection"
    assert s.attributes["gen_ai.agent.name"] == "moderator"
    assert s.attributes["soulbot.selection.winner"] == "alice"
    assert s.attributes["soulbot.selection.strategy"] == "highest_score"
    assert s.attributes["soulbot.selection.round_index"] == 3

    candidate_events = [e for e in s.events if e.name == "candidate"]
    assert len(candidate_events) == 2
    names = {e.attributes["soulbot.candidate.name"] for e in candidate_events}
    assert names == {"alice", "bob"}


def test_caps_candidates_at_10(monkeypatch):
    exporter = _swap_tracer(monkeypatch)

    record_speaker_selection(
        candidates=[{"name": f"agent_{i}", "score": float(i)} for i in range(25)],
        winner="agent_0",
        strategy="round_robin",
        round_index=0,
        coordinator="mod",
    )

    spans = exporter.get_finished_spans()
    candidate_events = [e for e in spans[0].events if e.name == "candidate"]
    assert len(candidate_events) == 10


def test_noop_when_otel_unavailable(monkeypatch):
    """Soft-fail: if _OTEL_AVAILABLE=False, helper must not raise."""
    monkeypatch.setattr(sel_mod, "_OTEL_AVAILABLE", False)
    # Should return without calling _tracer (which is None)
    record_speaker_selection(
        candidates=[{"name": "x", "score": 1.0}],
        winner="x",
        strategy="s",
        round_index=0,
        coordinator="c",
    )


def test_reason_truncated_to_100_chars(monkeypatch):
    exporter = _swap_tracer(monkeypatch)
    long_reason = "x" * 200

    record_speaker_selection(
        candidates=[{"name": "a", "score": 1.0, "reason": long_reason}],
        winner="a",
        strategy="s",
        round_index=0,
        coordinator="c",
    )

    ev = [e for e in exporter.get_finished_spans()[0].events if e.name == "candidate"][0]
    assert len(ev.attributes["soulbot.candidate.reason"]) == 100
