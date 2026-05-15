#!/usr/bin/env python3
"""node_task.py — Extract Sub Agent task package for a single node.

Called by Sub Agent via Bash to get all required info in one call,
instead of multiple file_system reads.
"""

import json
import argparse
import re
import sys
from pathlib import Path


def get_node_task(
    target_path: str,
    node_name: str,
    cache_dir: str,
    aiap_name: str,
    delegates: list[str] | None = None,
) -> dict:
    target = Path(target_path)
    cache = Path(cache_dir)

    # 1. Read target AIAP, extract specific function
    with open(target, encoding="utf-8") as f:
        data = json.load(f)

    # Find user content (typically data[1], but search by role for safety)
    user_content = next(
        (d["content"] for d in data if d.get("role") == "user"), None
    )
    if user_content is None:
        print(f"Error: No user role found in {target_path}", file=sys.stderr)
        sys.exit(1)
    functions = user_content["functions"]
    function_def = functions.get(node_name)
    if function_def is None:
        print(
            f"Error: Function '{node_name}' not found in {target_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 2. Extract system content (system_prompt, params — no tools, no mermaid)
    sys_content = next(
        (d["content"] for d in data if d.get("role") == "system"), {}
    )
    system_info = {
        "system_prompt": sys_content.get("system_prompt", ""),
        "params": sys_content.get("params", {}),
    }

    # 3. Read _index.json
    index_path = cache / "_index.json"
    index_state = {}
    if index_path.is_file():
        with open(index_path, encoding="utf-8") as f:
            idx = json.load(f)
        index_state = {
            "nodes_status": idx.get("nodes_status", {}),
            "trace_id": idx.get("trace_id", ""),
            "dispatch_plan": idx.get("dispatch_plan", {}),
        }

    # 4. Parse ASSERT dependencies and read predecessor caches
    assert_deps = {}
    for key, value in function_def.items():
        if isinstance(value, str) and "[ASSERT]" in value:
            # Extract referenced node names: "[ASSERT] NodeName executed"
            matches = re.findall(r"\[ASSERT\]\s+(\w+)\s+executed", value)
            for dep_node in matches:
                dep_cache = cache / f"{aiap_name}.{dep_node}.json"
                if dep_cache.is_file():
                    with open(dep_cache, encoding="utf-8") as f:
                        dep_data = json.load(f)
                    assert_deps[dep_node] = {
                        "status": dep_data.get("status"),
                        "output": dep_data.get("output", ""),
                        "user_summary": dep_data.get("user_summary", ""),
                    }

    # 5. Read conversation_context summary (last 5 turns, stripped of ai_response)
    ctx_path = cache.parent / "conversation_context.json"
    conv_ctx = {}
    if ctx_path.is_file():
        with open(ctx_path, encoding="utf-8") as f:
            ctx = json.load(f)
        turns = ctx.get("turns", [])
        # Only keep summary fields, exclude ai_response to save tokens
        recent = []
        for t in turns[-5:]:
            recent.append(
                {
                    "turn_id": t.get("turn_id"),
                    "user_message": t.get("user_message", ""),
                    "intent": t.get("intent", ""),
                    "status": t.get("status", ""),
                    "matched_package": t.get("matched_package", ""),
                }
            )
        conv_ctx = {
            "turn_id": turns[-1].get("turn_id") if turns else 0,
            "recent_turns": recent,
        }

    # 6. Check for resume state
    resume_state = None
    node_cache = cache / f"{aiap_name}.{node_name}.json"
    if node_cache.is_file():
        with open(node_cache, encoding="utf-8") as f:
            nc = json.load(f)
        if nc.get("status") in ("WAITING_USER", "MESSAGE_PENDING"):
            resume_state = {
                "status": nc.get("status"),
                "steps_done": nc.get("steps_done", []),
                "steps_remaining": nc.get("steps_remaining", []),
                "question": nc.get("question"),
                "message": nc.get("message"),
            }

    # 7. Extract delegated functions (if --delegates provided by node_engine)
    delegated_functions = {}
    delegated_modules = {}
    if delegates:
        aisop = user_content.get("aisop", {})
        for ref in delegates:
            if ref.startswith("aisop."):
                # sub_mermaid: aisop.features, aisop.pipeline
                sub_name = ref.split(".", 1)[1]
                if sub_name in aisop:
                    sub_mermaid = aisop[sub_name]
                    # Match all mermaid node formats: Name[label], {Name}, ((Name))
                    sub_nodes = re.findall(r"(\w+)[\[{(]", sub_mermaid)
                    sub_funcs = {
                        n: functions[n] for n in sub_nodes if n in functions
                    }
                    delegated_functions[sub_name] = {
                        "mermaid": sub_mermaid,
                        "functions": sub_funcs,
                    }
            elif ref.endswith(".aisop.json"):
                # cross-module: analysis.aisop.json
                mod_path = target.parent / ref
                if mod_path.is_file():
                    with open(mod_path, encoding="utf-8") as f:
                        mod_data = json.load(f)
                    mod_user = next(
                        (
                            d["content"]
                            for d in mod_data
                            if d.get("role") == "user"
                        ),
                        {},
                    )
                    delegated_modules[ref] = {
                        "path": str(mod_path),
                        "functions": mod_user.get("functions", {}),
                    }

    return {
        "node_name": node_name,
        "function": function_def,
        "system_content": system_info,
        "delegated_functions": delegated_functions,
        "delegated_modules": delegated_modules,
        "index_state": index_state,
        "assert_dependencies": assert_deps,
        "conversation_context": conv_ctx,
        "resume_state": resume_state,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract Sub Agent task package for a single node"
    )
    parser.add_argument(
        "--target", required=True, help="Target AIAP entry file path"
    )
    parser.add_argument("--node", required=True, help="Node function name")
    parser.add_argument(
        "--cache-dir", required=True, help="Execution cache directory"
    )
    parser.add_argument(
        "--aiap-name", required=True, help="AIAP package name"
    )
    parser.add_argument(
        "--delegates",
        default="",
        help="Comma-separated delegate references from node_engine",
    )
    args = parser.parse_args()

    delegates = (
        [d.strip() for d in args.delegates.split(",") if d.strip()]
        if args.delegates
        else None
    )
    result = get_node_task(
        args.target, args.node, args.cache_dir, args.aiap_name, delegates
    )
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
