#!/usr/bin/env python3
"""agent_write_node_cache.py — Sub Agent writes its node cache via structured tool.

Replaces AI's manual file_system.write of node cache.

USAGE
=====

Stdin JSON (recommended — avoids shell escape issues):

    cat <<'EOF' | python agent_write_node_cache.py \\
      --cache_dir=examples/.../cache/8 \\
      --aiap=soulbot_creator_evolution \\
      --node=DependencyCheck
    {
      "status": "PASS",
      "output": "Dependencies verified: 15/15 modules + 6/6 Creator resources.",
      "user_summary": "All dependencies present.",
      "tool_calls": 24,
      "steps_done": ["step1","step2","step3"]
    }
    EOF

--data CLI arg (alternative):

    python agent_write_node_cache.py \\
      --cache_dir=cache/8 \\
      --aiap=soulbot_creator_evolution \\
      --node=DependencyCheck \\
      --data='{"status":"PASS","output":"...","user_summary":"...","tool_calls":24}'

REQUIRED FIELDS (AI must provide)
=================================

  status        — enum: PASS | FAIL | PARTIAL | WAITING_USER | MESSAGE_PENDING | DEGRADED
  output        — string: key findings for the next Agent
  user_summary  — string: human-readable narrative
  tool_calls    — integer: total tool invocations

AUTO-FILLED FIELDS (if missing)
================================

  completed              ← inferred from status
  execute_mode           ← read from _index.json::dispatch_plan
  trace_id               ← read from _index.json
  span_id                ← {trace_id}.{node}
  agent_id               ← auto-read from _index.json::dispatch_plan[node].expected_agent_id (v5.5.0)
  cache_schema_version   ← '1.0'
  user_messages          ← []
  modifications          ← []
  steps_done             ← []
  steps_remaining        ← []

GUARANTEES
==========

  - JSON file ALWAYS valid (Python json.dumps handles all escaping)
  - Schema validation BEFORE write
  - Atomic .tmp + rename (no orphan .tmp on success)
  - _index.json::nodes_status auto-updated
  - Returns structured result with `fields_filled`, `coercions`, `errors`
"""
from __future__ import annotations

import argparse
import json
import re as _re_aid
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cache_tool_lib import (  # noqa: E402
    atomic_write_json,
    coerce_types,
    fill_defaults_node_cache,
    assert_critical_fields_present,
    validate_soft,
    validate_agent_id_strict,
    read_json_lenient,
    read_index_field,
    read_stdin_json,
    merge_index_field,
    merge_index_top_level,
    validate_spawn_failure_evidence,
)

# Statuses that count as "node done" → eligible to advance last_completed_node.
# WAITING_USER and MESSAGE_PENDING explicitly do NOT count (the node will resume).
_NODE_DONE_STATUSES = frozenset(("PASS", "FAIL", "PARTIAL", "DEGRADED", "ABORTED"))


