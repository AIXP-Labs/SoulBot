#!/usr/bin/env python3
"""node_audit_started — open observation marker for an AIAP node.

Doc 19 v1.0: subprocess CLI invoked by LLM via Bash tool. The LLM gets
the JSON response on stdout in the SAME message turn (Bash is a real
ACP tool with mid-message suspend semantics).

Usage:
    python node_audit_started.py \\
        --aisop=soulbot_cognitive_cycle \\
        --node_name=Perceive \\
        --cache_path=<absolute_path_to_node_cache_json>

stdout (single line JSON, exit code 0):
    {"audit_start": true, "node_name": "<n>",
     "audit_id": "audit_<8hex>",
     "node_assert": "monitoring started, strictly execute each step in node"}

On argparse / unexpected error, returns non-zero and writes a JSON error
envelope to stdout so the LLM can still parse uniformly.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
import uuid
from pathlib import Path

# Local sibling import. python_tools/ is on sys.path because the script
# is launched as `python node_audit_started.py ...` from that dir.
from _pipeline_state_audit import open_node_state


def main() -> int:
    p = argparse.ArgumentParser(description="Open AIAP node observation")
    p.add_argument("--aisop", required=True)
    p.add_argument("--node_name", required=True)
    p.add_argument("--cache_path", default="")
    p.add_argument(
        "--traceparent", default="",
        help=("W3C traceparent for trace context continuation "
              "(env TRACEPARENT as fallback; Doc 22 P1)"),
    )
    args = p.parse_args()

    if not args.aisop or not args.node_name:
        print(json.dumps({
            "audit_start": False,
            "node_name": args.node_name,
            "node_assert": "missing required field: aisop and node_name must be non-empty",
        }, ensure_ascii=False))
        return 2

    cache_path = (
        str(Path(args.cache_path).resolve()) if args.cache_path else ""
    )

    # audit_id is a fresh random token the LLM cannot pre-compute.
    # It is persisted in _pipeline_state.json open_nodes and is re-emitted
    # verbatim by node_audit_ended so the main process can audit that the
    # LLM actually executed node_started (instead of fabricating the text).
    audit_id = f"audit_{uuid.uuid4().hex[:8]}"

    open_node_state(args.aisop, args.node_name, cache_path, audit_id)
    # Doc 22 v1.8: started no longer emits a span. The interval span is
    # written by node_audit_ended / pipeline_node_aborted using opened_at
    # from state → single pipeline.node span per node with real duration.
    # Orphan guard still works: state.open_nodes[...] is the source of truth.

    response = {
        "audit_start": True,
        "node_name": args.node_name,
        "audit_id": audit_id,
        "node_assert": "monitoring started, strictly execute every step in node with 100% completion; never batch, skip, or fake the audit loop. Never fabricate cache content, validation reports, or tool_calls counts.",
    }
    print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({
            "audit_start": False,
            "node_name": "",
            "node_assert": f"node_audit_started crashed: {exc}",
            "_traceback": traceback.format_exc(),
        }, ensure_ascii=False))
        sys.exit(1)
