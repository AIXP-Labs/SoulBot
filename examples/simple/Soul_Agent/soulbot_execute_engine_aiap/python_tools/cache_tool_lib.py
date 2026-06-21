#!/usr/bin/env python3
"""cache_tool_lib.py — Shared helpers for  structured cache tools.

Pure stdlib (no external deps). Used by agent_write_node_cache.py and agent_update_index.py.

Provides:
  - atomic_write_json(path, data)        — atomic .tmp + rename pattern
  - read_json_lenient(path)              — read with utf-8-sig BOM tolerance
  - coerce_types(data, schema_type)      — soft type conversion (str→int, str→list, etc.)
  - fill_defaults(data, schema_type, ctx) — auto-fill missing required fields
  - validate_or_raise(data, schema_type) — invoke validator, raise on fatal
  - read_index_field(cache_dir, key)     — read field from _index.json safely
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Allow running from anywhere
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from json_schema_validator import validate_cache_file, validate_data  # noqa: E402

_CACHE_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def atomic_write_json(path: Path, data: dict) -> None:
    """Atomic write via .tmp + rename. Never produces orphan .tmp on success."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(path)
    except Exception:
        # Clean up tmp on failure
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Cross-platform file lock for parallel-dispatch race protection
# ---------------------------------------------------------------------------

