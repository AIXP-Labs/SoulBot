"""Fixtures for runner tests.

Mirrors the ``captured_spans`` fixture from tests/test_observability/conftest.py
so Doc 22 P3 per-turn span tests can attach an InMemorySpanExporter.
"""
from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def otel_env(monkeypatch):
    monkeypatch.setenv("SOULBOT_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    yield


@pytest.fixture
def captured_spans(otel_env):
    """Attach an InMemorySpanExporter to the current TracerProvider.

    Mirrors tests/test_observability/conftest.py::captured_spans — adds a
    SpanProcessor alongside existing ones since the OTel global provider
    is once-only per process.
    """
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
        trace.set_tracer_provider(provider)

    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    try:
        yield exporter
    finally:
        exporter.clear()
