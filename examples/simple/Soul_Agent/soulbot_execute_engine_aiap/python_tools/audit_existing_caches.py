#!/usr/bin/env python3
"""audit_existing_caches.py — Bulk audit of existing cache files against JSON Schema.

Non-invasive audit tool.

Walks the .execution_cache/ of each agent, classifies each JSON file
by name (_index.json / conversation_context.json / {aiap}.{Node}.json),
runs schema validation, and emits per-agent + per-category statistics.

Usage:
  python audit_existing_caches.py [--root <agents_dir>] [--json]

Default --root scans ../../../examples/simple/{agent_dir}/soulbot_execute_engine_aiap/.execution_cache/

Output:
  Per-agent breakdown of: total / valid / invalid_json / schema_violation.
  Top error categories.
  Path to top-5 worst files (most errors).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Allow running from anywhere
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from json_schema_validator import validate_cache_file  # noqa: E402


def classify_file(path: Path) -> str | None:
    """Return schema type name or None to skip."""
    name = path.name
    if name == "_index.json":
        return "_index"
    if name == "conversation_context.json":
        return "conversation_context"
    # Node cache: {aiap}.{Node}.json — exclude reports like nihil_scan_results.json
    if name.endswith(".json") and "." in name[:-5]:  # has internal dot besides .json
        # Exclude known non-node files
        if name in ("nihil_scan_results.json",):
            return None
        return "node_cache"
    return None


def audit_agent(agent_cache_root: Path) -> dict:
    """Audit one agent's .execution_cache/ directory."""
    stats = {
        "total": 0,
        "valid": 0,
        "invalid_json": 0,
        "schema_violation": 0,
        "by_schema": defaultdict(lambda: {"total": 0, "valid": 0, "invalid_json": 0, "schema_violation": 0}),
    }
    error_categories: Counter = Counter()
    worst_files: list[tuple[int, dict]] = []  # (error_count, result)

    for path in sorted(agent_cache_root.rglob("*.json")):
        schema_type = classify_file(path)
        if schema_type is None:
            continue

        result = validate_cache_file(path, schema_type)
        stats["total"] += 1
        stats["by_schema"][schema_type]["total"] += 1

        if not result["raw_parseable"]:
            stats["invalid_json"] += 1
            stats["by_schema"][schema_type]["invalid_json"] += 1
            error_categories["INVALID_JSON"] += 1
        elif not result["valid"]:
            stats["schema_violation"] += 1
            stats["by_schema"][schema_type]["schema_violation"] += 1
            # Categorize errors
            for err in result["errors"]:
                # Take prefix before ':' as category
                cat = err.split(":")[0] if ":" in err else err[:40]
                # Further simplify: take last segment after $.
                # e.g. "$.dispatch_plan.Start" -> "dispatch_plan.*"
                if cat.startswith("$."):
                    parts = cat[2:].split(".")
                    if len(parts) >= 2 and parts[1] not in ("turns", "items"):
                        cat = f"$.{parts[0]}.<key>"
                error_categories[cat] += 1
        else:
            stats["valid"] += 1
            stats["by_schema"][schema_type]["valid"] += 1

        if not result["valid"] and len(result["errors"]) > 0:
            worst_files.append((len(result["errors"]), result))

    worst_files.sort(key=lambda t: -t[0])
    stats["error_categories"] = dict(error_categories.most_common(10))
    stats["worst_files"] = [
        {"file": w[1]["file"], "error_count": w[0], "first_error": w[1]["errors"][0]}
        for w in worst_files[:5]
    ]
    return stats


def print_agent_report(name: str, stats: dict, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps({name: stats}, indent=2, default=dict, ensure_ascii=False))
        return

    total = stats["total"]
    pct_invalid = (stats["invalid_json"] / max(total, 1)) * 100
    pct_violation = (stats["schema_violation"] / max(total, 1)) * 100
    pct_valid = (stats["valid"] / max(total, 1)) * 100

    print(f"\n=== {name} ===")
    print(f"  Total cache files:       {total}")
    print(f"  Invalid JSON:            {stats['invalid_json']:4d}  ({pct_invalid:5.1f}%)")
    print(f"  Schema violation:        {stats['schema_violation']:4d}  ({pct_violation:5.1f}%)")
    print(f"  Valid:                   {stats['valid']:4d}  ({pct_valid:5.1f}%)")

    print(f"  By schema:")
    for schema_type, s in stats["by_schema"].items():
        s = dict(s)
        print(
            f"    {schema_type:30s}  total={s['total']:3d}  invalid_json={s['invalid_json']:3d}  "
            f"schema_viol={s['schema_violation']:3d}  valid={s['valid']:3d}"
        )

    if stats["error_categories"]:
        print(f"  Top error categories:")
        for cat, count in stats["error_categories"].items():
            print(f"    {count:4d}x  {cat}")

    if stats["worst_files"]:
        print(f"  Worst files (top 5):")
        for w in stats["worst_files"]:
            print(f"    {w['error_count']:3d} errors  {w['file']}")
            print(f"             {w['first_error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit existing SoulBot cache files.")
    parser.add_argument(
        "--root",
        default=None,
        help="Path to agents_dir (default: search examples/simple under cwd).",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    if args.root:
        agents_dir = Path(args.root)
    else:
        # Try common paths
        for candidate in [Path("examples/simple"), Path("../../../examples/simple"), Path("../../examples/simple")]:
            if candidate.is_dir():
                agents_dir = candidate
                break
        else:
            print("ERROR: Could not auto-locate agents_dir. Pass --root.", file=sys.stderr)
            return 2

    overall = {"agents": {}, "summary": {"total": 0, "valid": 0, "invalid_json": 0, "schema_violation": 0}}

    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        cache_root = agent_dir / "soulbot_execute_engine_aiap" / ".execution_cache"
        if not cache_root.is_dir():
            continue
        stats = audit_agent(cache_root)
        overall["agents"][agent_dir.name] = stats
        print_agent_report(agent_dir.name, stats, as_json=args.json)
        for k in ("total", "valid", "invalid_json", "schema_violation"):
            overall["summary"][k] += stats[k]

    if not args.json:
        s = overall["summary"]
        total = s["total"]
        print(f"\n=== Overall ({len(overall['agents'])} agents) ===")
        print(f"  Total cache files:       {total}")
        if total > 0:
            print(f"  Invalid JSON:            {s['invalid_json']:4d}  ({s['invalid_json']/total*100:5.1f}%)")
            print(f"  Schema violation:        {s['schema_violation']:4d}  ({s['schema_violation']/total*100:5.1f}%)")
            print(f"  Valid:                   {s['valid']:4d}  ({s['valid']/total*100:5.1f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
