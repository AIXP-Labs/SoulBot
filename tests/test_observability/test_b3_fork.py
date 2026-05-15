"""Test B3 — fork-safety: child process after fork must re-init TracerProvider
and flush spans to its own _spans.jsonl.

Skipped on Windows (os.register_at_fork unavailable).

Reference: Doc 12 v2.3 §2 Phase 0 B3
"""
from __future__ import annotations

import os
import sys
import time

import pytest


@pytest.mark.skipif(
    not hasattr(os, "register_at_fork"),
    reason="os.register_at_fork unavailable (Windows)",
)
def test_b3_post_fork_reinit(tmp_path, monkeypatch):
    """Child process spans must land in _spans.jsonl after fork."""
    spans_file = tmp_path / "spans.jsonl"
    monkeypatch.setenv("SOULBOT_SPANS_FILE", str(spans_file))

    from opentelemetry import trace

    from soulbot.observability import otel_setup as setup_mod

    setup_mod._INITIALIZED = False
    tracer, _ = setup_mod.init_otel()

    # Parent writes a span first
    with tracer.start_as_current_span("parent_span"):
        pass

    pid = os.fork()
    if pid == 0:
        # Child: write a span and shutdown to flush
        try:
            tracer_c = trace.get_tracer("child")
            with tracer_c.start_as_current_span("child_span"):
                pass
            setup_mod.shutdown_otel(timeout_millis=5000)
        finally:
            os._exit(0)

    # Parent waits
    _, status = os.waitpid(pid, 0)
    assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0

    # Allow a moment for file flush
    time.sleep(0.5)
    setup_mod.shutdown_otel(timeout_millis=5000)
    setup_mod._INITIALIZED = False

    content = spans_file.read_text(encoding="utf-8")
    assert "parent_span" in content, "parent span missing"
    assert "child_span" in content, "child span missing — fork re-init failed!"
