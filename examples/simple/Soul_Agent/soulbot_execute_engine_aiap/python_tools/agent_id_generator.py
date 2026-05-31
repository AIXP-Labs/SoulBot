#!/usr/bin/env python3
"""agent_id_generator.py -- Server-side agent_id generation (v5.6.0 A1+A4).

Generates expected_agent_id BEFORE sub-agent dispatch, removing host AI's
ability to self-report arbitrary agent_id values.

Usage:
    python agent_id_generator.py \\
        --cache_dir=<run_cache_dir> \\
        --node=<node_name> \\
        --dispatch_type=<auto|task|gemini> \\
        [--parent_trace_id=<trace_id>] \\
        [--parent_pid=<pid>]

Output (JSON to stdout):
    {
        "status": "ok",
        "expected_agent_id": "auto-7f3b9e2a",
        "dispatch_record": {
            "node": "Generate1",
            "expected_agent_id": "auto-7f3b9e2a",
            "generated_at": "2026-05-19T20:30:00.123456+00:00",
            "generation_seed": "7f3b9e2a1c4d5e6f",
            "parent_trace_id": "f5117f8e-...",
            "parent_pid": 12345
        }
    }

Design (v5.5.0 A1 + v5.6.0 A4):
    - Uses secrets.token_hex(4) for cryptographic PRNG (8 hex chars)
    - Prefix based on dispatch_type: auto-, task-, gemini-
    - v5.6.0 A4: When dispatch_type not explicitly provided, reads
      _index.json::capability_probe.recommended to determine prefix:
        "agent" -> auto-, "task" -> task-, "gemini" -> gemini-
      Fixes cycle 19 bug where recommended="agent" but generated task-<hex>.
    - Writes dispatch_record to _index.json::dispatch_records[node]
    - dispatch_record includes generated_at (ISO 8601) for timestamp
      anti-forgery (A4 v5.5.0: spawned_at > generated_at ordering invariant)
    - generation_seed: 16 hex chars for audit trail
    - Write-once: rejects if dispatch_records[node] already exists
    - Also writes expected_agent_id to dispatch_plan[node].expected_agent_id

Exit codes:
    0  Success
    1  Validation error (bad args, write-once violation)
    2  I/O error
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cache_tool_lib import (  # noqa: E402
    read_json_lenient,
    atomic_write_json,
    _FileLock,  # Q5 FIX (v5.5.0): import shared _FileLock instead of duplicating
)


_VALID_DISPATCH_TYPES = frozenset(("auto", "task", "gemini"))


def generate_agent_id(
    cache_dir: Path,
    node_name: str,
    dispatch_type: str,
    parent_trace_id: str = "",
    parent_pid: int = 0,
) -> dict:
    """Generate expected_agent_id and write dispatch_record to _index.json.

    Returns:
        {
            "status": "ok" | "error",
            "expected_agent_id": str,
            "dispatch_record": dict,
            "errors": [str],
        }
    """
    result = {
        "status": "ok",
        "expected_agent_id": "",
        "dispatch_record": {},
        "errors": [],
    }

    # Validate dispatch_type
    if dispatch_type not in _VALID_DISPATCH_TYPES:
        result["status"] = "error"
        result["errors"].append(
            f"Invalid dispatch_type '{dispatch_type}'. "
            f"Must be one of: {sorted(_VALID_DISPATCH_TYPES)}"
        )
        return result

    # Validate cache_dir
    cache_dir = Path(cache_dir).resolve()
    if not cache_dir.is_dir():
        result["status"] = "error"
        result["errors"].append(f"cache_dir not found: {cache_dir}")
        return result

    index_path = cache_dir / "_index.json"

    # A4 v5.6.0: Align prefix with capability_probe.recommended from _index.json.
    # Maps: recommended="agent" -> auto-, "task" -> task-, "gemini" -> gemini-
    # This fixes cycle 19 bug where recommended="agent" generated task-<hex>.
    _RECOMMENDED_TO_PREFIX = {"agent": "auto", "task": "task", "gemini": "gemini"}
    actual_prefix = dispatch_type
    probe_recommended = ""
    try:
        index_data = read_json_lenient(index_path)
        capability_probe = index_data.get("capability_probe", {})
        if isinstance(capability_probe, dict):
            probe_recommended = capability_probe.get("recommended", "") or ""
    except Exception:
        pass  # Non-fatal

    if probe_recommended in _RECOMMENDED_TO_PREFIX:
        aligned_prefix = _RECOMMENDED_TO_PREFIX[probe_recommended]
        if aligned_prefix != dispatch_type:
            result.setdefault("warnings", [])
            result["warnings"].append(
                f"PREFIX_ALIGNMENT (A4 v5.6.0): dispatch_type='{dispatch_type}' "
                f"overridden to '{aligned_prefix}' based on "
                f"capability_probe.recommended='{probe_recommended}'"
            )
        actual_prefix = aligned_prefix
    else:
        # v5.6.1 FIX: capability_probe not yet written (boot-order edge case --
        # PipelineStart generates its own agent_id BEFORE it runs the probe).
        # Default to "auto" (Claude Code Agent tool, most common host) instead of
        # silently honoring an unverified dispatch_type. Fixes cycle 21 where
        # PipelineStart got task- while all later nodes correctly got auto-.
        if actual_prefix != "auto":
            result.setdefault("warnings", [])
            result["warnings"].append(
                f"PREFIX_BOOT_DEFAULT (v5.6.1): capability_probe.recommended "
                f"unavailable; defaulting prefix to 'auto' (was '{dispatch_type}')"
            )
        actual_prefix = "auto"

    # Generate agent_id using cryptographic PRNG
    hex_token = secrets.token_hex(4)  # 8 hex chars
    expected_agent_id = f"{actual_prefix}-{hex_token}"

    # Generate seed for audit trail (16 hex chars)
    generation_seed = secrets.token_hex(8)

    # Timestamp
    generated_at = datetime.now(timezone.utc).isoformat()

    # Build dispatch_record
    dispatch_record = {
        "node": node_name,
        "expected_agent_id": expected_agent_id,
        "generated_at": generated_at,
        "generation_seed": generation_seed,
        "parent_trace_id": parent_trace_id or "",
        "parent_pid": parent_pid or os.getpid(),
    }

    # Write to _index.json with lock (write-once for dispatch_records[node])
    try:
        with _FileLock(index_path):
            data = read_json_lenient(index_path)

            # Write-once check for dispatch_records
            dispatch_records = data.get("dispatch_records", {})
            if not isinstance(dispatch_records, dict):
                dispatch_records = {}
            if node_name in dispatch_records:
                result["status"] = "error"
                result["errors"].append(
                    f"WRITE_ONCE_VIOLATION: dispatch_records['{node_name}'] "
                    f"already exists. agent_id_generator.py is write-once per node."
                )
                return result

            # Write dispatch_record
            dispatch_records[node_name] = dispatch_record
            data["dispatch_records"] = dispatch_records

            # Also write expected_agent_id to dispatch_plan[node]
            dispatch_plan = data.get("dispatch_plan", {})
            if isinstance(dispatch_plan, dict):
                plan_entry = dispatch_plan.get(node_name)
                if isinstance(plan_entry, str):
                    # Convert string plan entry to dict
                    dispatch_plan[node_name] = {
                        "execute_mode": plan_entry,
                        "expected_agent_id": expected_agent_id,
                    }
                elif isinstance(plan_entry, dict):
                    plan_entry["expected_agent_id"] = expected_agent_id
                else:
                    dispatch_plan[node_name] = {
                        "execute_mode": "agent",
                        "expected_agent_id": expected_agent_id,
                    }
                data["dispatch_plan"] = dispatch_plan

            # observability (plan20/16): append-only dispatch timeline for crash
            # localization. ACP session_id is NOT reachable here (soulacp layer),
            # so correlate a crash by timestamp: ACP elapsed_ms back-derives the
            # crash wall-clock, matched against these per-node dispatch ts.
            # Empty/short timeline at crash => crash happened in startup/orchestrator
            # stage (before first dispatch), not in a node sub-agent.
            _tl = data.get("dispatch_timeline", [])
            if not isinstance(_tl, list):
                _tl = []
            _tl.append({
                "node": node_name,
                "ts": generated_at,
                "dispatch_type": actual_prefix,
                "agent_id": expected_agent_id,
            })
            data["dispatch_timeline"] = _tl

            atomic_write_json(index_path, data)

    except TimeoutError as e:
        result["status"] = "error"
        result["errors"].append(f"Lock timeout: {e}")
        return result
    except OSError as e:
        result["status"] = "error"
        result["errors"].append(f"I/O error: {e}")
        return result

    result["expected_agent_id"] = expected_agent_id
    result["dispatch_record"] = dispatch_record
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate expected_agent_id for sub-agent dispatch (v5.5.0 A1)"
    )
    parser.add_argument(
        "--cache_dir", required=True,
        help="Path to the turn cache dir (e.g. .execution_cache/18/)"
    )
    parser.add_argument(
        "--node", required=True,
        help="Node name (e.g. Generate1)"
    )
    parser.add_argument(
        "--dispatch_type", required=True,
        choices=sorted(_VALID_DISPATCH_TYPES),
        help="Dispatch mechanism type: auto (Agent tool), task (Task tool), gemini (Gemini CLI)"
    )
    parser.add_argument(
        "--parent_trace_id", default="",
        help="Parent orchestrator's trace_id for provenance"
    )
    parser.add_argument(
        "--parent_pid", type=int, default=0,
        help="Parent process ID"
    )
    args = parser.parse_args()

    result = generate_agent_id(
        cache_dir=Path(args.cache_dir),
        node_name=args.node,
        dispatch_type=args.dispatch_type,
        parent_trace_id=args.parent_trace_id,
        parent_pid=args.parent_pid,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
