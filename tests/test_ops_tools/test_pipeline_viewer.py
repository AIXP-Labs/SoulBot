"""Fix 4 — HTML viewer tests."""
from __future__ import annotations

import json

from tools.pipeline_viewer import (
    parse_spans_jsonl,
    render_file,
    render_html,
)


def _span(
    *,
    name: str = "invoke_agent",
    trace_id: str = "abc123",
    status: str = "OK",
    duration_ms: float = 120.0,
    ttft: float | None = None,
    output_tokens: int | None = None,
    model: str = "claude-acp/sonnet-4.5",
) -> dict:
    start_ns = 1_000_000_000
    end_ns = start_ns + int(duration_ms * 1e6)
    attrs = {
        "gen_ai.request.model": model,
        "gen_ai.provider.name": "anthropic",
        "acp.provider.name": "claude",
    }
    if ttft is not None:
        attrs["gen_ai.server.time_to_first_token"] = ttft
    if output_tokens is not None:
        attrs["gen_ai.usage.output_tokens"] = output_tokens
    return {
        "name": name,
        "context": {"trace_id": trace_id, "span_id": "s1"},
        "start_time": start_ns,
        "end_time": end_ns,
        "status": {"status_code": status, "description": ""},
        "attributes": attrs,
        "events": [],
    }


def test_parse_skips_malformed_lines(tmp_path):
    p = tmp_path / "_spans.jsonl"
    p.write_text(
        json.dumps(_span()) + "\n"
        + "{not json}\n"
        + "\n"
        + json.dumps(_span(name="second")) + "\n",
        encoding="utf-8",
    )
    spans = parse_spans_jsonl(p)
    assert len(spans) == 2
    assert spans[0]["name"] == "invoke_agent"
    assert spans[1]["name"] == "second"


def test_render_html_groups_by_trace():
    spans = [
        _span(trace_id="t1"),
        _span(trace_id="t1", name="child"),
        _span(trace_id="t2"),
    ]
    html_text = render_html(spans)
    assert "2 trace(s)" in html_text
    assert "t1" in html_text and "t2" in html_text
    assert "child" in html_text


def test_render_html_shows_ttft_and_tpot():
    spans = [_span(ttft=0.05, output_tokens=100, duration_ms=250.0)]
    html_text = render_html(spans)
    # TTFT column shows seconds with 3 decimals
    assert "0.050" in html_text
    # TPOT ≈ (250 - 50) / 100 = 2.0 ms/tok
    assert "2.0" in html_text


def test_render_html_error_class():
    spans = [_span(status="ERROR")]
    html_text = render_html(spans)
    assert 'class="err"' in html_text


def test_render_html_no_ttft_shows_dash():
    spans = [_span()]
    html_text = render_html(spans)
    # At least one "-" placeholder for TTFT
    assert "<td>-</td>" in html_text


def test_render_file_roundtrip(tmp_path):
    input_path = tmp_path / "_spans.jsonl"
    output_path = tmp_path / "out.html"
    input_path.write_text(json.dumps(_span()) + "\n", encoding="utf-8")
    render_file(input_path, output_path)
    assert output_path.exists()
    content = output_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in content
    assert "invoke_agent" in content
