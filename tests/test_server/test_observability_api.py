"""Tests for /observability/* endpoints (Doc 16 Plan B Step 1).

Covers:
- GET /observability/health (file missing / empty / populated)
- GET /observability/traces (filter by status + limit)
- GET /observability/spans/{trace_id} (404 for unknown, sorted by start_time)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from soulbot.server.api_server import create_app


def _span(*, trace_id: str, span_id: str, name: str = "demo",
          start_ns: int = 1_000_000_000, duration_ns: int = 100_000_000,
          status: str = "OK", parent_id: str | None = None,
          attrs: dict | None = None, events: list | None = None) -> dict:
    return {
        "name": name,
        "context": {"trace_id": trace_id, "span_id": span_id},
        "parent_id": parent_id,
        "start_time": start_ns,
        "end_time": start_ns + duration_ns,
        "status": {"status_code": status, "description": ""},
        "attributes": attrs or {},
        "events": events or [],
    }


@pytest.fixture
def agents_dir(tmp_path: Path) -> Path:
    """Mimic real layout: tmp_path/data/_spans.jsonl + minimal agent."""
    (tmp_path / "data").mkdir()
    agent_dir = tmp_path / "demo_agent"
    agent_dir.mkdir()
    (agent_dir / "agent.py").write_text(
        'from soulbot.agents import LlmAgent\n'
        'root_agent = LlmAgent(name="demo_agent", model="test")\n',
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def client(agents_dir: Path) -> TestClient:
    app = create_app(agents_dir=agents_dir)
    return TestClient(app)


def _write_spans(agents_dir: Path, spans: list[dict]) -> Path:
    spans_file = agents_dir / "data" / "_spans.jsonl"
    spans_file.write_text(
        "\n".join(json.dumps(s) for s in spans) + "\n",
        encoding="utf-8",
    )
    return spans_file


# --- /observability/health ----------------------------------------------

class TestObservabilityHealth:
    def test_no_spans_file(self, client: TestClient):
        resp = client.get("/observability/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["exists"] is False
        assert "spans_file" in body

    def test_with_spans(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id="t1", span_id="s1"),
            _span(trace_id="t1", span_id="s2", parent_id="s1"),
            _span(trace_id="t2", span_id="s3"),
        ])
        resp = client.get("/observability/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["exists"] is True
        assert body["span_count"] == 3
        assert body["trace_count"] == 2
        assert body["size_bytes"] > 0


# --- /observability/traces ----------------------------------------------

class TestObservabilityTraces:
    def test_empty_when_no_file(self, client: TestClient):
        resp = client.get("/observability/traces")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_aggregates_by_trace_id(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id="t1", span_id="root", name="invoke_agent",
                  attrs={"gen_ai.agent.name": "demo_agent",
                         "gen_ai.request.model": "claude-acp/sonnet-4.5"}),
            _span(trace_id="t1", span_id="child", parent_id="root",
                  name="command msg.send"),
            _span(trace_id="t2", span_id="other", name="invoke_agent"),
        ])
        resp = client.get("/observability/traces")
        traces = resp.json()
        assert len(traces) == 2
        t1 = next(t for t in traces if t["trace_id"] == "t1")
        assert t1["span_count"] == 2
        assert t1["root_name"] == "invoke_agent"
        assert "demo_agent" in t1["agents"]
        assert "claude-acp/sonnet-4.5" in t1["models"]

    def test_filter_by_status_error(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id="t-ok", span_id="s1", status="OK"),
            _span(trace_id="t-err", span_id="s2", status="ERROR"),
        ])
        resp = client.get("/observability/traces?status=ERROR")
        traces = resp.json()
        assert len(traces) == 1
        assert traces[0]["trace_id"] == "t-err"
        assert traces[0]["has_error"] is True

    def test_filter_by_status_ok(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id="t-ok", span_id="s1", status="OK"),
            _span(trace_id="t-err", span_id="s2", status="ERROR"),
        ])
        resp = client.get("/observability/traces?status=OK")
        traces = resp.json()
        assert len(traces) == 1
        assert traces[0]["trace_id"] == "t-ok"

    def test_limit(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id=f"t{i}", span_id=f"s{i}",
                  start_ns=1_000_000_000 + i * 1000)
            for i in range(20)
        ])
        resp = client.get("/observability/traces?limit=5")
        assert len(resp.json()) == 5


# --- /observability/spans/{trace_id} ------------------------------------

class TestObservabilitySpansByTrace:
    def test_404_when_no_file(self, client: TestClient):
        resp = client.get("/observability/spans/nonexistent")
        assert resp.status_code == 404

    def test_404_unknown_trace(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [_span(trace_id="t1", span_id="s1")])
        resp = client.get("/observability/spans/unknown")
        assert resp.status_code == 404

    def test_returns_sorted_by_start_time(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id="t1", span_id="b", start_ns=2_000_000_000),
            _span(trace_id="t1", span_id="a", start_ns=1_000_000_000),
            _span(trace_id="t1", span_id="c", start_ns=3_000_000_000),
            _span(trace_id="other", span_id="x"),
        ])
        resp = client.get("/observability/spans/t1")
        spans = resp.json()
        assert len(spans) == 3
        assert [s["context"]["span_id"] for s in spans] == ["a", "b", "c"]

    def test_returns_events_intact(self, client: TestClient, agents_dir: Path):
        _write_spans(agents_dir, [
            _span(trace_id="t1", span_id="s1", events=[
                {"name": "security.injection.suspected",
                 "attributes": {"soulbot.security.preview": "..."}},
            ]),
        ])
        resp = client.get("/observability/spans/t1")
        spans = resp.json()
        assert spans[0]["events"][0]["name"] == "security.injection.suspected"
