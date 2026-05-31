#!/usr/bin/env python3
"""generate_dispatch_plan.py -- Deterministic dispatch_plan generation (v5.7.0 A1).

Server-side tool that removes orchestrator AI judgment from dispatch_plan
mode assignment. Reads target AIAP functions and deterministically assigns
execute_mode per function declaration: set -> use it, unset -> default 'agent'.

This follows the same architecture-over-patch pattern as agent_id_generator.py
(v5.5.0): remove host AI freedom rather than detect violations.

Input:
    --entry_path: Absolute path to target AIAP entry file (.aisop.json)
    --cache_dir:  Absolute path to execution cache directory
    --nodes_in_path: Comma-separated list of node names (from mermaid parse)

Logic:
    1. Read target AIAP entry file, parse functions
    2. For each node in nodes_in_path:
       mode = functions[node].get("execute_mode", "agent")
       (unset -> agent, pure code, NO AI judgment)
    3. Write dispatch_plan to _index.json (atomic write via cache_tool_lib)

Output (JSON to stdout):
    {
        "status": "ok",
        "agent_count": N,
        "inline_count": N,
        "plan": { "NodeName": "agent"|"inline", ... }
    }

Exit codes:
    0  Success
    1  Validation error (bad args, file not found)
    2  I/O error (read/write failure)
    3  Parse error (invalid JSON in target AIAP)

Design notes:
    - nodes_in_path is still provided by orchestrator (mermaid parsing not
      migrated this cycle). This tool only determinizes mode assignment.
    - parallel_waves NOT generated here (stays with orchestrator).
    - Follows agent_id_generator.py pattern: pure Python, deterministic,
      atomic write to _index.json, JSON summary to stdout.

Reference: plan20/12_dispatch_plan_generation_vulnerability.md section 5.1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cache_tool_lib import (  # noqa: E402
    read_json_lenient,
    atomic_write_json,
    _FileLock,
)


def _read_target_functions(entry_path: Path) -> dict:
    """Read target AIAP entry file and extract functions dict.

    Handles both single-object and array-of-messages AISOP format:
      - Array format: [{"role":"system",...}, {"role":"user","content":{"functions":{...}}}]
      - Object format: {"functions": {...}}

    Returns the functions dict or empty dict if not found.

    NOTE (QI-2 v5.7.0): This function is intentionally independent from
    dispatch_audit.py's _read_target_functions(). Both implementations parse
    AISOP format independently to maintain verification independence — the
    audit must NOT share code with the generator it verifies. If the AISOP
    format changes, BOTH implementations must be updated. A shared integration
    test should verify format parity (see dispatch_audit.py for the mirror note).
    """
    if not entry_path.is_file():
        raise FileNotFoundError(f"Target AIAP entry file not found: {entry_path}")

    with open(entry_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    # Array format (standard AISOP): look for role=user message with functions
    if isinstance(data, list):
        for msg in data:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "user":
                content = msg.get("content", {})
                if isinstance(content, dict) and "functions" in content:
                    return content["functions"]
        raise ValueError(
            f"Target AIAP has no user message with functions: {entry_path}"
        )

    # Object format
    if isinstance(data, dict):
        if "functions" in data:
            return data["functions"]
        content = data.get("content", {})
        if isinstance(content, dict) and "functions" in content:
            return content["functions"]

    raise ValueError(f"Cannot extract functions from target AIAP: {entry_path}")


def generate_dispatch_plan(
    entry_path: Path,
    cache_dir: Path,
    nodes_in_path: list[str],
) -> dict:
    """Generate deterministic dispatch_plan from target AIAP functions.

    For each node in nodes_in_path:
        - If function has execute_mode field set -> use that value
        - If execute_mode NOT set -> default to "agent"

    This is pure deterministic logic. NO AI judgment involved.

    Returns:
        {
            "status": "ok" | "error",
            "agent_count": int,
            "inline_count": int,
            "plan": { "NodeName": "agent"|"inline", ... },
            "errors": [str],
        }
    """
    result = {
        "status": "ok",
        "agent_count": 0,
        "inline_count": 0,
        "plan": {},
        "errors": [],
    }

    # Validate inputs
    if not entry_path.is_file():
        result["status"] = "error"
        result["errors"].append(f"entry_path not found: {entry_path}")
        return result

    if not cache_dir.is_dir():
        result["status"] = "error"
        result["errors"].append(f"cache_dir not found: {cache_dir}")
        return result

    if not nodes_in_path:
        result["status"] = "error"
        result["errors"].append("nodes_in_path is empty")
        return result

    # Read target AIAP functions
    try:
        functions = _read_target_functions(entry_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as e:
        result["status"] = "error"
        result["errors"].append(f"Failed to read target AIAP: {e}")
        return result

    # Deterministic mode assignment
    plan = {}
    agent_count = 0
    inline_count = 0

    for node_name in nodes_in_path:
        func_def = functions.get(node_name, {})
        if not isinstance(func_def, dict):
            func_def = {}

        # Core logic: set -> use it, unset -> default "agent"
        # This is the ONLY place where execute_mode is determined.
        # NO AI judgment. Pure code.
        mode = func_def.get("execute_mode", "agent")

        # Validate mode value
        if mode not in ("agent", "inline"):
            # Invalid mode value, log warning and default to agent
            result.setdefault("warnings", [])
            result["warnings"].append(
                f"Node '{node_name}' has invalid execute_mode='{mode}', "
                f"defaulting to 'agent'"
            )
            mode = "agent"

        plan[node_name] = mode

        if mode == "agent":
            agent_count += 1
        else:
            inline_count += 1

    result["plan"] = plan
    result["agent_count"] = agent_count
    result["inline_count"] = inline_count

    # Write dispatch_plan to _index.json (atomic, lock-protected)
    index_path = cache_dir / "_index.json"
    try:
        with _FileLock(index_path):
            data = read_json_lenient(index_path)

            # Write dispatch_plan as mode-only entries
            # (agent_id_generator.py will later upgrade each entry to
            #  { execute_mode, expected_agent_id } when it runs)
            dispatch_plan = {}
            for node_name, mode in plan.items():
                dispatch_plan[node_name] = mode

            data["dispatch_plan"] = dispatch_plan
            atomic_write_json(index_path, data)

    except TimeoutError as e:
        result["status"] = "error"
        result["errors"].append(f"Lock timeout writing _index.json: {e}")
        return result
    except OSError as e:
        result["status"] = "error"
        result["errors"].append(f"I/O error writing _index.json: {e}")
        return result

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministic dispatch_plan generation (v5.7.0 A1). "
            "Reads target AIAP execute_mode fields; unset defaults to 'agent'. "
            "NO AI judgment."
        )
    )
    parser.add_argument(
        "--entry_path", required=True,
        help="Absolute path to target AIAP entry file (.aisop.json)"
    )
    parser.add_argument(
        "--cache_dir", required=True,
        help="Absolute path to execution cache directory"
    )
    parser.add_argument(
        "--nodes_in_path", required=True,
        help="Comma-separated list of node names (from mermaid parse)"
    )
    args = parser.parse_args()

    nodes = [n.strip() for n in args.nodes_in_path.split(",") if n.strip()]

    result = generate_dispatch_plan(
        entry_path=Path(args.entry_path),
        cache_dir=Path(args.cache_dir),
        nodes_in_path=nodes,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] == "ok":
        return 0
    elif any("I/O error" in e for e in result.get("errors", [])):
        return 2
    elif any("parse" in e.lower() or "json" in e.lower() for e in result.get("errors", [])):
        return 3
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
