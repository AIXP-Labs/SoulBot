#!/usr/bin/env python3
"""
user_gate_audit.py  v5.12.0

Mechanical audit tool for user_gate sovereignty enforcement.
v5.12.0 changes (G1+G3 from plan20/19_user_gate_enforcement_remediation):
  - G1: Auto-detect gates from node definition text by scanning for
    gate-specific markers instead of relying on explicit user_gate:true flag.
    Backward-compatible: explicit user_gate:true still recognized.
    Markers scanned: USER_CONFIRMATION_MANDATORY, sovereignty_violation,
    auto_approve_attempt, WAITING_USER (as requirement text, not sys.io.*),
    [GATE] User reply REQUIRED, step{N} ENDS HERE.
    IMPORTANT: Does NOT scan sys.io.confirm/select generic words to avoid
    false positives on ValidateStep SYS_CALL_VALIDATION description text.
  - G3: Multi-file node parsing — resolves node definitions across all
    .aisop.json files in the AIAP directory, not just the entry_path
    single file.

Reads node definition text for gate markers (or explicit user_gate flag),
cache status, and _index.json::user_gates_presented.
Exits non-zero when a sovereignty bypass is detected.

Exit codes:
    0  — PASS (no sovereignty bypass detected)
    1  — SOVEREIGNTY_BYPASS: user_gate=true node reached terminal
         status without ever presenting WAITING_USER
    2  — ARGUMENT_ERROR: missing/invalid CLI arguments
    3  — FILE_ERROR: required file not found or invalid JSON

Hash-neutral: governance_hash covers *.aisop.json only;
this python tool does not affect the hash.

Usage:
    python user_gate_audit.py \\
        --cache_dir=<path> \\
        --aiap=<aiap_name> \\
        --node=<node_name> \\
        --entry_path=<path_to_target_aisop>

Output (stdout): JSON
    { "status": "PASS"|"SOVEREIGNTY_BYPASS"|"ERROR",
      "node": "<node_name>",
      "user_gate": true|false|null,
      "gate_detection_method": "explicit_flag"|"text_marker"|null,
      "matched_markers": [...],
      "cache_status": "<status>"|null,
      "was_presented": true|false|null,
      "reason": "<human-readable>" }
"""

import argparse
import glob
import json
import os
import re
import sys
from pathlib import Path

# Make sibling python_tools importable (for agent_update_index in --enforce mode).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


# Gate-specific text markers that indicate a node requires user interaction.
# These are scanned in the node's step text and constraint text.
# IMPORTANT: sys.io.confirm/select are NOT in this list to avoid false
# positives on ValidateStep SYS_CALL_VALIDATION description text (FLAW 1).
_GATE_MARKERS = [
    r"USER_CONFIRMATION_MANDATORY",
    r"sovereignty_violation",
    r"auto_approve_attempt",
    r"WAITING_USER",               # as requirement text in step definitions
    r"\[GATE\]\s*User\s+reply\s+REQUIRED",
    r"step\d+\s+ENDS\s+HERE",
]
_GATE_PATTERN = re.compile("|".join(_GATE_MARKERS), re.IGNORECASE)


