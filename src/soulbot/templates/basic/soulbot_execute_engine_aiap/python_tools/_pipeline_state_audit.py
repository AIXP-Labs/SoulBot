"""_pipeline_state_audit — shared persistent state for pipeline_node_* tools.

Each pipeline_node_* invocation is a fresh subprocess (Doc 19 design),
so in-memory state is lost between calls. This module persists:

  - retry_count[(aisop, node_name)] → int
      Used by node_audit_ended to decide audit_end:false vs degraded.
  - open_nodes[(aisop, node_name)] → {cache_path, opened_at}
      Used to fall back the cache_path when LLM omits it in node_ended.

Both live in a single JSON file under the agent data directory.

Also exposes ``append_span`` which writes one OTel-shaped span entry to
``data/_spans.jsonl`` so the SoulBot Web UI ``/observability`` view keeps
working without needing the SoulBot main process to mediate. Each tool
invocation writes a complete span (no streaming — subprocess cannot keep
an OTel session alive).

Resolution order for the data directory:
  1. SOULBOT_PIPELINE_STATE_DIR env var (test override)
  2. SOULBOT_AGENTS_DIR/data (set by agent.py at startup)
  3. ./data (final fallback, relative to cwd)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _state_dir() -> Path:
    env = os.environ.get("SOULBOT_PIPELINE_STATE_DIR")
    if env:
        return Path(env)
    agents_dir = os.environ.get("SOULBOT_AGENTS_DIR")
    if agents_dir:
        return Path(agents_dir) / "data"
    return Path("data")


def _state_file() -> Path:
    p = _state_dir() / "_pipeline_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _spans_file() -> Path:
    return _state_dir() / "_spans.jsonl"


# ---------------------------------------------------------------------------
# State IO (atomic write via .tmp + replace)
# ---------------------------------------------------------------------------


def _read_state() -> dict:
    f = _state_file()
    if not f.exists():
        return {"retry_count": {}, "open_nodes": {}}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"retry_count": {}, "open_nodes": {}}


def _write_state(state: dict) -> None:
    target = _state_file()
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(target)


def _key(aisop: str, node_name: str) -> str:
    return f"{aisop}::{node_name}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def open_node_state(
    aisop: str,
    node_name: str,
    cache_path: str,
    audit_id: str = "",
) -> None:
    """Mark (aisop, node_name) as in-flight with its cache_path + audit_id."""
    state = _read_state()
    state["open_nodes"][_key(aisop, node_name)] = {
        "cache_path": cache_path,
        "opened_at": time.time(),
        "audit_id": audit_id,
    }
    _write_state(state)


def close_node_state(aisop: str, node_name: str) -> None:
    """Drop the in-flight record (called on success/degraded/aborted)."""
    state = _read_state()
    state["open_nodes"].pop(_key(aisop, node_name), None)
    _write_state(state)


def get_open_cache_path(aisop: str, node_name: str) -> str:
    """Return the cache_path captured by node_started, or "" if none."""
    entry = _read_state()["open_nodes"].get(_key(aisop, node_name))
    return entry.get("cache_path", "") if entry else ""


def get_opened_at(aisop: str, node_name: str) -> float:
    """Return the opened_at epoch captured by node_started, or 0.0 if none."""
    entry = _read_state()["open_nodes"].get(_key(aisop, node_name))
    return entry.get("opened_at", 0.0) if entry else 0.0


def get_audit_id(aisop: str, node_name: str) -> str:
    """Return the audit_id captured by node_started, or "" if none."""
    entry = _read_state()["open_nodes"].get(_key(aisop, node_name))
    return entry.get("audit_id", "") if entry else ""


def is_node_open(aisop: str, node_name: str) -> bool:
    """Return True iff node_started was called (and not yet closed)."""
    return _key(aisop, node_name) in _read_state()["open_nodes"]


def get_retry_count(aisop: str, node_name: str) -> int:
    """Return number of audit_end:false responses already returned."""
    return _read_state()["retry_count"].get(_key(aisop, node_name), 0)


def increment_retry(aisop: str, node_name: str) -> int:
    """Bump retry counter; return new value."""
    state = _read_state()
    k = _key(aisop, node_name)
    state["retry_count"][k] = state["retry_count"].get(k, 0) + 1
    _write_state(state)
    return state["retry_count"][k]


def clear_retry(aisop: str, node_name: str) -> None:
    """Reset retry counter (called on success/degraded/aborted)."""
    state = _read_state()
    state["retry_count"].pop(_key(aisop, node_name), None)
    _write_state(state)


def reset_all_state() -> None:
    """Wipe the entire state file. Test helper / session-start cleanup."""
    f = _state_file()
    if f.exists():
        f.unlink()


# ---------------------------------------------------------------------------
# W3C trace context (Doc 22 P1 — dual channel: CLI arg + env var fallback)
# ---------------------------------------------------------------------------


def _parse_traceparent(tp: str) -> tuple[str | None, str | None]:
    """Parse W3C traceparent → (trace_id, parent_span_id).

    Format: ``version-trace_id(32 hex)-parent_id(16 hex)-flags``
    Example: ``00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01``

    Returns ``("0x...", "0x...")`` on success, ``(None, None)`` if the
    input is missing or malformed (invalid format is tolerated silently
    so child-span writing never fails due to header corruption).
    """
    if not tp or tp.count("-") != 3:
        return None, None
    parts = tp.split("-")
    if len(parts[1]) != 32 or len(parts[2]) != 16:
        return None, None
    try:
        int(parts[1], 16)
        int(parts[2], 16)
    except ValueError:
        return None, None
    return f"0x{parts[1]}", f"0x{parts[2]}"


def resolve_trace_context(cli_arg: str = "") -> tuple[str | None, str | None]:
    """Resolution order for trace context (higher priority wins):

    1. CLI arg ``--traceparent=<value>`` (preferred when env whitelist
       is active; see test_pipeline_tools.py:_run which sets env={...}
       and would otherwise strip TRACEPARENT)
    2. ``os.environ.get("TRACEPARENT")`` (default when Bash Tool inherits
       parent env)
    3. ``(None, None)`` — span falls back to independent UUID trace_id
       (pre-Doc 22 behaviour, backward compatible)
    """
    tp = cli_arg or os.environ.get("TRACEPARENT", "")
    return _parse_traceparent(tp)


# ---------------------------------------------------------------------------
# OTel span output (jsonl append, OTel SDK not required)
# ---------------------------------------------------------------------------


def append_span(
    *,
    name: str,
    attributes: dict[str, Any],
    status: str = "OK",
    description: str = "",
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    start_time_ns: int | None = None,
) -> None:
    """Append one span entry to data/_spans.jsonl.

    Format mirrors the OTel BatchSpanProcessor JSON output enough for the
    Web UI ``/observability`` view to render. end_time is always "now";
    start_time defaults to "now" (point-event) but can be set via
    *start_time_ns* to record an interval span (e.g. node_audit_ended
    passes the opened_at timestamp so Web UI shows real node duration).

    If *trace_id* / *parent_span_id* are provided (typically from W3C
    traceparent via CLI arg or env var — see ``resolve_trace_context``),
    the span will link into the caller's trace tree. Otherwise a fresh
    random UUID trace_id is generated (backward-compatible behaviour).
    """
    end_ns = int(time.time() * 1e9)
    start_ns = start_time_ns if start_time_ns is not None else end_ns
    tid = trace_id or f"0x{uuid.uuid4().hex}"
    sid = f"0x{uuid.uuid4().hex[:16]}"
    entry = {
        "name": name,
        "context": {
            "trace_id": tid,
            "span_id": sid,
            "trace_state": "[]",
        },
        "parent_id": parent_span_id,
        "kind": "SpanKind.INTERNAL",
        "start_time": _iso_from_ns(start_ns),
        "end_time": _iso_from_ns(end_ns),
        "status": {"status_code": status, "description": description},
        "attributes": attributes,
        "events": [],
        "links": [],
        "resource": {
            "attributes": {
                "service.name": "soulbot",
                "service.namespace": "pipeline_tool",
            },
        },
    }
    f = _spans_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _iso_from_ns(ns: int) -> str:
    """Convert nanosecond epoch to ISO-8601 UTC string."""
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Independent audit cache (human-auditable dual-source of truth)
# ---------------------------------------------------------------------------


def append_audit_record(
    cache_path: str,
    *,
    audit_id: str,
    aisop: str,
    node_name: str,
    opened_at: float,
    verdict: str,
    cache_exists_at_end: bool = False,
    retry_count_final: int = 0,
    reason: str = "",
) -> None:
    """Append a node audit record to the turn-level ``audit.json``.

    This is the **Python-authored** audit file — kept separate from the
    LLM-authored node cache (``{AIAP}.{Node}.json``) so humans can
    diff the two to detect LLM fabrication.

    File location: single ``audit.json`` file per turn, sibling to the
    node cache files. E.g. ``.execution_cache/151/audit.json`` contains
    one entry per node (``nodes["Perceive"]``, ``nodes["Attention"]``, ...).

    Write protocol: read existing ``audit.json`` (tolerate missing/corrupt),
    merge ``nodes[node_name] = <record>``, then atomic tmp+rename write.

    Concurrency: normal_engine runs nodes sequentially so read-modify-write
    is race-free. If future node_engine emits in parallel, this function
    will need a file lock.

    Best-effort: any exception is swallowed so this never blocks the
    audit_end / audit_aborted response returned to the LLM.
    """
    if not cache_path:
        return
    try:
        turn_dir = Path(cache_path).parent
        audit_path = turn_dir / "audit.json"
        now = time.time()
        duration_ms = (
            int((now - opened_at) * 1000) if opened_at else 0
        )
        record = {
            "audit_id": audit_id,
            "cache_path": cache_path,
            # machine-readable (epoch seconds, float)
            "opened_at": opened_at,
            "closed_at": now,
            # human-readable ISO 8601 UTC (same format as _spans.jsonl)
            "audit_start_time": (
                _iso_from_ns(int(opened_at * 1e9)) if opened_at else ""
            ),
            "audit_end_time": _iso_from_ns(int(now * 1e9)),
            "duration_ms": duration_ms,
            "verdict": verdict,
            "cache_exists_at_end": cache_exists_at_end,
            "retry_count_final": retry_count_final,
        }
        if reason:
            record["reason"] = reason

        # Read existing turn-level audit.json (tolerate missing / corrupt)
        if audit_path.exists():
            try:
                data = json.loads(audit_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    data = {}
            except Exception:
                data = {}
        else:
            data = {}
        data.setdefault("turn_id", turn_dir.name)
        data.setdefault("aisop", aisop)
        data.setdefault("cache_dir", str(turn_dir))
        nodes = data.setdefault("nodes", {})
        if not isinstance(nodes, dict):
            nodes = {}
            data["nodes"] = nodes
        nodes[node_name] = record

        # Atomic write
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = audit_path.with_name(audit_path.name + ".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(audit_path)
    except Exception:
        # best-effort: metadata failure must not block audit_end response
        pass


# Backward-compat alias (older callers will be migrated)
write_audit_cache = append_audit_record
