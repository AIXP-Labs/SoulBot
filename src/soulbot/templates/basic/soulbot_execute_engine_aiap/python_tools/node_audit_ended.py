#!/usr/bin/env python3
"""node_audit_ended — verify cache and emit audit verdict.

Doc 19 v1.0: subprocess CLI invoked by LLM via Bash tool.

Usage:
    python node_audit_ended.py \\
        --aisop=soulbot_cognitive_cycle \\
        --node_name=Perceive \\
        --cache_path=<absolute_path_to_node_cache_json> \\
        [--max_retry=3]

stdout (single line JSON, exit code 0):
    {"audit_end": true|false|"degraded", "node_name": "<n>", "audit_id": "audit_<8hex>", "node_assert": "<directive>"}

Verdict rules:
  - cache file exists                      → audit_end:true,  span PASS
  - missing AND retries < MAX_RETRY        → audit_end:false, retry counter ++
  - missing AND retries >= MAX_RETRY - 1   → audit_end:"degraded", span DEGRADED
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from _pipeline_state_audit import (
    append_span,
    clear_retry,
    close_node_state,
    get_audit_id,
    get_open_cache_path,
    get_opened_at,
    get_retry_count,
    increment_retry,
    is_node_open,
    append_audit_record,
    resolve_trace_context,
)


DEFAULT_MAX_RETRY = 3


def main() -> int:
    p = argparse.ArgumentParser(description="End AIAP node observation + cache audit")
    p.add_argument("--aisop", required=True)
    p.add_argument("--node_name", required=True)
    p.add_argument("--cache_path", default="")
    p.add_argument("--max_retry", type=int, default=DEFAULT_MAX_RETRY)
    p.add_argument(
        "--traceparent", default="",
        help=("W3C traceparent for trace context continuation "
              "(env TRACEPARENT as fallback; Doc 22 P1)"),
    )
    args = p.parse_args()

    if not args.aisop or not args.node_name:
        print(json.dumps({
            "audit_end": False,
            "node_name": args.node_name,
            "node_assert": "missing required field: aisop and node_name must be non-empty",
        }, ensure_ascii=False))
        return 2

    if args.max_retry < 1:
        print(json.dumps({
            "audit_end": False,
            "node_name": args.node_name,
            "node_assert": f"invalid --max_retry={args.max_retry}, must be >= 1",
        }, ensure_ascii=False))
        return 2

    # Orphan guard: node_audit_ended can only be called AFTER
    # node_audit_started has run for this (aisop, node_name). If
    # there is no corresponding open_nodes entry, the LLM is fabricating
    # the call without the real started observation — refuse.
    if not is_node_open(args.aisop, args.node_name):
        print(json.dumps({
            "audit_end": False,
            "node_name": args.node_name,
            "node_assert": (
                "[ORPHAN CALL] node_audit_started was never invoked for "
                f"({args.aisop}, {args.node_name}). You MUST call "
                "node_audit_started FIRST and OUTPUT its stdout verbatim "
                "(including the audit_id) before calling "
                "node_audit_ended. Fabricating audit_id or skipping "
                "node_started is forbidden."
            ),
        }, ensure_ascii=False))
        return 2

    audit_id = get_audit_id(args.aisop, args.node_name)

    # Fall back to the cache_path captured at node_started time
    cache_path = args.cache_path
    if not cache_path:
        cache_path = get_open_cache_path(args.aisop, args.node_name)

    cache_path = str(Path(cache_path).resolve()) if cache_path else ""
    cache_exists = bool(cache_path) and Path(cache_path).exists()

    if cache_exists:
        opened_at = get_opened_at(args.aisop, args.node_name)
        retry_count_final = get_retry_count(args.aisop, args.node_name)
        clear_retry(args.aisop, args.node_name)
        close_node_state(args.aisop, args.node_name)
        tid, psid = resolve_trace_context(args.traceparent)
        append_span(
            name=f"pipeline.node {args.aisop}.{args.node_name}",
            attributes={
                "soulbot.aisop.name": args.aisop,
                "soulbot.node.name": args.node_name,
                "soulbot.execution.cache_path": cache_path,
                "soulbot.node.status": "PASS",
                "soulbot.node.audit_id": audit_id,
            },
            status="OK",
            trace_id=tid,
            parent_span_id=psid,
            start_time_ns=int(opened_at * 1e9) if opened_at else None,
        )
        append_audit_record(
            cache_path,
            audit_id=audit_id,
            aisop=args.aisop,
            node_name=args.node_name,
            opened_at=opened_at,
            verdict="PASS",
            cache_exists_at_end=True,
            retry_count_final=retry_count_final,
        )
        response = {
            "audit_end": True,
            "node_name": args.node_name,
            "audit_id": audit_id,
            "node_assert": "node audit success, Strictly execute the soulbot_execute_engine node-by-node; never batch, skip, or fake the audit loop. Never fabricate cache content, validation reports, or tool_calls counts.",
        }
        print(json.dumps(response, ensure_ascii=False))
        return 0

    # ---- cache missing ----
    retries = get_retry_count(args.aisop, args.node_name)
    increment_retry(args.aisop, args.node_name)

    if retries >= args.max_retry - 1:
        # DEGRADED — exhaust retries, do not block main flow
        opened_at = get_opened_at(args.aisop, args.node_name)
        clear_retry(args.aisop, args.node_name)
        close_node_state(args.aisop, args.node_name)
        tid, psid = resolve_trace_context(args.traceparent)
        append_span(
            name=f"pipeline.node {args.aisop}.{args.node_name}",
            attributes={
                "soulbot.aisop.name": args.aisop,
                "soulbot.node.name": args.node_name,
                "soulbot.execution.cache_path": cache_path,
                "soulbot.node.status": "DEGRADED",
                "soulbot.node.degraded_reason": "max_retries_reached",
                "soulbot.node.retry_count": retries + 1,
            },
            status="ERROR",
            description=f"degraded: max_retries_reached ({args.max_retry})",
            trace_id=tid,
            parent_span_id=psid,
            start_time_ns=int(opened_at * 1e9) if opened_at else None,
        )
        append_audit_record(
            cache_path,
            audit_id=audit_id,
            aisop=args.aisop,
            node_name=args.node_name,
            opened_at=opened_at,
            verdict="DEGRADED",
            cache_exists_at_end=False,
            retry_count_final=retries + 1,
            reason="max_retries_reached",
        )
        response = {
            "audit_end": "degraded",
            "node_name": args.node_name,
            "audit_id": audit_id,
            "node_assert": (
                f"exceeded max retries ({args.max_retry}), marked DEGRADED, "
                f"continue strictly execute .aisop.json program file"
            ),
        }
    else:
        # Retry: tell LLM to re-execute the node; do NOT close span / clear retry
        remaining = args.max_retry - retries - 1
        response = {
            "audit_end": False,
            "node_name": args.node_name,
            "audit_id": audit_id,
            "node_assert": (
                f"[ASSERT] cache not generated correctly. You MUST strictly "
                f"re-execute each step in node (init -> execute -> review -> writeCache) "
                f"and use the exact absolute cache_path echoed in this request. "
                f"Remaining retries: {remaining}/{args.max_retry}"
            ),
        }

    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({
            "audit_end": False,
            "node_name": "",
            "node_assert": f"node_audit_ended crashed: {exc}",
            "_traceback": traceback.format_exc(),
        }, ensure_ascii=False))
        sys.exit(1)
