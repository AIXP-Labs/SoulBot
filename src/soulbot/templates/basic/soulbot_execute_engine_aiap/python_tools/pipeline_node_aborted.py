#!/usr/bin/env python3
"""pipeline_node_aborted — close observation as ERROR with reason.

Doc 19 v1.0: subprocess CLI invoked by LLM via Bash tool.

Use only when the node was previously announced via node_audit_started
but cannot reach writeCache (e.g. circuit breaker halts the half-open test,
on_error escalates to fatal). If a node is skipped BEFORE node_started
fired, do NOT call this — there is no open observation to close.

Usage:
    python pipeline_node_aborted.py \\
        --aisop=soulbot_cognitive_cycle \\
        --node_name=Perceive \\
        [--reason=half_open_test_failed]

stdout (single line JSON, exit code 0):
    {"audit_end": "aborted", "node_name": "<n>",
     "node_assert": "node aborted, continue strictly execute .aisop.json program file"}
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback

from _pipeline_state_audit import (
    append_span,
    clear_retry,
    close_node_state,
    get_audit_id,
    get_open_cache_path,
    get_opened_at,
    get_retry_count,
    append_audit_record,
    resolve_trace_context,
)


def main() -> int:
    p = argparse.ArgumentParser(description="Abort AIAP node observation")
    p.add_argument("--aisop", required=True)
    p.add_argument("--node_name", required=True)
    p.add_argument("--reason", default="")
    p.add_argument(
        "--traceparent", default="",
        help=("W3C traceparent for trace context continuation "
              "(env TRACEPARENT as fallback; Doc 22 P1)"),
    )
    args = p.parse_args()

    if not args.aisop or not args.node_name:
        print(json.dumps({
            "audit_end": "aborted",
            "node_name": args.node_name,
            "node_assert": "missing required field: aisop and node_name must be non-empty",
        }, ensure_ascii=False))
        return 2

    # Capture state snapshot BEFORE close_node_state clears it
    audit_id = get_audit_id(args.aisop, args.node_name)
    opened_at = get_opened_at(args.aisop, args.node_name)
    cache_path = get_open_cache_path(args.aisop, args.node_name)
    retry_count_final = get_retry_count(args.aisop, args.node_name)

    clear_retry(args.aisop, args.node_name)
    close_node_state(args.aisop, args.node_name)

    description = f"aborted: {args.reason}" if args.reason else "aborted"
    tid, psid = resolve_trace_context(args.traceparent)
    append_span(
        name=f"pipeline.node {args.aisop}.{args.node_name}",
        attributes={
            "soulbot.aisop.name": args.aisop,
            "soulbot.node.name": args.node_name,
            "soulbot.node.status": "ABORTED",
            "soulbot.node.aborted_reason": args.reason,
            "soulbot.node.audit_id": audit_id,
        },
        status="ERROR",
        description=description,
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
        verdict="ABORTED",
        cache_exists_at_end=False,
        retry_count_final=retry_count_final,
        reason=args.reason,
    )

    response = {
        "audit_end": "aborted",
        "node_name": args.node_name,
        "node_assert": "node aborted, continue strictly execute .aisop.json program file",
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({
            "audit_end": "aborted",
            "node_name": "",
            "node_assert": f"pipeline_node_aborted crashed: {exc}",
            "_traceback": traceback.format_exc(),
        }, ensure_ascii=False))
        sys.exit(1)
