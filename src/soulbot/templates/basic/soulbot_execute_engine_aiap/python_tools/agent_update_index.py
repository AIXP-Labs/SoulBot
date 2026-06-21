#!/usr/bin/env python3
"""agent_update_index.py — Safe structured update of _index.json.

Replaces AI's manual rewrite of _index.json,
which historically loses fields (e.g. turn 67 missing engine_version).

USAGE
=====

PREFERRED — JSON from a file (zero command-line escaping risk):

    python agent_update_index.py \\
      --cache_dir=cache/8 \\
      --updates-file=cache/8/_tmp_update.json

  Write the JSON object to a UTF-8 file first (e.g. with the Write tool),
  then pass its path. The JSON NEVER touches the command line, so the
  Windows inline-JSON failure mode (printf/echo '{...}' | python silently
  dropping the payload and stalling the run) cannot occur. Priority:
  --updates-file > --updates > stdin.

Merge arbitrary fields inline (small payloads only):

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

        # 2. Merge updates — TRUE recursive deep-merge + dotted-path unflatten.
        #    Fix 2026-06-10 (plan22/03 §12.6 Bug2 + §12.1 E5):
        #    - OLD code used dict.update() = ONE-LEVEL merge: any 2nd-level nested
        #      object in `v` REPLACED the existing nested object wholesale. Sending
        #      {user_gates_presented:{EvolveStep:{user_answer:"all"}}} wiped the
        #      sibling presented_at/question_hash. Now recurses to all depths.
        #    - dotted keys ("nodes_status.NodeX") were stored as LITERAL keys with
        #      a '.' (instead of nested) -> _index junk keys. Now unflattened first.
        def _unflatten(d):
            out = {}
            for key, val in d.items():
                if isinstance(key, str) and "." in key:
                    parts = key.split(".")
                    cur = out
                    for p in parts[:-1]:
                        nxt = cur.get(p)
                        if not isinstance(nxt, dict):
                            nxt = {}
                            cur[p] = nxt
                        cur = nxt
                    cur[parts[-1]] = val
                else:
                    out[key] = val
            return out

        def _deep_merge(base, upd):
            for key, val in upd.items():
                if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                    base[key] = _deep_merge(dict(base[key]), val)
                else:
                    base[key] = val
            return base

        merged = _deep_merge(dict(existing), _unflatten(updates))
        result["merged_keys"].extend(list(updates.keys()))

        # E4 (2026-06-10, plan22/03 §17): deterministically stamp a gate's
        # presented_at with a REAL server timestamp when the caller left an empty
        # or midnight (00:00:00) placeholder. Prevents orchestrator-supplied
        # placeholder gate timestamps (cf. cache/90 presented_at "23:30:00Z").
        # Conservative: only rewrites explicit placeholders, never a real value
        # and never an absent field. (started_at is already real via prepare_cache;
        # snapshot created_at is real via snapshot_build.py.)
        _gates = merged.get("user_gates_presented")
        if isinstance(_gates, dict):
            from datetime import datetime as _dt, timezone as _tz
            for _gnode, _g in _gates.items():
                if isinstance(_g, dict):
                    _pa = _g.get("presented_at")
                    if isinstance(_pa, str) and ((not _pa.strip()) or "T00:00:00" in _pa):
                        _g["presented_at"] = _dt.now(_tz.utc).isoformat()
                        result.setdefault("e4_stamped_presented_at", []).append(_gnode)

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
    parser.add_argument("--updates-file", default=None, help="Path to a UTF-8 file containing the JSON object to merge. PREFERRED over --updates/stdin: the JSON never touches the command line, eliminating shell-escaping failures (the Windows inline-JSON stall).")
    parser.add_argument("--updates", default=None, help="JSON object to merge inline (small payloads only). If omitted, read from stdin.")
    parser.add_argument("--mark-completed", action="store_true", help="Set status=completed + current_node=null.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    # Get updates — priority: --updates-file > --updates > stdin.
    # --updates-file is the canonical path: the JSON lives in a file, so the
    # command line carries only a path. This sidesteps the Windows failure mode
    # where `printf '{...}' | python` (or inline --updates with embedded quotes)
    # silently dropped the payload, leaving _index.json unmodified and stalling
    # the run (cf. cache/125 ValidateStep stall).
    if args.updates_file:
        try:
            _text = Path(args.updates_file).read_text(encoding="utf-8")
            updates = json.loads(_text) if _text.strip() else {}
        except FileNotFoundError:
            print(json.dumps({"status": "error", "errors": [f"--updates-file not found: {args.updates_file}"]}, ensure_ascii=False))
            return 2
        except (OSError, json.JSONDecodeError) as e:
            print(json.dumps({"status": "error", "errors": [f"--updates-file read/parse failed: {e}"]}, ensure_ascii=False))
            return 2
    elif args.updates:
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