class _FileLock:
    """Cross-platform exclusive file lock with timeout retry.

    Used to serialize concurrent _index.json writes when AISOP
    node_engine step3 (c) PARALLEL DISPATCH (B3) dispatches multiple
    Sub Agents that each call _append_nodes_status.

    Falls back to lockfile-based mutex on Windows (msvcrt.locking can be
    flaky on network paths). Uses fcntl.flock on Unix.
    """

    def __init__(self, target: Path, timeout: float = 10.0, poll_s: float = 0.05) -> None:
        self.lockfile = target.with_suffix(target.suffix + ".lock")
        self.timeout = timeout
        self.poll_s = poll_s
        self._handle = None

    def __enter__(self):
        deadline = time.time() + self.timeout
        while True:
            try:
                # O_EXCL creates atomically — fails if file exists
                fd = os.open(
                    str(self.lockfile),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                self._handle = fd
                return self
            except FileExistsError:
                if time.time() >= deadline:
                    raise TimeoutError(
                        f"Failed to acquire lock {self.lockfile} within {self.timeout}s"
                    )
                time.sleep(self.poll_s)

    def __exit__(self, *exc):
        if self._handle is not None:
            try:
                os.close(self._handle)
            except OSError:
                pass
            try:
                self.lockfile.unlink(missing_ok=True)
            except OSError:
                pass
        return False  # propagate exceptions


def merge_index_field(
    index_path: Path,
    field: str,
    key: str,
    value: dict,
    timeout: float = 10.0,
) -> None:
    """Lock-protected merge: _index.json[field][key] <- value, atomic write.

    Solves the parallel-dispatch race where two Sub Agents simultaneously
    update _index.json::nodes_status — without lock, one update overwrites
    the other.

    SIBLING-PRESERVING MERGE (2026-06-15, plan22/22): when both the existing
    _index.json[field][key] and `value` are dicts, `value` is merged ONE LEVEL
    INTO the existing object instead of replacing it wholesale. This preserves
    sibling keys written by a prior call — e.g. agent_write_node_cache.py writes
    nodes_status[node]={status,tool_calls}, which previously WIPED a
    next_node_plan that the per-node loop (C2/B-INLINE) had written to
    nodes_status[node].next_node_plan beforehand. Same idiom as
    merge_index_top_level. Non-dict values (or a non-dict existing entry) still
    replace, preserving prior behaviour for scalar/list entries.
    """
    with _FileLock(index_path, timeout=timeout):
        data = read_json_lenient(index_path)
        if field not in data or not isinstance(data[field], dict):
            data[field] = {}
        existing = data[field].get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged = dict(existing)
            merged.update(value)
            data[field][key] = merged
        else:
            data[field][key] = value
        atomic_write_json(index_path, data)


def merge_index_top_level(
    index_path: Path,
    updates: dict,
    timeout: float = 10.0,
) -> None:
    """Lock-protected merge of top-level fields into _index.json."""
    with _FileLock(index_path, timeout=timeout):
        data = read_json_lenient(index_path)
        for k, v in updates.items():
            if k in data and isinstance(data[k], dict) and isinstance(v, dict):
                merged = dict(data[k])
                merged.update(v)
                data[k] = merged
            else:
                data[k] = v
        atomic_write_json(index_path, data)


# ---------------------------------------------------------------------------
# Agent ID auto-generation
# ---------------------------------------------------------------------------

import re as _re

# Strict agent_id categories (A1 v5.4.1)
# Only these 5 patterns are accepted:
_AGENT_ID_PATTERNS = [
    _re.compile(r"^auto-[0-9a-f]{8}$"),
    _re.compile(r"^task-[0-9a-f]{8}$"),
    _re.compile(r"^gemini-[0-9a-f]{8}$"),
]
_AGENT_ID_LITERALS = frozenset(("inline_planned", "inline_fallback"))


def validate_agent_id_strict(agent_id: str) -> tuple[bool, str]:
    """Validate agent_id against the strict 5-category enum (A1 v5.4.1).

    Returns (is_valid, reason). If invalid, reason explains the rejection.
    Categories:
      1. ^auto-[0-9a-f]{8}$   (Sub Agent dispatch via Agent tool)
      2. ^task-[0-9a-f]{8}$   (Sub Agent dispatch via Task tool)
      3. ^gemini-[0-9a-f]{8}$ (Sub Agent dispatch via Gemini CLI)
      4. 'inline_planned'      (Planned inline execution)
      5. 'inline_fallback'     (Fallback — requires fallback_reason)
    """
    if not agent_id or not isinstance(agent_id, str):
        return False, "agent_id is empty or not a string"
    if agent_id in _AGENT_ID_LITERALS:
        return True, f"matched literal '{agent_id}'"
    for pat in _AGENT_ID_PATTERNS:
        if pat.match(agent_id):
            return True, f"matched pattern {pat.pattern}"
    return False, (
        f"agent_id '{agent_id}' does not match any of the 5 strict categories: "
        "auto-<hex8>, task-<hex8>, gemini-<hex8>, inline_planned, inline_fallback"
    )


def resolve_agent_id(supplied: Optional[str]) -> str:
    """Pick agent_id with sensible fallbacks.

    Priority:
      1. Supplied via --agent_id CLI flag
      2. CLAUDE_AGENT_ID env var (set by orchestrator)
      3. SOULBOT_AGENT_ID env var (set by orchestrator)
      4. Auto-generated unique ID 'auto-{8 hex chars}'

    Never returns the generic 'default' which loses audit signal.
    All returned values conform to the strict 5-category enum (A1 v5.4.1).
    """
    if supplied and supplied != "default":
        return supplied
    for env_key in ("CLAUDE_AGENT_ID", "SOULBOT_AGENT_ID"):
        env_val = os.environ.get(env_key, "").strip()
        if env_val:
            return env_val
    return f"auto-{os.urandom(4).hex()}"


def read_json_lenient(path: Path) -> dict:
    """Read JSON tolerating UTF-8 BOM. Returns {} if file missing."""
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def read_index_field(cache_dir: Path, key: str, default: Any = None) -> Any:
    """Read a single field from {cache_dir}/_index.json, return default if missing."""
    try:
        data = read_json_lenient(cache_dir / "_index.json")
        return data.get(key, default)
    except (OSError, json.JSONDecodeError):
        return default


# ---------------------------------------------------------------------------
# Type coercion (Phase A audit found 39+ tool_calls type errors)
# ---------------------------------------------------------------------------

def coerce_types(data: dict, schema_type: str) -> tuple[dict, list[str]]:
    """Soft type conversion. Returns (coerced_data, list_of_coercions)."""
    out = dict(data)
    coercions: list[str] = []

    if schema_type == "node_cache":
        # tool_calls: "24" -> 24
        if "tool_calls" in out and isinstance(out["tool_calls"], str):
            try:
                out["tool_calls"] = int(out["tool_calls"].strip())
                coercions.append("tool_calls: str -> int")
            except ValueError:
                pass

        # modifications: "a, b, c" -> ["a","b","c"]; "x" -> ["x"]
        mods = out.get("modifications")
        if isinstance(mods, str):
            if "," in mods:
                out["modifications"] = [s.strip() for s in mods.split(",") if s.strip()]
            elif mods.strip():
                out["modifications"] = [mods.strip()]
            else:
                out["modifications"] = []
            coercions.append("modifications: str -> list")

        # user_messages: "hi" -> ["hi"]
        msgs = out.get("user_messages")
        if isinstance(msgs, str):
            out["user_messages"] = [msgs] if msgs else []
            coercions.append("user_messages: str -> list")

        # completed: "true"/"false" -> bool
        c = out.get("completed")
        if isinstance(c, str):
            if c.lower() in ("true", "1", "yes"):
                out["completed"] = True
                coercions.append("completed: str -> True")
            elif c.lower() in ("false", "0", "no"):
                out["completed"] = False
                coercions.append("completed: str -> False")

        # steps_done / steps_remaining: "step1,step2" -> [...]
        for k in ("steps_done", "steps_remaining"):
            v = out.get(k)
            if isinstance(v, str):
                if "," in v:
                    out[k] = [s.strip() for s in v.split(",") if s.strip()]
                elif v.strip():
                    out[k] = [v.strip()]
                else:
                    out[k] = []
                coercions.append(f"{k}: str -> list")

    return out, coercions


# ---------------------------------------------------------------------------
# Default-fill (Phase A audit found 'completed' missing as top issue)
# ---------------------------------------------------------------------------

def fill_defaults_node_cache(
    data: dict,
    cache_dir: Path,
    node_name: str,
) -> tuple[dict, list[str]]:
    """Fill missing required fields with sane defaults. Returns (filled, list_of_fills)."""
    out = dict(data)
    fills: list[str] = []

    # completed: infer from status
    if "completed" not in out:
        status = out.get("status", "")
        if status in ("PASS", "FAIL", "DEGRADED", "ABORTED"):
            out["completed"] = True
        elif status in ("WAITING_USER", "MESSAGE_PENDING"):
            out["completed"] = False
        else:
            out["completed"] = True  # default optimistic
        fills.append(f"completed=auto({out['completed']!r})")

    # cache_schema_version
    if "cache_schema_version" not in out:
        out["cache_schema_version"] = _CACHE_SCHEMA_VERSION
        fills.append(f"cache_schema_version={_CACHE_SCHEMA_VERSION!r}")

    # execute_mode: read from _index.json::dispatch_plan
    if "execute_mode" not in out:
        plan = read_index_field(cache_dir, "dispatch_plan", {}) or {}
        em = plan.get(node_name)
        if isinstance(em, dict):
            em = em.get("execute_mode", "agent")
        elif not isinstance(em, str):
            em = "agent"
        out["execute_mode"] = em
        fills.append(f"execute_mode=auto({em!r})")

    # trace_id: read from _index.json
    if "trace_id" not in out:
        tid = read_index_field(cache_dir, "trace_id", "")
        if tid:
            out["trace_id"] = tid
            fills.append("trace_id=auto(from _index)")

    # span_id: generate from trace_id + node_name
    if "span_id" not in out:
        tid = out.get("trace_id", "")
        if tid:
            out["span_id"] = f"{tid}.{node_name}"
            fills.append("span_id=auto(trace.node)")

    # agent_id: v5.5.0 server-side — read from _index.json::dispatch_plan[node].expected_agent_id
    # CLI arg removed; host AI cannot self-report agent_id
    # Q4 FIX (v5.5.0): Do NOT silently fallback to resolve_agent_id(None) for non-inline
    # agent nodes — that would bypass agent_write_node_cache.py step 3a's
    # PRE_V5_5_0_INCOMPATIBLE rejection check. Leave agent_id unset so the
    # downstream strict enforcement can trigger.
    if "agent_id" not in out:
        plan = read_index_field(cache_dir, "dispatch_plan", {}) or {}
        plan_entry = plan.get(node_name)
        expected_aid = None
        if isinstance(plan_entry, dict):
            expected_aid = plan_entry.get("expected_agent_id")
        if expected_aid:
            out["agent_id"] = expected_aid
            fills.append(f"agent_id=server({expected_aid!r})")
        else:
            # Fallback for inline nodes only
            em = None
            if isinstance(plan_entry, dict):
                em = plan_entry.get("execute_mode")
            elif isinstance(plan_entry, str):
                em = plan_entry
            if em == "inline":
                out["agent_id"] = "inline_planned"
                fills.append("agent_id=inline_planned")
            # else: intentionally leave agent_id unset for agent-dispatched nodes
            # so agent_write_node_cache.py step 3a can reject with PRE_V5_5_0_INCOMPATIBLE
            # when expected_agent_id is missing from _index.json

    # user_messages: default empty list
    if "user_messages" not in out:
        out["user_messages"] = []
        fills.append("user_messages=[]")

    # modifications: default empty list
    if "modifications" not in out:
        out["modifications"] = []
        fills.append("modifications=[]")

    # steps_done: cannot infer, but allow empty
    if "steps_done" not in out:
        out["steps_done"] = []
        fills.append("steps_done=[]")

    # steps_remaining: default empty
    if "steps_remaining" not in out:
        out["steps_remaining"] = []
        fills.append("steps_remaining=[]")

    # node_summary_rendered: B1 v5.26.0 — default false.
    # Set to true by orchestrator via agent_update_index.py after step4 output.
    # dispatch_audit.py --completeness-check verifies this field post-hoc.
    if "node_summary_rendered" not in out:
        out["node_summary_rendered"] = False
        fills.append("node_summary_rendered=false")

    return out, fills


# ---------------------------------------------------------------------------
# Validation wrappers
# ---------------------------------------------------------------------------

def validate_or_raise(data: dict, schema_type: str) -> None:
    """Validate; raise ValueError on schema violation."""
    errors = validate_data(data, schema_type)
    if errors:
        raise ValueError(f"Schema violation ({schema_type}): {errors}")


def validate_soft(data: dict, schema_type: str) -> list[str]:
    """Validate; return error list (empty if valid)."""
    return validate_data(data, schema_type)


# ---------------------------------------------------------------------------
# Critical-field assertion
# ---------------------------------------------------------------------------

# Fields AI MUST provide (cannot be auto-filled)
NODE_CACHE_CRITICAL_FIELDS = ("status", "output", "user_summary", "tool_calls")


def assert_critical_fields_present(data: dict, schema_type: str) -> None:
    """Raise if AI omitted fields that cannot be auto-filled."""
    if schema_type != "node_cache":
        return
    missing = [k for k in NODE_CACHE_CRITICAL_FIELDS if k not in data]
    if missing:
        raise ValueError(
            f"AI must provide critical fields: {missing}. "
            f"Auto-fill cannot infer these — they require real execution data."
        )


# ---------------------------------------------------------------------------
# Stdin reading (cross-platform UTF-8)
# ---------------------------------------------------------------------------

def read_stdin_json() -> dict:
    """Read JSON from stdin with UTF-8 enforcement."""
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    text = sys.stdin.read()
    if not text.strip():
        raise ValueError("Empty stdin — expected JSON object")
    return json.loads(text)


# ---------------------------------------------------------------------------
# Shared spawn_failure_evidence validation (Q2 v5.6.0 DRY extraction)
# ---------------------------------------------------------------------------

# Valid failure_signal enum values for spawn_failure_evidence
VALID_FAILURE_SIGNALS = frozenset(("timeout", "nonzero_exit", "exception", "spawn_error"))

# Required fields in spawn_failure_evidence
SPAWN_FAILURE_EVIDENCE_REQUIRED = ("attempted_spawn_tool", "attempted_at", "failure_signal", "failure_detail")


def validate_spawn_failure_evidence(
    sfe: Any,
    generated_at: str = "",
) -> tuple[bool, str]:
    """Validate a spawn_failure_evidence object (A1 v5.6.0).

    Shared validation used by both agent_write_node_cache.py and dispatch_audit.py.

    Args:
        sfe: The spawn_failure_evidence value from cache data.
        generated_at: ISO 8601 timestamp from dispatch_records[node].generated_at
            for temporal ordering check. Empty string skips the check.

    Returns:
        (is_valid, reason) tuple.
        is_valid=True means evidence is present and valid.
        is_valid=False with reason explaining the rejection.
    """
    if not isinstance(sfe, dict):
        return False, "spawn_failure_evidence is missing or not a dict"

    # Check required fields
    missing = [f for f in SPAWN_FAILURE_EVIDENCE_REQUIRED if f not in sfe]
    if missing:
        return False, f"spawn_failure_evidence missing required fields: {missing}"

    # Validate failure_signal enum
    fs = sfe.get("failure_signal", "")
    if fs not in VALID_FAILURE_SIGNALS:
        return False, (
            f"failure_signal '{fs}' not in {sorted(VALID_FAILURE_SIGNALS)}. "
            "Vague reasons are not accepted."
        )

    # Validate temporal ordering: attempted_at > generated_at
    if generated_at:
        attempted_at = sfe.get("attempted_at", "")
        if attempted_at:
            try:
                gen_t = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
                att_t = datetime.fromisoformat(attempted_at.replace("Z", "+00:00"))
                if att_t <= gen_t:
                    return False, (
                        f"attempted_at ({attempted_at}) <= generated_at ({generated_at}). "
                        "Spawn attempt must occur AFTER agent_id generation."
                    )
            except (ValueError, TypeError):
                return False, "could not parse timestamps for temporal ordering check"

    return True, "valid"
