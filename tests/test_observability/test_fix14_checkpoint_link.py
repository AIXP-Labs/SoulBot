"""Fix 14 — ``pipeline.stage.resume`` span is linked back to the paused span.

When SoulBot resumes from a WAITING_USER checkpoint, the resume span should
carry an OTel ``Link(SpanContext)`` pointing at the saved (paused) span's
context. This lets trace viewers render the full trace even though the two
spans are in separate traces (resume may happen hours/days later).

Reference: Doc 12 v2.3 §9.2 test_fix14_checkpoint_link.
"""
from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Link, SpanContext, TraceFlags


def test_fix14_resume_span_carries_link():
    """Construct a resume span with a Link to a previously-saved context.

    We use a local TracerProvider to avoid global-state contention with other
    tests; the assertion only needs access to the finished span's ``links``.
    """
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test.resume")

    saved_trace_id = 0x0AF7651916CD43DD8448EB211C80319C
    saved_span_id = 0xB7AD6B7169203331

    link = Link(
        context=SpanContext(
            trace_id=saved_trace_id,
            span_id=saved_span_id,
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        ),
        attributes={"soulbot.link.kind": "checkpoint_resume"},
    )

    with tracer.start_as_current_span("pipeline.stage.resume", links=[link]):
        pass

    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    resume_span = spans[0]
    assert resume_span.name == "pipeline.stage.resume"
    assert len(resume_span.links) == 1

    got = resume_span.links[0]
    assert got.context.trace_id == saved_trace_id
    assert got.context.span_id == saved_span_id
    assert got.attributes["soulbot.link.kind"] == "checkpoint_resume"
    # SAMPLED flag must survive so downstream viewers render the link arrow
    assert got.context.trace_flags.sampled is True