def _load_json(path: str) -> dict:
    """Load and parse a JSON file. Raises FileNotFoundError / json.JSONDecodeError."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_node_def_from_data(data: list, node_name: str) -> dict | None:
    """Extract node function definition from parsed AISOP data array."""
    for item in data:
        if item.get("role") != "user":
            continue
        functions = item.get("content", {}).get("functions", {})
        if node_name in functions:
            return functions[node_name]
    return None


def _scan_text_for_gate_markers(node_def: dict) -> list[str]:
    """
    Scan all step text and constraint text in a node definition for
    gate-specific markers. Returns list of matched marker strings.
    """
    matched = []
    texts_to_scan = []

    for key, value in node_def.items():
        if key.startswith("step") and isinstance(value, str):
            texts_to_scan.append(value)
        elif key == "constraints" and isinstance(value, str):
            texts_to_scan.append(value)

    combined_text = " ".join(texts_to_scan)
    for marker in _GATE_MARKERS:
        if re.search(marker, combined_text, re.IGNORECASE):
            matched.append(marker)

    return matched


def _collect_aisop_files(entry_path: str) -> list[str]:
    """
    G3: Collect all .aisop.json files in the same directory as entry_path.
    Returns a list of absolute paths, with entry_path first.
    """
    aiap_dir = os.path.dirname(os.path.abspath(entry_path))
    pattern = os.path.join(aiap_dir, "*.aisop.json")
    all_files = glob.glob(pattern)

    # Ensure entry_path is first (primary lookup)
    abs_entry = os.path.abspath(entry_path)
    result = [abs_entry]
    for f in sorted(all_files):
        abs_f = os.path.abspath(f)
        if abs_f != abs_entry:
            result.append(abs_f)

    return result


def _extract_user_gate(entry_path: str, node_name: str) -> tuple[bool | None, str | None, list[str]]:
    """
    Detect whether the given node requires a user gate.

    Detection methods (in priority order):
    1. Explicit user_gate:true field in node definition (backward compatible)
    2. Text-scanning for gate-specific markers in step/constraint text (G1)

    G3: Searches across all .aisop.json files in the AIAP directory,
    not just the entry_path single file.

    Returns:
        (gate_detected: bool|None, detection_method: str|None, matched_markers: list[str])
        - gate_detected: True if gate required, False if not, None if node not found
        - detection_method: 'explicit_flag' or 'text_marker' or None
        - matched_markers: list of marker patterns that matched (empty if explicit flag)
    """
    aisop_files = _collect_aisop_files(entry_path)

    for file_path in aisop_files:
        try:
            data = _load_json(file_path)
        except (FileNotFoundError, json.JSONDecodeError):
            continue

        node_def = _get_node_def_from_data(data, node_name)
        if node_def is None:
            continue

        # Method 1: Explicit user_gate:true flag (backward compatible)
        explicit_flag = node_def.get("user_gate")
        if explicit_flag is True:
            return (True, "explicit_flag", [])

        # Method 2: Text-scan for gate markers (G1 auto-detect)
        markers = _scan_text_for_gate_markers(node_def)
        if markers:
            return (True, "text_marker", markers)

        # Node found but no gate detected
        return (False, None, [])

    # Node not found in any file
    return (None, None, [])


# ---------------------------------------------------------------------------
# ENFORCE additions (plan20/24): on bypass, rewrite cache + _index to
# WAITING_USER so the existing resume flow re-collects the decision. Run by the
# sub-agent in agent_engine.writeCache (high execution depth) and/or node_engine.
# Reuses this file's G1 detection (_extract_user_gate) — single source.
# ---------------------------------------------------------------------------

_TERMINAL = {"PASS", "FAIL", "PARTIAL", "DEGRADED", "ABORTED"}
# Step that PRESENTS the gate + suspends (pause point). NOT sys.io.* (FLAW-1).
_PRESENT_MARKERS = [r"WAITING_USER", r"ENDS\s+HERE"]


def _atomic_write(path: str, data: dict) -> None:
    tmp = str(path) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _ordered_step_keys(node_def: dict) -> list:
    def sort_key(key: str):
        nums = re.findall(r"\d+", key)
        return tuple(int(n) for n in nums) if nums else (9999,)

    return sorted([k for k in node_def if k.startswith("step")], key=sort_key)


def _find_present_step(node_def: dict):
    for key in _ordered_step_keys(node_def):
        text = node_def.get(key, "")
        if isinstance(text, str) and any(
            re.search(m, text, re.IGNORECASE) for m in _PRESENT_MARKERS
        ):
            return key
    return None


def _node_def_for(entry_path: str, node: str):
    for fp in _collect_aisop_files(entry_path):
        try:
            data = _load_json(fp)
        except (FileNotFoundError, json.JSONDecodeError):
            continue
        nd = _get_node_def_from_data(data, node)
        if nd is not None:
            return nd
    return None


def _manufacture_question(cache: dict, node: str) -> str:
    """Surface what was auto-approved for the user to judge (no answer fabrication)."""
    plan = cache.get("evolution_plan") or {}
    items = []
    for tier in ("level_a", "level_b", "accepted_changes"):
        v = plan.get(tier)
        if isinstance(v, list):
            for it in v:
                items.append(
                    str(it.get("title") or it.get("id") or it)
                    if isinstance(it, dict) else str(it)
                )
    if items:
        detail = "; ".join(items)[:600]
    else:
        summ = cache.get("user_summary") or cache.get("output") or ""
        detail = summ[:600] if isinstance(summ, str) else ""
    return (
        f"[公理 0 人类主权与福祉] 节点 '{node}' 到达终态却未经 WAITING_USER "
        f"呈现给你确认（sovereignty bypass）。以下内容被自批准、未经你确认："
        f"{detail}。请回复：批准 / 修改 / 拒绝。"
    )


def enforce(cache_dir: str, aiap: str, node: str, entry_path: str) -> dict:
    """On bypass, authoritatively rewrite cache file + _index to WAITING_USER.

    FLAW-A: also override _index::nodes_status (agent_update_index merged the
      sub-agent's PASS) and un-advance last_completed_node.
    FLAW-B: steps_done THROUGH the present step, steps_remaining FROM the collect
      step (NOT a full reset -> avoids double-present on resume).
    """
    cache_path = os.path.join(cache_dir, f"{aiap}.{node}.json")
    cache = _load_json(cache_path)

    node_def = _node_def_for(entry_path, node) or {}
    steps = _ordered_step_keys(node_def)
    present = _find_present_step(node_def)
    if present and present in steps:
        i = steps.index(present)
        steps_done = steps[: i + 1]
        steps_remaining = steps[i + 1:]
    else:
        steps_done, steps_remaining = [], steps  # fallback: conservative full re-run

    question = _manufacture_question(cache, node)
    cache["bypassed_status"] = cache.get("status")
    cache["bypassed_output"] = cache.get("output")
    if "evolution_plan" in cache:
        cache["evolution_plan_stale"] = True
    cache["status"] = "WAITING_USER"
    cache["completed"] = False
    cache["waiting_user"] = True
    cache["question"] = question
    cache["steps_done"] = steps_done
    cache["steps_remaining"] = steps_remaining
    cache["sovereignty_coercion"] = True
    cache["sovereignty_bypass_detected"] = True
    _atomic_write(cache_path, cache)

    idx_path = os.path.join(cache_dir, "_index.json")
    updated_via = "direct"
    idx = _load_json(idx_path)
    upd = {"nodes_status": {node: {"status": "WAITING_USER"}}}
    if idx.get("last_completed_node") == node:
        nip = idx.get("nodes_in_path") or []
        upd["last_completed_node"] = (
            nip[nip.index(node) - 1] if node in nip and nip.index(node) > 0 else None
        )
    try:
        from agent_update_index import update_index  # type: ignore

        r = update_index(Path(cache_dir), upd)
        if isinstance(r, dict) and r.get("status") == "ok":
            updated_via = "agent_update_index"
        else:
            raise RuntimeError(str(r))
    except Exception:
        idx = _load_json(idx_path)
        idx.setdefault("nodes_status", {})[node] = {"status": "WAITING_USER"}
        if "last_completed_node" in upd:
            idx["last_completed_node"] = upd["last_completed_node"]
        _atomic_write(idx_path, idx)

    return {
        "enforced": True,
        "steps_done": steps_done,
        "steps_remaining": steps_remaining,
        "present_step": present,
        "index_updated_via": updated_via,
        "question": question,
    }


def audit(cache_dir: str, aiap: str, node: str, entry_path: str) -> dict:
    """
    Core audit logic.  Returns a result dict suitable for JSON stdout.
    v5.12.0: uses auto-detection (text markers) in addition to explicit flag.
    """
    result = {
        "status": "PASS",
        "node": node,
        "user_gate": None,
        "gate_detection_method": None,
        "matched_markers": [],
        "cache_status": None,
        "was_presented": None,
        "reason": "",
    }

    # 1. Detect user gate requirement (G1 auto-detect + G3 multi-file)
    user_gate, detection_method, matched_markers = _extract_user_gate(entry_path, node)
    result["user_gate"] = user_gate
    result["gate_detection_method"] = detection_method
    result["matched_markers"] = matched_markers

    if not user_gate:
        # user_gate is False or None -> nothing to audit
        method_note = ""
        if user_gate is None:
            method_note = " (node not found in any .aisop.json file)"
        else:
            method_note = " (no explicit user_gate flag or gate text markers detected)"
        result["reason"] = (
            f"Node '{node}' does not require a user gate{method_note}; audit skipped."
        )
        return result

    # 2. Read node cache to get terminal status
    cache_path = os.path.join(cache_dir, f"{aiap}.{node}.json")
    try:
        cache = _load_json(cache_path)
    except FileNotFoundError:
        result["status"] = "ERROR"
        result["reason"] = f"Cache file not found: {cache_path}"
        return result
    except json.JSONDecodeError:
        result["status"] = "ERROR"
        result["reason"] = f"Cache file is invalid JSON: {cache_path}"
        return result

    cache_status = cache.get("status")
    result["cache_status"] = cache_status

    # Terminal statuses that indicate the node has finished
    terminal = {"PASS", "FAIL", "PARTIAL", "DEGRADED", "ABORTED"}
    if cache_status not in terminal:
        # Node is not terminal (e.g. WAITING_USER, MESSAGE_PENDING) -> OK
        result["reason"] = (
            f"Node '{node}' status is '{cache_status}' (non-terminal); "
            "audit not applicable."
        )
        return result

    # 3. Check _index.json::user_gates_presented for evidence of
    #    prior WAITING_USER presentation
    index_path = os.path.join(cache_dir, "_index.json")
    try:
        index = _load_json(index_path)
    except (FileNotFoundError, json.JSONDecodeError):
        result["status"] = "ERROR"
        result["reason"] = f"Cannot read _index.json at {index_path}"
        return result

    presented = index.get("user_gates_presented", {})
    # Support both formats: array of objects [{node_name: ...}] and dict {node: ...}
    if isinstance(presented, list):
        was_presented = any(
            (entry.get("node_name") == node if isinstance(entry, dict) else entry == node)
            for entry in presented
        )
    else:
        was_presented = node in presented
    result["was_presented"] = was_presented

    if was_presented:
        gate_desc = (
            f"user_gate=true (detected via {detection_method})"
            if detection_method
            else "user_gate=true"
        )
        result["reason"] = (
            f"Node '{node}' ({gate_desc}) reached '{cache_status}' "
            "AND was previously presented as WAITING_USER. "
            "Sovereignty preserved."
        )
        return result

    # 4. SOVEREIGNTY BYPASS DETECTED
    gate_desc = (
        f"detected via {detection_method}"
        + (f", markers: {matched_markers}" if matched_markers else "")
        if detection_method
        else "user_gate=true"
    )
    result["status"] = "SOVEREIGNTY_BYPASS"
    result["reason"] = (
        f"SOVEREIGNTY_BYPASS: Node '{node}' requires user gate "
        f"({gate_desc}) "
        f"and reached terminal status '{cache_status}' "
        "WITHOUT ever presenting WAITING_USER to the user. "
        "This violates Axiom 0 (Human Sovereignty). "
        "The node must present a WAITING_USER gate before "
        "reaching a terminal status."
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="User gate sovereignty audit tool"
    )
    parser.add_argument("--cache_dir", required=True, help="Execution cache directory")
    parser.add_argument("--aiap", required=True, help="AIAP package name")
    parser.add_argument("--node", required=True, help="Node name to audit")
    parser.add_argument("--entry_path", required=True, help="Path to target AIAP entry file")
    parser.add_argument("--json", action="store_true", help="Force JSON output (default)")
    parser.add_argument("--enforce", action="store_true",
                        help="On SOVEREIGNTY_BYPASS, rewrite cache + _index to WAITING_USER (plan20/24).")

    args = parser.parse_args()

    try:
        result = audit(args.cache_dir, args.aiap, args.node, args.entry_path)
    except Exception as exc:
        result = {
            "status": "ERROR",
            "node": args.node,
            "user_gate": None,
            "cache_status": None,
            "was_presented": None,
            "reason": f"Unexpected error: {exc}",
        }

    if result["status"] == "SOVEREIGNTY_BYPASS" and args.enforce:
        try:
            result["enforcement"] = enforce(args.cache_dir, args.aiap, args.node, args.entry_path)
        except Exception as exc:
            result["enforcement"] = {"enforced": False, "error": str(exc)}

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] == "SOVEREIGNTY_BYPASS":
        sys.exit(1)
    elif result["status"] == "ERROR":
        sys.exit(3)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
