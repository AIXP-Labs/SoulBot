#!/usr/bin/env python3
"""dispatch_audit.py -- Audit a run's node caches for dispatch integrity (v5.6.0).

v5.6.0 CHANGE: Restored fallback statistics with legit/illegitimate classification.
  - Retained: integrity_violation category (expected vs actual agent_id comparison)
  - Retained: timestamp ordering verification (spawned_at > generated_at)
  - Added (A3 v5.6.0): legit_fallback vs illegitimate_fallback classification
    inline_fallback + valid spawn_failure_evidence -> legit_fallback (acceptable)
    inline_fallback + missing/invalid spawn_failure_evidence -> illegitimate_fallback (violation)
  - illegitimate_fallback > 0 -> severity >= WARN
  - illegitimate_fallback / total > 10% -> CRITICAL

Server-side agent_id generation (agent_id_generator.py) means host AI cannot
self-report agent_id. Audit now verifies: cache.agent_id == expected_agent_id,
AND for inline_fallback nodes, verifies spawn_failure_evidence is present and valid.

Usage:
  python dispatch_audit.py --cache_dir=<run_dir>

Output (human-readable to stdout, plus JSON summary with --json):
  === Dispatch Audit v5.6.0: <run_dir> ===
  Total nodes executed: N
  Integrity violations: V
  Legit fallbacks: L
  Illegitimate fallbacks: I
  INTEGRITY RATE: P% [OK | WARN | CRITICAL]

Threshold:
  0 integrity_violations AND 0 illegitimate_fallback -> OK
  illegitimate_fallback > 0 OR integrity_violations <= 10% -> WARN
  illegitimate_fallback / total > 10% OR integrity_violations > 10% -> CRITICAL

Exit codes:
  0  OK
  1  WARN
  2  CRITICAL
  3  argument error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from cache_tool_lib import validate_spawn_failure_evidence  # noqa: E402


def _load_index(cache_dir: str) -> Dict:
    """Load _index.json from cache directory."""
    index_path = os.path.join(cache_dir, "_index.json")
    if not os.path.isfile(index_path):
        return {}
    try:
        with open(index_path, encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return {}


def _get_expected_agent_id(index: Dict, node_name: str) -> str | None:
    """Get expected_agent_id from dispatch_plan or dispatch_records.

    Priority:
      1. dispatch_plan[node].expected_agent_id (set by agent_id_generator.py)
      2. dispatch_records[node].expected_agent_id (backup source)
    For inline nodes (execute_mode=inline): expected is 'inline_planned'.
    """
    # Check dispatch_plan
    plan = index.get("dispatch_plan", {})
    if isinstance(plan, dict):
        entry = plan.get(node_name)
        if isinstance(entry, dict):
            eid = entry.get("expected_agent_id")
            if eid:
                return eid
            # Inline node
            if entry.get("execute_mode") == "inline":
                return "inline_planned"
        elif isinstance(entry, str) and entry == "inline":
            return "inline_planned"

    # Check dispatch_records
    records = index.get("dispatch_records", {})
    if isinstance(records, dict):
        record = records.get(node_name)
        if isinstance(record, dict):
            return record.get("expected_agent_id")

    return None


def _check_timestamp_ordering(index: Dict, cache: Dict, node_name: str) -> str | None:
    """A4 v5.5.0: Verify spawned_at > generated_at ordering invariant.

    Returns violation description or None if OK.
    """
    records = index.get("dispatch_records", {})
    if not isinstance(records, dict):
        return None
    record = records.get(node_name)
    if not isinstance(record, dict):
        return None

    generated_at = record.get("generated_at", "")
    if not generated_at:
        return None

    trail = cache.get("spawn_audit_trail")
    if not isinstance(trail, dict):
        return None

    spawned_at = trail.get("spawned_at", "")
    if not spawned_at:
        return None

    try:
        gen_time = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        spawn_time = datetime.fromisoformat(spawned_at.replace("Z", "+00:00"))
        if spawn_time <= gen_time:
            return (
                f"timestamp_ordering_violation: spawned_at ({spawned_at}) "
                f"<= generated_at ({generated_at}). "
                "Sub-agent spawn must occur AFTER agent_id generation."
            )
    except (ValueError, TypeError):
        return f"timestamp_parse_error: could not parse timestamps for ordering check"

    return None


def _validate_spawn_failure_evidence(cache: Dict, index: Dict, node_name: str) -> str:
    """Validate spawn_failure_evidence for inline_fallback nodes (A3 v5.6.0).

    Q2 v5.6.0: Delegates to shared validate_spawn_failure_evidence from cache_tool_lib.py,
    eliminating duplicated schema/enum/temporal validation logic.

    Returns:
        'legit' if evidence is present and valid
        'illegitimate' if evidence is missing or invalid
        'not_applicable' if node is not inline_fallback
    """
    agent_id = (cache.get("agent_id") or "").strip()
    if agent_id != "inline_fallback":
        return "not_applicable"

    # Check if dispatch_plan says 'agent' for this node
    plan = index.get("dispatch_plan", {})
    if isinstance(plan, dict):
        entry = plan.get(node_name)
        plan_mode = None
        if isinstance(entry, dict):
            plan_mode = entry.get("execute_mode")
        elif isinstance(entry, str):
            plan_mode = entry
        if plan_mode != "agent":
            return "not_applicable"

    # Get generated_at for temporal ordering check
    generated_at = ""
    records = index.get("dispatch_records", {})
    if isinstance(records, dict):
        record = records.get(node_name)
        if isinstance(record, dict):
            generated_at = record.get("generated_at", "")

    sfe = cache.get("spawn_failure_evidence")
    sfe_valid, _reason = validate_spawn_failure_evidence(sfe, generated_at)
    return "legit" if sfe_valid else "illegitimate"


def scan(cache_dir: str) -> Tuple[Dict, List[Dict]]:
    """Walk cache_dir, check each node cache for integrity violations.

    v5.6.0: integrity_violation + legit/illegitimate fallback classification.
    For each node: expected_agent_id (from _index.json) vs actual (from cache).
    For inline_fallback nodes: verify spawn_failure_evidence presence and validity.

    Returns (summary_counts, violations_list).
    """
    index = _load_index(cache_dir)
    total_nodes = 0
    integrity_violations = 0
    legit_fallbacks = 0
    illegitimate_fallbacks = 0
    violations: List[Dict] = []

    if not os.path.isdir(cache_dir):
        return {"total_nodes": 0, "integrity_violations": 0,
                "legit_fallbacks": 0, "illegitimate_fallbacks": 0}, violations

    for fn in sorted(os.listdir(cache_dir)):
        if not fn.endswith(".json"):
            continue
        if fn in ("_index.json", "conversation_context.json", "node_cache.schema.json"):
            continue
        if fn.startswith("_"):
            continue

        path = os.path.join(cache_dir, fn)
        try:
            with open(path, encoding="utf-8") as fp:
                cache = json.load(fp)
        except Exception:
            continue
        if not isinstance(cache, dict):
            continue

        total_nodes += 1

        # Extract node name from filename: {aiap_name}.{NodeName}.json -> NodeName
        parts = fn.rsplit(".", 2)
        node_name = parts[-2] if len(parts) >= 3 else fn.replace(".json", "")

        actual_agent_id = (cache.get("agent_id") or "").strip()
        expected_agent_id = _get_expected_agent_id(index, node_name)

        # Integrity check: expected vs actual agent_id
        if expected_agent_id is not None and actual_agent_id != expected_agent_id:
            integrity_violations += 1
            violations.append({
                "node": node_name,
                "expected": expected_agent_id,
                "actual": actual_agent_id,
                "evidence_cache": fn,
                "violation_type": "integrity_violation",
            })

        # Timestamp ordering check (A4 v5.5.0)
        ts_violation = _check_timestamp_ordering(index, cache, node_name)
        if ts_violation:
            integrity_violations += 1
            violations.append({
                "node": node_name,
                "expected": "spawned_at > generated_at",
                "actual": ts_violation,
                "evidence_cache": fn,
                "violation_type": "timestamp_ordering_violation",
            })

        # Fallback classification (A3 v5.6.0)
        fallback_class = _validate_spawn_failure_evidence(cache, index, node_name)
        if fallback_class == "legit":
            legit_fallbacks += 1
        elif fallback_class == "illegitimate":
            illegitimate_fallbacks += 1
            violations.append({
                "node": node_name,
                "expected": "spawn_failure_evidence with valid fields",
                "actual": "inline_fallback without valid spawn_failure_evidence",
                "evidence_cache": fn,
                "violation_type": "illegitimate_fallback",
            })

    counts = {
        "total_nodes": total_nodes,
        "integrity_violations": integrity_violations,
        "legit_fallbacks": legit_fallbacks,
        "illegitimate_fallbacks": illegitimate_fallbacks,
    }
    return counts, violations


def severity(integrity_rate: float, illegitimate_rate: float, illegitimate_count: int) -> Tuple[str, int]:
    """Severity thresholds for integrity violation rate + illegitimate fallback rate.

    v5.6.0: illegitimate_fallback > 0 -> at least WARN.
    illegitimate_rate > 10% OR integrity_rate > 10% -> CRITICAL.
    """
    if integrity_rate == 0.0 and illegitimate_count == 0:
        return "OK", 0
    if illegitimate_rate > 0.10 or integrity_rate > 0.10:
        return "CRITICAL", 2
    return "WARN", 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit run dir for dispatch integrity (v5.6.0)"
    )
    parser.add_argument("--cache_dir", required=True, help="Path to run cache directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary to stdout")
    args = parser.parse_args()

    cache_dir = args.cache_dir
    if not os.path.isdir(cache_dir):
        print(f"ERROR: cache_dir not found: {cache_dir}", file=sys.stderr)
        return 3

    counts, violations = scan(cache_dir)
    total = counts["total_nodes"]
    integrity_violations = counts["integrity_violations"]
    legit_fallbacks = counts["legit_fallbacks"]
    illegitimate_fallbacks = counts["illegitimate_fallbacks"]

    if total == 0:
        print(f"ERROR: no node cache files found in {cache_dir}", file=sys.stderr)
        return 3

    # v5.6.0: Combined formula
    integrity_rate = integrity_violations / total if total else 0.0
    illegitimate_rate = illegitimate_fallbacks / total if total else 0.0
    fallback_rate = (legit_fallbacks + illegitimate_fallbacks) / total if total else 0.0
    sev, exit_code = severity(integrity_rate, illegitimate_rate, illegitimate_fallbacks)

    summary: Dict = {
        "cache_dir": cache_dir,
        "audit_version": "5.6.0",
        "total_nodes": total,
        "integrity_violations": integrity_violations,
        "legit_fallbacks": legit_fallbacks,
        "illegitimate_fallbacks": illegitimate_fallbacks,
        "fallback_rate_pct": round(fallback_rate * 100, 1),
        "integrity_rate_pct": round(integrity_rate * 100, 1),
        "illegitimate_rate_pct": round(illegitimate_rate * 100, 1),
        "severity": sev,
    }
    if violations:
        summary["violations"] = violations

    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"=== Dispatch Audit v5.6.0: {cache_dir} ===")
        print(f"Total nodes executed:      {total}")
        print(f"Integrity violations:      {integrity_violations}")
        print(f"Legit fallbacks:           {legit_fallbacks}")
        print(f"Illegitimate fallbacks:    {illegitimate_fallbacks}")
        print(f"INTEGRITY RATE: {integrity_rate * 100:.1f}% [{sev}]")
        print(f"FALLBACK RATE:  {fallback_rate * 100:.1f}%")
        if violations:
            print()
            print("Violation details:")
            for v in violations:
                print(
                    f"  {v['node']}: expected={v['expected']}, "
                    f"actual={v['actual']}, type={v['violation_type']}"
                )

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
