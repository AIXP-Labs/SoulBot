"""Fixtures for observability tests.

Provides InMemorySpanExporter + InMemoryMetricReader that let tests assert
span attributes / metric data points directly without writing to disk.

Reference: Doc 12 v2.3 §9.1
"""
from __future__ import annotations

import os

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

# v2.3 C5: use long path (official), short `from opentelemetry.sdk.trace.export
# import InMemorySpanExporter` re-export is not guaranteed across SDK versions.
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def otel_env(monkeypatch):
    """Isolate OTel env vars per test.

    Default: capture-content=false (PII redaction ON, as in production).
    Tests needing content can override explicitly.
    """
    monkeypatch.setenv("SOULBOT_SAMPLE_RATE", "1.0")
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    yield


@pytest.fixture
def otel_trace(otel_env):
    """InMemorySpanExporter + SimpleSpanProcessor (synchronous, no batching)."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    yield exporter
    exporter.clear()


@pytest.fixture
def otel_metric(otel_env, monkeypatch):
    """InMemoryMetricReader for histogram assertions.

    OTel's global MeterProvider is once-only per process. Once any earlier
    test called ``init_otel`` / ``set_meter_provider``, calling it again is
    silently ignored. Instead of fighting that, we build a local
    MeterProvider + InMemoryMetricReader, create the 4 histograms directly
    on it, and monkey-patch ``get_llm_histograms`` to return those — so
    code under test (``acp_llm.py``) records into this provider even though
    the global stays unchanged.
    """
    reader = InMemoryMetricReader()
    provider = MeterProvider(
        resource=Resource.create({"service.name": "test"}),
        metric_readers=[reader],
    )
    meter = provider.get_meter("soulbot.llm.test")

    from soulbot.observability import metrics as soulbot_metrics
    from soulbot.observability import semconv as sc

    hists = soulbot_metrics.LLMHistograms(
        duration=meter.create_histogram(
            name=sc.METRIC_OPERATION_DURATION, unit="s", description="test"
        ),
        estimated_token_usage=meter.create_histogram(
            name=sc.METRIC_ESTIMATED_TOKEN_USAGE, unit="{token}", description="test"
        ),
        acp_subprocess_ttft=meter.create_histogram(
            name=sc.METRIC_ACP_SUBPROCESS_TTFT, unit="s", description="test"
        ),
        acp_pool_queue_time=meter.create_histogram(
            name=sc.METRIC_ACP_POOL_QUEUE_TIME, unit="s", description="test"
        ),
    )
    monkeypatch.setattr(
        soulbot_metrics, "get_llm_histograms", lambda: hists
    )
    # Also patch the import used by acp_llm (it does
    # `from ..observability.metrics import get_llm_histograms`, so the name
    # is already bound in acp_llm's module globals).
    from soulbot.models import acp_llm as acp_mod
    monkeypatch.setattr(acp_mod, "get_llm_histograms", lambda: hists)

    yield reader


# --- Phase 5 fixtures -----------------------------------------------------

@pytest.fixture
def captured_spans(otel_env):
    """Attach an InMemorySpanExporter to whatever TracerProvider is current.

    Works even when the OTel global TracerProvider was set by an earlier test
    (``init_otel``) — instead of trying to override the provider (which is
    once-only per process), we add another SpanProcessor alongside the
    existing ones so every span is duplicated into our in-memory buffer.
    """
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        # Still proxy / noop: install a real one so we can attach processors.
        provider = TracerProvider(resource=Resource.create({"service.name": "test"}))
        trace.set_tracer_provider(provider)

    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    try:
        yield exporter
    finally:
        # SDK does not expose a public "remove" API; clear exporter to avoid
        # cross-test bleed. The attached processor sticks around for the rest
        # of the test process, but it only writes to this now-cleared buffer.
        exporter.clear()


# --- Fake ACP pool (mocks soulacp.ACPConnectionPool) ---------------------

import asyncio as _asyncio  # noqa: E402
from contextlib import asynccontextmanager as _asynccontextmanager  # noqa: E402


class _FakeACPConfig:
    """Minimal stand-in for soulacp.ACPConfig used by ACPLlm retry logic."""

    max_retries = 3
    retry_base_delay = 0.01
    provider = "claude"
    enable_fallback = False


class _FakeClient:
    """Stand-in for soulacp client — supports query() + query_stream()."""

    def __init__(
        self,
        response: str = "hello world",
        stream_chunks: list[str] | None = None,
        first_chunk_delay_s: float = 0.01,
    ):
        self.response = response
        self.stream_chunks = stream_chunks or ["hello ", "world"]
        self.first_chunk_delay_s = first_chunk_delay_s

    async def query(self, prompt: str) -> str:
        return self.response

    async def query_stream(self, prompt: str):
        for i, chunk in enumerate(self.stream_chunks):
            if i == 0:
                await _asyncio.sleep(self.first_chunk_delay_s)
            yield chunk


class _FakePool:
    """Stand-in for soulacp.ACPConnectionPool — controls acquire() semantics."""

    def __init__(
        self,
        client: _FakeClient | None = None,
        sid: str = "session-fake-123",
        fail_first_n: int = 0,
        rotate_to_sid: str | None = None,
    ):
        self.client = client or _FakeClient()
        self.sid = sid
        self.fail_first_n = fail_first_n
        self.rotate_to_sid = rotate_to_sid
        self._config = _FakeACPConfig()
        self.acquire_calls = 0

    def acquire(self, session_id=None):
        pool = self

        @_asynccontextmanager
        async def _cm():
            pool.acquire_calls += 1
            if pool.acquire_calls <= pool.fail_first_n:
                raise ConnectionError(f"fake failure {pool.acquire_calls}")
            # Session rotation: return a different sid than the caller asked for
            returned_sid = (
                pool.rotate_to_sid
                if (pool.rotate_to_sid and session_id and session_id != pool.rotate_to_sid)
                else pool.sid
            )
            yield (pool.client, returned_sid)

        return _cm()


@pytest.fixture
def fake_acp_pool(monkeypatch):
    """Patch ACPLlm._get_pool + _get_config to return controllable fakes."""
    from soulbot.models import acp_llm as acp_mod

    pool = _FakePool()
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_pool", lambda self: pool)
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_config", lambda self: _FakeACPConfig())
    return pool


@pytest.fixture
def fake_acp_streaming(monkeypatch):
    """Like fake_acp_pool but configured for streaming (first_chunk_delay > 0)."""
    from soulbot.models import acp_llm as acp_mod

    pool = _FakePool(
        client=_FakeClient(
            stream_chunks=["Hel", "lo ", "world!"],
            first_chunk_delay_s=0.02,
        )
    )
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_pool", lambda self: pool)
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_config", lambda self: _FakeACPConfig())
    return pool


@pytest.fixture
def fake_acp_pool_flaky(monkeypatch):
    """First acquire raises ConnectionError → retry path triggers."""
    from soulbot.models import acp_llm as acp_mod

    pool = _FakePool(fail_first_n=1)
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_pool", lambda self: pool)
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_config", lambda self: _FakeACPConfig())
    return pool


@pytest.fixture
def fake_acp_pool_rotating(monkeypatch):
    """Pool returns sid different from requested → session.rotated event."""
    from soulbot.models import acp_llm as acp_mod

    pool = _FakePool(sid="new-session", rotate_to_sid="new-session")
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_pool", lambda self: pool)
    monkeypatch.setattr(acp_mod.ACPLlm, "_get_config", lambda self: _FakeACPConfig())
    return pool