def write_node_cache(
    cache_dir: Path,
    aiap_name: str,
    node_name: str,
    data: dict,
    *,
    dry_run: bool = False,
) -> dict:
    """Write a node cache file safely.

    Returns:
        {
          "status": "ok"|"error",
          "file": str path,
          "fields_filled": [list of auto-filled fields],
          "coercions": [list of type coercions performed],
          "errors": [list of fatal errors if status=error],
          "hints": [list of remediation hints for common errors],
          "warnings": [list of non-fatal warnings],
        }
    """
    result = {
        "status": "ok",
        "file": "",
        "fields_filled": [],
        "coercions": [],
        "errors": [],
        "hints": [],
        "warnings": [],
    }

    cache_dir = Path(cache_dir).resolve()
    if not cache_dir.is_dir():
        result["status"] = "error"
        result["errors"].append(f"cache_dir not found: {cache_dir}")
        result["hints"].append("Pass an existing turn cache dir, e.g. CONTEXT_DIR from your bootstrap.")
        return result

    if not aiap_name or not node_name:
        result["status"] = "error"
        result["errors"].append("aiap_name and node_name are required")
        result["hints"].append("Set --aiap=AIAP_NAME and --node=YOUR_NODE from your bootstrap params.")
        return result

    # 1. Critical-field check (AI must provide; cannot auto-fill)
    try:
        assert_critical_fields_present(data, "node_cache")
    except ValueError as e:
        result["status"] = "error"
        result["errors"].append(str(e))
        result["hints"].append(
            "Provide ALL 4 critical fields: status (enum), output (string), "
            "user_summary (string), tool_calls (integer)."
        )
        return result

    # 2. Type coercion (str -> int, str -> list, etc.)
    data, coercions = coerce_types(data, "node_cache")
    result["coercions"] = coercions

    # 3. Auto-fill defaults (v5.5.0: agent_id auto-read from _index.json, no CLI arg)
    data, fills = fill_defaults_node_cache(data, cache_dir, node_name)
    result["fields_filled"] = fills

    # 3a. AGENT_ID SERVER-SIDE READ (A1 v5.5.0)
    # agent_id MUST come from _index.json::dispatch_plan[node].expected_agent_id
    # Host AI has NO override capability. Missing field -> reject as PRE_V5_5_0_INCOMPATIBLE.
    if "agent_id" not in data or not data.get("agent_id"):
        plan = read_index_field(cache_dir, "dispatch_plan", {}) or {}
        plan_entry = plan.get(node_name)
        expected_aid = None
        if isinstance(plan_entry, dict):
            expected_aid = plan_entry.get("expected_agent_id")
        if expected_aid:
            data["agent_id"] = expected_aid
            result["fields_filled"].append(f"agent_id=server({expected_aid!r})")
        else:
            # Check for inline nodes
            em = None
            if isinstance(plan_entry, dict):
                em = plan_entry.get("execute_mode")
            elif isinstance(plan_entry, str):
                em = plan_entry
            if em == "inline":
                data["agent_id"] = "inline_planned"
                result["fields_filled"].append("agent_id=inline_planned")
            else:
                result["status"] = "error"
                result["errors"].append(
                    "PRE_V5_5_0_INCOMPATIBLE: _index.json::dispatch_plan"
                    f"['{node_name}'].expected_agent_id is missing. "
                    "v5.5.0 requires server-side agent_id generation via "
                    "agent_id_generator.py BEFORE sub-agent dispatch. "
                    "The --agent_id CLI parameter has been removed."
                )
                result["hints"].append(
                    "Run agent_id_generator.py --cache_dir=<dir> --node=<node> "
                    "--dispatch_type=auto BEFORE dispatching the sub-agent."
                )
                return result

    # 3b. AUTO-FILL dispatch_plan_expected from _index.json (A3 v5.4.3)
    if "dispatch_plan_expected" not in data:
        plan = read_index_field(cache_dir, "dispatch_plan", {}) or {}
        plan_val = plan.get(node_name)
        if isinstance(plan_val, dict):
            plan_val = plan_val.get("execute_mode", "agent")
        elif not isinstance(plan_val, str):
            plan_val = None
        if plan_val in ("agent", "inline"):
            data["dispatch_plan_expected"] = plan_val
            result["fields_filled"].append(f"dispatch_plan_expected=auto({plan_val!r})")

    # 3c. AGENT_ID_STRICT validation (A1 v5.4.1)
    aid = data.get("agent_id", "")
    aid_valid, aid_reason = validate_agent_id_strict(aid)
    if not aid_valid:
        result["warnings"].append(
            f"AGENT_ID_STRICT (A1 v5.4.1): {aid_reason}. "
            "Expected: auto-<hex8>, task-<hex8>, gemini-<hex8>, inline_planned, inline_fallback."
        )
    if aid == "inline_fallback" and not data.get("fallback_reason"):
        result["warnings"].append(
            "AGENT_ID_STRICT: agent_id='inline_fallback' but 'fallback_reason' is missing. "
            "inline_fallback MUST include fallback_reason per A1 v5.4.1."
        )

    # 3d. AGENT_ID ENTROPY + UNIQUENESS HARD VALIDATOR (A1 v5.4.4)
    # For prefixed hex agent_ids, enforce:
    #   (a) hex portion has >= 4 unique hex characters (rejects trivial fakes)
    #   (b) agent_id is unique across sibling caches in same trace_id
    _HEX_PREFIX_RE = _re_aid.compile(r"^(auto|task|gemini)-([0-9a-f]{8})$")
    hex_match = _HEX_PREFIX_RE.match(aid)
    if hex_match:
        hex_portion = hex_match.group(2)
        unique_chars = len(set(hex_portion))
        # (a) Entropy check: unique hex chars >= 4
        if unique_chars < 4:
            result["status"] = "error"
            result["errors"].append(
                f"AGENT_ID_ENTROPY_VIOLATION (A1 v5.4.4): agent_id '{aid}' "
                f"has only {unique_chars} unique hex chars in '{hex_portion}' "
                f"(minimum 4 required). Trivial/fake hex patterns are rejected. "
                f"Use os.urandom(4).hex() or secrets.token_hex(4) to generate."
            )
            result["hints"].append(
                "Generate agent_id hex via: python -c \"import os; print('auto-' + os.urandom(4).hex())\""
            )
            return result

        # (b) Cross-cache uniqueness check: scan sibling caches for duplicate agent_id
        for sibling_fn in sorted(cache_dir.iterdir()):
            if not sibling_fn.name.endswith(".json"):
                continue
            if sibling_fn.name in ("_index.json", "conversation_context.json", "node_cache.schema.json"):
                continue
            if sibling_fn.name.startswith("_"):
                continue
            # Skip our own target file
            expected_filename = f"{aiap_name}.{node_name}.json"
            if sibling_fn.name == expected_filename:
                continue
            try:
                with open(sibling_fn, encoding="utf-8") as _sf:
                    sibling_cache = json.load(_sf)
                if isinstance(sibling_cache, dict):
                    sibling_aid = sibling_cache.get("agent_id", "")
                    if sibling_aid == aid:
                        result["status"] = "error"
                        result["errors"].append(
                            f"AGENT_ID_UNIQUENESS_VIOLATION (A1 v5.4.4): agent_id '{aid}' "
                            f"already exists in sibling cache '{sibling_fn.name}'. "
                            f"Each sub-agent node MUST have a unique agent_id within the same trace. "
                            f"Duplicate agent_id indicates fabrication (collision probability ~1/2^32)."
                        )
                        result["hints"].append(
                            "Re-generate agent_id via: python -c \"import os; print('auto-' + os.urandom(4).hex())\""
                        )
                        return result
            except (json.JSONDecodeError, OSError):
                continue

    # 3e. SPAWN_FAILURE_EVIDENCE validation (A1 v5.6.0)
    # When agent_id='inline_fallback' AND dispatch_plan says 'agent',
    # spawn_failure_evidence is REQUIRED with valid fields.
    # Q2 v5.6.0: Uses shared validate_spawn_failure_evidence from cache_tool_lib.py
    aid_val = data.get("agent_id", "")
    if aid_val == "inline_fallback":
        plan = read_index_field(cache_dir, "dispatch_plan", {}) or {}
        plan_entry = plan.get(node_name)
        plan_mode = None
        if isinstance(plan_entry, dict):
            plan_mode = plan_entry.get("execute_mode")
        elif isinstance(plan_entry, str):
            plan_mode = plan_entry
        if plan_mode == "agent":
            sfe = data.get("spawn_failure_evidence")
            # Get generated_at for temporal ordering check
            generated_at = ""
            records = read_index_field(cache_dir, "dispatch_records", {}) or {}
            record = records.get(node_name)
            if isinstance(record, dict):
                generated_at = record.get("generated_at", "")
            sfe_valid, sfe_reason = validate_spawn_failure_evidence(sfe, generated_at)
            if not sfe_valid:
                result["status"] = "error"
                result["errors"].append(
                    f"SPAWN_FAILURE_EVIDENCE_INVALID (A1 v5.6.0): {sfe_reason}. "
                    f"agent_id='inline_fallback' with dispatch_plan['{node_name}']='agent' "
                    "requires valid spawn_failure_evidence."
                )
                result["hints"].append(
                    "spawn_failure_evidence is REQUIRED for inline_fallback when "
                    "dispatch_plan says 'agent'. Include attempted_spawn_tool "
                    "(Agent|Task|Bash:gemini), attempted_at (ISO8601), "
                    "failure_signal (timeout|nonzero_exit|exception|spawn_error), "
                    "and failure_detail with structured error info."
                )
                return result

    # 4. Strict schema validation BEFORE write
    errors = validate_soft(data, "node_cache")
    if errors:
        result["status"] = "error"
        result["errors"] = errors
        result["hints"] = _build_hints(errors, data)
        return result

    # 4b. Semantic warnings (schema-valid but contractually risky)
    if data.get("status") == "WAITING_USER" and not data.get("question"):
        result["warnings"].append(
            "status=WAITING_USER but 'question' is empty — Main Agent has nothing to "
            "forward to user; the gate is effectively broken. Add question='...'"
        )
    if data.get("status") == "MESSAGE_PENDING" and not data.get("message") and not data.get("user_messages"):
        result["warnings"].append(
            "status=MESSAGE_PENDING but no 'message'/'user_messages' set — Main Agent "
            "has nothing to forward."
        )

    # 5. Compute output path
    out_path = cache_dir / f"{aiap_name}.{node_name}.json"
    result["file"] = str(out_path)

    if dry_run:
        result["warnings"].append("dry_run=True; no file written")
        return result

    # 6. Atomic write
    try:
        atomic_write_json(out_path, data)
    except OSError as e:
        result["status"] = "error"
        result["errors"].append(f"atomic_write_json failed: {e}")
        return result

    # 7. Update _index.json::nodes_status (atomic merge)
    try:
        _append_nodes_status(cache_dir / "_index.json", node_name, {
            "status": data.get("status"),
            "tool_calls": data.get("tool_calls"),
        })
    except Exception as e:
        result["warnings"].append(f"nodes_status update failed: {e}")

    # 7b. Maintain last_completed_node for crash recovery + observability.
    # Per node_engine.aisop.json::step3 (f) RESUMABILITY MARKER — AI was
    # supposed to do this but historically forgets; tool now does it
    # automatically when node reaches a terminal status.
    if data.get("status") in _NODE_DONE_STATUSES:
        try:
            merge_index_top_level(cache_dir / "_index.json", {
                "last_completed_node": node_name,
            })
        except Exception as e:
            result["warnings"].append(f"last_completed_node update failed: {e}")

    # 8. Cleanup AI's staging files: _tmp_*.json that AI used to stage JSON
    # input before calling the tool (observed in inline mode mostly — AI prefers
    # 'cat _tmp_xxx.json | python tool.py' over heredoc on Windows).
    cleanup_count = 0
    node_key = node_name.lower()
    patterns = [f"_tmp_{node_key}.json", f"_tmp_{node_name}.json"]
    for pat in patterns:
        f = cache_dir / pat
        if f.is_file():
            try:
                f.unlink()
                cleanup_count += 1
            except OSError:
                pass
    if cleanup_count:
        result["warnings"].append(f"cleaned up {cleanup_count} AI staging file(s)")

    return result


