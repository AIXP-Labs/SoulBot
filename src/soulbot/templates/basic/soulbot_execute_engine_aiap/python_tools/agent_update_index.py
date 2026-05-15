#!/usr/bin/env python3
"""agent_update_index.py — Safe structured update of _index.json.

Replaces AI's manual rewrite of _index.json,
which historically loses fields (e.g. turn 67 missing engine_version).

USAGE
=====

Merge arbitrary fields:

    python agent_update_index.py \\
      --cache_dir=cache/8 \\
      --updates='{"current_node":"Research2","last_completed_node":"Research1"}'

Stdin JSON also supported (for large dispatch_plan):

    cat <<'EOF' | python agent_update_index.py --cache_dir=cache/8
    {
      "dispatch_plan": {
        "Start": "inline",
        "NLU": "inline",
        "PipelineEntry": "inline",
        "PipelineStart": "agent"
      }
    }
    EOF

Mark turn completed:

    python agent_update_index.py --cache_dir=cache/8 --mark-completed

GUARANTEES
==========

  - MERGE semantics (never overwrites existing keys not in --updates)
  - Schema-validated after merge
  - Atomic .tmp + rename
  - Preserves Python-written fields (engine_version, started_at, trace_id, etc.)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cache_tool_lib import (  # noqa: E402
    atomic_write_json,
    read_json_lenient,
    validate_soft,
    _FileLock,
)


def update_index(
    cache_dir: Path,
    updates: dict,
    *,
    mark_completed: bool = False,
    dry_run: bool = False,
) -> dict:
    """Merge updates into _index.json safely.

    Returns:
        {
          "status": "ok"|"error",
          "file": str,
          "merged_keys": [list of top-level keys merged],
          "errors": [list of fatal errors],
          "warnings": [list of warnings],
        }
    """
    result = {
        "status": "ok",
        "file": "",
        "merged_keys": [],
        "errors": [],
        "warnings": [],
    }

    cache_dir = Path(cache_dir).resolve()
    if not cache_dir.is_dir():
        result["status"] = "error"
        result["errors"].append(f"cache_dir not found: {cache_dir}")
        return result

    index_path = cache_dir / "_index.json"
    result["file"] = str(index_path)

    # Lock-protected read-modify-write to avoid parallel-dispatch race.
    with _FileLock(index_path, timeout=10.0):
        # 1. Load existing _index.json
        try:
            existing = read_json_lenient(index_path)
        except json.JSONDecodeError as e:
            result["status"] = "error"
            result["errors"].append(f"existing _index.json parse failed: {e}")
            return result

        if not existing:
            result["status"] = "error"
            result["errors"].append(
                "_index.json missing or empty — must be created by prepare_execution_context first"
            )
            return result

        # 2. Merge updates (deep merge for dicts)
        merged = dict(existing)
        for k, v in updates.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                new = dict(merged[k])
                new.update(v)
                merged[k] = new
            else:
                merged[k] = v
            result["merged_keys"].append(k)

        # 3. Optional: mark turn completed
        if mark_completed:
            merged["status"] = "completed"
            merged["current_node"] = None
            result["merged_keys"].extend(["status=completed", "current_node=null"])

        # 4. Validate against schema
        errors = validate_soft(merged, "_index")
        if errors:
            result["status"] = "error"
            result["errors"] = errors
            return result

        if dry_run:
            result["warnings"].append("dry_run=True; no file written")
            return result

        # 5. Atomic write (still inside lock)
        try:
            atomic_write_json(index_path, merged)
        except OSError as e:
            result["status"] = "error"
            result["errors"].append(f"atomic_write_json failed: {e}")
            return result

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Update _index.json safely.")
    parser.add_argument("--cache_dir", required=True)
    parser.add_argument("--updates", default=None, help="JSON object to merge. If omitted, read from stdin.")
    parser.add_argument("--mark-completed", action="store_true", help="Set status=completed + current_node=null.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    # Get updates
    if args.updates:
        try:
            updates = json.loads(args.updates)
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "errors": [f"--updates parse failed: {e}"]}, ensure_ascii=False))
            return 2
    elif sys.stdin.isatty() and not args.mark_completed:
        print(json.dumps({"status": "error", "errors": ["No --updates and no stdin"]}, ensure_ascii=False))
        return 2
    elif not args.mark_completed:
        try:
            text = sys.stdin.read()
            updates = json.loads(text) if text.strip() else {}
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "errors": [f"stdin JSON parse failed: {e}"]}, ensure_ascii=False))
            return 2
    else:
        updates = {}

    if not isinstance(updates, dict):
        print(json.dumps({"status": "error", "errors": ["updates is not a JSON object"]}, ensure_ascii=False))
        return 2

    result = update_index(
        Path(args.cache_dir),
        updates,
        mark_completed=args.mark_completed,
        dry_run=args.dry_run,
    )

    if not args.quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
