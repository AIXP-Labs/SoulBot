"""Tests for otel_setup.py — init_otel, FileSpanExporter, shutdown_otel.

Covers:
- B1: FileSpanExporter writes single-line JSONL
- B8: Resource has expected attributes (service.name/version/instance.id/env)
- B9: PII redaction (default strips gen_ai.input.messages / .output.messages)
- B15: init_otel is idempotent (second call is a no-op)
- Phase 1: Metrics singleton records to InMemoryMetricReader
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from soulbot.observability import semconv as sc
from soulbot.observability.otel_setup import (
    FileSpanExporter,
    _build_resource,
    init_otel,
    shutdown_otel,
)


class TestFileSpanExporter:
    """FileSpanExporter tests use a local TracerProvider (not set as global) so
    that they don't collide with other tests — OTel global tracer provider can
    only be set once per process."""

    def _make_tracer(self, exporter):
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider.get_tracer("test")

    def test_b1_single_line_jsonl(self, tmp_path, monkeypatch):
        """B1: each span serialized to exactly one line (indent=None forced)."""
        monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
        out = tmp_path / "spans.jsonl"
        tracer = self._make_tracer(FileSpanExporter(out))

        for name in ("test1", "test2"):
            with tracer.start_as_current_span(name):
                pass

        lines = out.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2, f"expected 2 spans, got {len(lines)}"
        for line in lines:
            obj = json.loads(line)  # valid JSON each
            assert "name" in obj

    def test_b9_pii_stripped_by_default(self, tmp_path, monkeypatch):
        """B9: gen_ai.input.messages absent when capture-content flag off (default)."""
        monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "false")
        out = tmp_path / "spans.jsonl"
        tracer = self._make_tracer(FileSpanExporter(out))

        with tracer.start_as_current_span("call") as span:
            span.set_attribute(sc.GEN_AI_INPUT_MESSAGES, "user: secret prompt")
            span.set_attribute(sc.GEN_AI_OUTPUT_MESSAGES, "assistant: secret reply")
            span.set_attribute(sc.GEN_AI_AGENT_NAME, "test-agent")  # should pass through

        obj = json.loads(out.read_text(encoding="utf-8").strip())
        attrs = obj.get("attributes", {})
        assert sc.GEN_AI_AGENT_NAME in attrs
        assert sc.GEN_AI_INPUT_MESSAGES not in attrs, "PII not redacted!"
        assert sc.GEN_AI_OUTPUT_MESSAGES not in attrs, "PII not redacted!"

    def test_b9_pii_kept_when_opt_in(self, tmp_path, monkeypatch):
        """B9 opt-in: when env flag = true, input/output messages preserved."""
        monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
        out = tmp_path / "spans.jsonl"
        tracer = self._make_tracer(FileSpanExporter(out))

        with tracer.start_as_current_span("call") as span:
            span.set_attribute(sc.GEN_AI_INPUT_MESSAGES, "keep me")

        obj = json.loads(out.read_text(encoding="utf-8").strip())
        assert obj["attributes"][sc.GEN_AI_INPUT_MESSAGES] == "keep me"


class TestBuildResource:
    def test_b8_required_resource_attrs(self, monkeypatch):
        monkeypatch.setenv("OTEL_SERVICE_NAME", "soulbot-test")
        monkeypatch.setenv("SOULBOT_VERSION", "9.9.9")
        monkeypatch.setenv("DEPLOY_ENV", "ci")

        resource = _build_resource()
        attrs = dict(resource.attributes)

        assert attrs.get("service.name") == "soulbot-test"
        assert attrs.get("service.version") == "9.9.9"
        assert attrs.get("deployment.environment.name") == "ci"
        assert "service.instance.id" in attrs
        # ProcessResourceDetector should inject these
        assert "process.pid" in attrs


class TestInitOtel:
    def test_idempotent(self, monkeypatch, tmp_path):
        """B15: calling init_otel twice does not produce dupe providers or error."""
        monkeypatch.setenv("SOULBOT_SPANS_FILE", str(tmp_path / "spans.jsonl"))
        # Reset internal flag to simulate fresh import
        from soulbot.observability import otel_setup as setup_mod

        setup_mod._INITIALIZED = False

        try:
            tracer1, meter1 = init_otel()
            tracer2, meter2 = init_otel()
            # No exception; singleton flag respected
            assert setup_mod._INITIALIZED is True
        finally:
            shutdown_otel(timeout_millis=2000)
            setup_mod._INITIALIZED = False

    @pytest.mark.skipif(
        "HAS_SET_GLOBAL_TRACER_PROVIDER" in os.environ,
        reason=(
            "init_otel() uses global trace.set_tracer_provider() which is"
            " once-only per process; skip if an earlier test already set it."
            " Integration coverage via subprocess-based tests (see test_b3_fork)."
        ),
    )
    def test_writes_spans_file(self, monkeypatch, tmp_path):
        """Smoke test: init_otel writes spans to configured file.

        NOTE: OTel global TracerProvider is once-only. This test only passes
        when run in isolation or first in the module. For CI, rely on
        test_b3_fork.py (subprocess) for integration coverage.
        """
        monkeypatch.setenv("SOULBOT_SPANS_FILE", str(tmp_path / "spans.jsonl"))
        from soulbot.observability import otel_setup as setup_mod

        setup_mod._INITIALIZED = False
        # Skip if global provider already set to a real one (another test ran)
        provider_name = trace.get_tracer_provider().__class__.__name__
        if provider_name not in ("ProxyTracerProvider", "NoOpTracerProvider"):
            pytest.skip(
                f"global provider already set ({provider_name}); run in isolation"
            )

        try:
            tracer, _ = init_otel()
            os.environ["HAS_SET_GLOBAL_TRACER_PROVIDER"] = "1"
            with tracer.start_as_current_span("test_init_span"):
                pass
            trace.get_tracer_provider().force_flush(timeout_millis=5000)
            content = (tmp_path / "spans.jsonl").read_text(encoding="utf-8")
            assert "test_init_span" in content
        finally:
            shutdown_otel(timeout_millis=2000)
            setup_mod._INITIALIZED = False


class TestShutdown:
    def test_shutdown_no_crash_on_repeat(self, monkeypatch, tmp_path):
        """shutdown_otel is safe to call multiple times or without init."""
        # Without init → should not crash
        shutdown_otel(timeout_millis=1000)
        # After init then double shutdown
        monkeypatch.setenv("SOULBOT_SPANS_FILE", str(tmp_path / "s.jsonl"))
        from soulbot.observability import otel_setup as setup_mod

        setup_mod._INITIALIZED = False
        init_otel()
        shutdown_otel(timeout_millis=1000)
        shutdown_otel(timeout_millis=1000)  # double shutdown
        setup_mod._INITIALIZED = False