def _append_nodes_status(index_path: Path, node_name: str, entry: dict) -> None:
    """Merge nodes_status[node_name] = entry into _index.json with lock.

    Uses cache_tool_lib.merge_index_field which serializes concurrent
    parallel-dispatch writes via cross-platform file lock — without it,
    two Sub Agents finishing simultaneously can lose each other's entries.
    """
    merge_index_field(index_path, "nodes_status", node_name, entry)


def _build_hints(errors: list[str], data: dict) -> list[str]:
    """Generate remediation hints for common schema violations.

    Inspects error messages and the data shape to suggest concrete fixes
    the AI can apply on retry. Keeps the AI from blindly resending the same
    invalid payload.
    """
    hints: list[str] = []
    seen: set[str] = set()

    def add(h: str) -> None:
        if h not in seen:
            hints.append(h)
            seen.add(h)

    for err in errors:
        low = err.lower()

        # Missing required field
        if "missing required key" in low:
            if "'status'" in err:
                add("status: must be one of PASS / FAIL / PARTIAL / WAITING_USER / MESSAGE_PENDING / DEGRADED.")
            elif "'output'" in err:
                add("output: provide a non-empty string with key findings for the next agent.")
            elif "'user_summary'" in err:
                add("user_summary: provide a one-sentence narrative for the human reader.")
            elif "'tool_calls'" in err:
                add("tool_calls: provide an INTEGER (not a string) — the total tool invocations during this node.")
            elif "'steps_done'" in err or "'steps_remaining'" in err:
                add("steps_done / steps_remaining: pass a list of step keys like ['step1','step2'].")
            else:
                add("Add the missing field listed in the error. See --help for the full field list.")

        # Type mismatch
        if "type mismatch" in low:
            if "tool_calls" in err:
                add('tool_calls type: pass integer 24, not string "24".')
            elif "modifications" in err:
                add('modifications type: pass list ["file_a","file_b"], not a comma-separated string.')
            elif "user_messages" in err:
                add('user_messages type: pass list ["msg1"], not a single string.')
            elif "completed" in err:
                add('completed type: pass boolean true/false, not string "true".')
            elif "steps_done" in err or "steps_remaining" in err:
                add('steps lists must be arrays of strings like ["step1","step2"].')
            else:
                add("Type mismatch — check the field type against node_cache.schema.json.")

        # Enum violation
        if "enum violation" in low:
            if "status" in err:
                add("status enum: must be EXACTLY one of PASS / FAIL / PARTIAL / WAITING_USER / MESSAGE_PENDING / DEGRADED (case-sensitive).")
            elif "execute_mode" in err:
                add("execute_mode enum: must be 'agent' or 'inline' (lowercase).")
            else:
                add("Enum violation — check allowed values in node_cache.schema.json.")

        # Minimum violation
        if "minimum=" in err:
            add("Numeric value below minimum — tool_calls / retry_count / execution_time_ms must be >= 0.")

    # WAITING_USER context-sensitive hint
    if data.get("status") == "WAITING_USER" and not data.get("question"):
        add("status=WAITING_USER requires non-empty 'question' field — Main Agent forwards it to the user.")

    if not hints:
        hints.append("Re-read node_cache.schema.json or run with --help for the full contract.")

    return hints


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Write a node cache file.")
    parser.add_argument("--cache_dir", required=True, help="Path to the turn cache dir (e.g. .execution_cache/8/).")
    parser.add_argument("--aiap", required=True, help="AIAP name (e.g. soulbot_creator_evolution).")
    parser.add_argument("--node", required=True, help="Node name (e.g. DependencyCheck).")
    parser.add_argument("--data", default=None, help="JSON string. If omitted, read from stdin.")
    parser.add_argument("--agent_id", default=None, help="DEPRECATED (v5.5.0): agent_id is now auto-read from _index.json. This flag is ignored.")
    parser.add_argument("--dry-run", action="store_true", help="Validate + auto-fill but don't write.")
    parser.add_argument("--quiet", action="store_true", help="Only print exit code.")
    args = parser.parse_args()

    # Get data from --data or stdin
    if args.data:
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(json.dumps({"status": "error", "errors": [f"--data JSON parse failed: {e}"]}, ensure_ascii=False))
            return 2
    else:
        try:
            data = read_stdin_json()
        except (json.JSONDecodeError, ValueError) as e:
            print(json.dumps({"status": "error", "errors": [f"stdin JSON parse failed: {e}"]}, ensure_ascii=False))
            return 2

    if not isinstance(data, dict):
        print(json.dumps({"status": "error", "errors": ["Input is not a JSON object"]}, ensure_ascii=False))
        return 2

    # v5.5.0: --agent_id is deprecated and ignored. agent_id is auto-read from _index.json.
    if args.agent_id:
        print(json.dumps({
            "status": "ok",
            "warnings": [
                "DEPRECATED (v5.5.0): --agent_id CLI flag is ignored. "
                "agent_id is now auto-read from _index.json::dispatch_plan[node].expected_agent_id. "
                "Remove --agent_id from your invocation."
            ]
        }, ensure_ascii=False), file=sys.stderr)

    result = write_node_cache(
        Path(args.cache_dir),
        args.aiap,
        args.node,
        data,
        dry_run=args.dry_run,
    )

    if not args.quiet:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
