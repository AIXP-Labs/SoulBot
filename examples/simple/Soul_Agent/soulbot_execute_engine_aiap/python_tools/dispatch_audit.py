#!/usr/bin/env python3
"""dispatch_audit.py -- Audit a run's node caches for dispatch integrity (v5.13.1).

v5.13.1 CHANGE (A1): Branch-aware completeness verification fix.
  REPLACED: v5.13.0 logic that checked ALL graph nodes against nodes_in_path
  (false-positive on multi-branch programs like soulbot_creator_evolution with 13
  NLU branches where only 1 branch is walked).
  NEW: verify_nodes_in_path_completeness() is now BRANCH-AWARE:
    - For each sub-graph/mermaid, identify decision nodes and their branches.
    - Determine which branches are "walked" (have intersection with nodes_in_path).
    - For walked branches: all non-decision nodes must be in nodes_in_path.
      Gate node missing -> CRITICAL. Non-gate missing -> WARN.
    - Unwalked branches (no intersection with nodes_in_path): EXEMPT entirely.
  ALSO FIXED: _parse_mermaid_nodes() edge_pattern regex was capturing mermaid
  edge labels (Pass, Fail, Red, Yellow, Green/Yellow) as node names.
  Called via --completeness-check CLI flag.

v5.13.0 CHANGE (A1, superseded by v5.13.1): Added nodes_in_path completeness verification.
  Original logic required ALL graph nodes in nodes_in_path. Superseded by branch-aware
  logic in v5.13.1.

v5.7.0 CHANGE: Added --pre-execution generation-stage audit gate (A3 v5.7.0).
  NEW: --pre-execution mode independently recomputes should-be dispatch_plan from
  target AIAP (reading execute_mode fields, unset -> 'agent'), then compares vs
  _index.json::dispatch_plan. Any mismatch is a generation_violation.
  This gate MUST run BEFORE first node dispatch — never post-hoc.
  Violation -> block execution + force regeneration.

  Post-execution scan (existing behavior) retained and enhanced with
  generation_violation category for plan-vs-declaration mismatches detected
  after execution.

v5.6.1 CHANGE: agent-mode nodes (execute_mode=agent) use direct-write - the sub-agent
  reads expected_agent_id from _index and writes it verbatim (trusted execution).
  agent_id integrity_violation + timestamp_ordering are now SKIPPED for agent-mode
  nodes (they were anti-forgery for the python-injected agent_id). Inline path
  unchanged. Fallback classification (legit/illegitimate) KEPT - it audits
  spawn/fallback authenticity, not agent_id.

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
  # Post-execution audit (existing behavior)
  python dispatch_audit.py --cache_dir=<run_dir>

  # Pre-execution generation-stage audit (NEW v5.7.0)
  python dispatch_audit.py --cache_dir=<run_dir> --pre-execution --entry_path=<target.aisop.json> [--json]

Output (human-readable to stdout, plus JSON summary with --json):
  === Dispatch Audit v5.13.1: <run_dir> ===
  Total nodes executed: N
  Integrity violations: V
  Legit fallbacks: L
  Illegitimate fallbacks: I
  Generation violations: G  (pre-execution mode only)
  INTEGRITY RATE: P% [OK | WARN | CRITICAL]

Threshold:
  0 integrity_violations AND 0 illegitimate_fallback AND 0 generation_violations -> OK
  illegitimate_fallback > 0 OR integrity_violations <= 10% -> WARN
  illegitimate_fallback / total > 10% OR integrity_violations > 10% -> CRITICAL
  generation_violations > 0 (pre-execution) -> CRITICAL (blocks execution)

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


# ---------------------------------------------------------------------------
# Mermaid graph parsing for nodes_in_path completeness (A1 v5.13.0)
# ---------------------------------------------------------------------------

import re as _re


def _parse_mermaid_nodes(mermaid_text: str) -> Tuple[List[str], List[str]]:
    """Parse mermaid graph TD text and extract all node names.

    Returns (all_nodes, decision_nodes) where:
      - all_nodes: every node name found in the graph (rectangles + diamonds)
      - decision_nodes: node names using diamond syntax {NodeName} (exempt from
        completeness check because branch routing may legitimately skip them)

    QI-2 v5.13.0: This parser is intentionally INDEPENDENT from
    generate_dispatch_plan.py's mermaid handling and from node_engine's
    orchestrator-side mermaid parsing. Independence is required because
    the completeness audit must NOT share code with the systems it verifies.
    """
    all_nodes: List[str] = []
    decision_nodes: List[str] = []
    seen: set = set()

    if not mermaid_text:
        return all_nodes, decision_nodes

    # Match node definitions: NodeName[Label], NodeName{Label}, NodeName((Label))
    # Rectangle: NodeName[...]
    rect_pattern = _re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\[')
    # Diamond (decision): NodeName{...}
    diamond_pattern = _re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\{')
    # Circle (end): NodeName((
    circle_pattern = _re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\(\(')
    # Edge-only node references (Q1 v5.13.0, Q2 v5.13.1 edge label fix): nodes that
    # appear only in arrow definitions (e.g. "A --> B" or "A -->|label| B") without
    # an explicit label definition. These would be missed by the patterns above.
    # v5.13.1 FIX: The source-side pattern was capturing edge labels like "Pass",
    # "Fail", "Red", "Yellow", "Green/Yellow" from "-- Pass -->" syntax as node
    # names. Fixed by requiring "-->" (not just "--") on source side, and filtering
    # out text between "-- " and " -->" which are edge labels.
    edge_pattern = _re.compile(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\s*-->'  # source side: "NodeA -->" only (not "-- label -->")
        r'|-->\s*(?:\|[^|]*\|\s*)?([A-Za-z_][A-Za-z0-9_]*)\b'  # target side: "--> NodeB" or "-->|label| NodeB"
    )
    # Edge label pattern: matches "-- Label -->" to identify false node matches
    edge_label_pattern = _re.compile(r'--\s+\S+.*?-->')

    for line in mermaid_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('graph ') or line.startswith('%%'):
            continue

        # Find rectangle nodes
        for m in rect_pattern.finditer(line):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                all_nodes.append(name)

        # Find diamond (decision) nodes
        for m in diamond_pattern.finditer(line):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                all_nodes.append(name)
                decision_nodes.append(name)

        # Find circle (endNode) nodes
        for m in circle_pattern.finditer(line):
            name = m.group(1)
            if name not in seen:
                seen.add(name)
                all_nodes.append(name)

        # Find edge-only node references (Q1 v5.13.0, Q2 v5.13.1 edge label fix)
        for m in edge_pattern.finditer(line):
            name = m.group(1) or m.group(2)
            if not name or name in seen:
                continue
            # v5.13.1: Filter out edge labels — text captured from
            # "-- Pass -->" or "-- Fail -->" patterns. These are mermaid
            # edge labels, not node names. Common edge labels to exclude:
            # Pass, Fail, Red, Yellow, Green, Yes, No, True, False
            # Also filter names that appear inside "-- X -->" context
            # by checking if the name is between -- and --> on this line
            is_edge_label = False
            for lm in edge_label_pattern.finditer(line):
                label_text = lm.group(0)
                if name in label_text:
                    is_edge_label = True
                    break
            if not is_edge_label:
                seen.add(name)
                all_nodes.append(name)

    return all_nodes, decision_nodes


def _read_all_mermaid_graphs(entry_path: str) -> List[str]:
    """Read all mermaid graph texts from a target AIAP entry file.

    Handles both array (standard AISOP) and object format.
    Returns list of mermaid graph text strings (main + any sub_mermaid).

    QI-2 v5.13.0: Independent from generate_dispatch_plan.py and
    _read_target_functions(). Both parse AISOP independently.
    """
    p = Path(entry_path)
    if not p.is_file():
        return []

    try:
        with open(p, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    graphs: List[str] = []

    def _extract_aisop(content: dict) -> None:
        if not isinstance(content, dict):
            return
        aisop = content.get("aisop", {})
        if isinstance(aisop, dict):
            for key, val in aisop.items():
                if isinstance(val, str) and ("graph " in val or "graph\n" in val):
                    graphs.append(val)

    # Array format
    if isinstance(data, list):
        for msg in data:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "user":
                content = msg.get("content", {})
                _extract_aisop(content)
        return graphs

    # Object format
    if isinstance(data, dict):
        _extract_aisop(data)
        content = data.get("content", {})
        _extract_aisop(content)

    return graphs


def _parse_mermaid_branches(mermaid_text: str) -> List[Dict]:
    """Parse a mermaid graph and extract branch structure around decision nodes.

    For each decision node (diamond syntax {NodeName}), identifies the branches
    that emanate from it and the nodes on each branch.

    Returns a list of branch descriptors:
      [{ "decision_node": str, "branch_label": str, "branch_nodes": [str] }, ...]

    Nodes NOT on any decision branch (i.e., on the main sequential path before
    any decision or shared across all branches) are returned as a special
    branch with decision_node=None, branch_label="main_path".

    v5.13.1 A1: This function enables branch-aware completeness checking.
    """
    if not mermaid_text:
        return []

    # Parse all edges from the mermaid graph
    # Edges: "A --> B", "A -->|label| B", "A -- label --> B"
    edges: List[Tuple[str, str, str]] = []  # (source, target, label)
    edge_re = _re.compile(
        r'\b([A-Za-z_][A-Za-z0-9_]*)\s*'  # source node
        r'(?:-->\s*(?:\|([^|]*)\|\s*)?'    # --> with optional |label|
        r'|--\s+([^\s-]+(?:/[^\s-]+)?)\s+-->\s*)'  # or -- label -->
        r'([A-Za-z_][A-Za-z0-9_]*)\b'     # target node
    )

    for line in mermaid_text.split('\n'):
        line = line.strip()
        if not line or line.startswith('graph ') or line.startswith('%%'):
            continue
        for m in edge_re.finditer(line):
            source = m.group(1)
            label = m.group(2) or m.group(3) or ""
            target = m.group(4)
            edges.append((source, target, label.strip()))

    # Build adjacency: for each node, what are its outgoing edges
    outgoing: Dict[str, List[Tuple[str, str]]] = {}
    for src, tgt, lbl in edges:
        outgoing.setdefault(src, []).append((tgt, lbl))

    # Identify decision nodes: nodes with 2+ outgoing edges (branching points)
    all_nodes_parsed, decision_nodes_parsed = _parse_mermaid_nodes(mermaid_text)
    decision_set = set(decision_nodes_parsed)

    # Also detect nodes with 2+ outgoing edges even if not diamond syntax
    for node, targets in outgoing.items():
        if len(targets) >= 2:
            decision_set.add(node)

    # For each decision node, collect the nodes reachable on each branch
    branches: List[Dict] = []

    for decision_node in decision_set:
        outgoing_edges = outgoing.get(decision_node, [])
        if len(outgoing_edges) < 2:
            continue

        for target, label in outgoing_edges:
            # BFS/DFS to collect all nodes reachable from this branch target
            # Stop when hitting endNode, another decision node's branch, or
            # a node that merges back
            branch_nodes: List[str] = []
            visited: set = set()
            queue = [target]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if current == "endNode":
                    continue
                branch_nodes.append(current)

                # Follow outgoing edges from current (but not if current is
                # a decision node with multiple branches — that starts new sub-branches)
                current_outgoing = outgoing.get(current, [])
                if current in decision_set and len(current_outgoing) >= 2 and current != target:
                    # This is a nested decision node — don't traverse into its branches here
                    continue
                for next_node, _ in current_outgoing:
                    if next_node not in visited:
                        queue.append(next_node)

            branches.append({
                "decision_node": decision_node,
                "branch_label": label or f"branch_to_{target}",
                "branch_nodes": branch_nodes,
            })

    return branches


def verify_nodes_in_path_completeness(
    cache_dir: str,
    entry_path: str,
) -> Tuple[Dict, List[Dict]]:
    """Verify nodes_in_path completeness against target AIAP mermaid graph (A1 v5.13.1).

    BRANCH-AWARE completeness verification (v5.13.1 — replaces v5.13.0 logic):
    Instead of requiring ALL graph nodes to be in nodes_in_path (which produced
    false-positives on multi-branch programs), this version:

    1. Parses each mermaid graph and identifies decision nodes with branches.
    2. For each branch, determines if it is "walked" (has intersection with
       nodes_in_path).
    3. For WALKED branches: verifies all non-decision nodes are in nodes_in_path.
       Gate node missing -> CRITICAL. Non-gate missing -> WARN.
    4. For UNWALKED branches (no intersection with nodes_in_path): EXEMPT entirely.
       These are legitimate unexecuted branches (e.g., NLU routing to a different
       intent handler than the one being executed).

    Gate node detection: uses user_gate_audit.py G1 marker set to identify nodes
    with sovereignty gates. Omission of a gate node in a WALKED branch is
    escalated to CRITICAL.

    endNode is always excluded (never executed as a real node).

    Returns (summary_counts, violations_list).
    """
    index = _load_index(cache_dir)
    violations: List[Dict] = []
    completeness_violations = 0
    gate_omissions = 0
    entry_path_omissions = 0   # P0 fix: unconditional main-path/entry node omissions (BLOCK-worthy)
    branches_walked = 0
    branches_exempt = 0

    # Get nodes_in_path from _index.json
    nodes_in_path = index.get("nodes_in_path", [])
    if not isinstance(nodes_in_path, list):
        nodes_in_path = []
    nodes_in_path_set = set(nodes_in_path)

    # Read and parse all mermaid graphs from target AIAP
    mermaid_texts = _read_all_mermaid_graphs(entry_path)
    if not mermaid_texts:
        return {
            "total_graph_nodes": 0,
            "nodes_in_path_count": len(nodes_in_path),
            "completeness_violations": 0,
            "gate_omissions": 0,
            "decision_nodes_exempt": 0,
            "branches_walked": 0,
            "branches_exempt": 0,
            "audit_stage": "completeness-check",
            "audit_version": "5.13.1",
            "warning": "no_mermaid_graphs_found",
        }, []

    # Parse all nodes from all mermaid graphs
    all_graph_nodes: List[str] = []
    all_decision_nodes: List[str] = []
    seen_global: set = set()

    for mermaid_text in mermaid_texts:
        nodes, decisions = _parse_mermaid_nodes(mermaid_text)
        for n in nodes:
            if n not in seen_global:
                seen_global.add(n)
                all_graph_nodes.append(n)
        for d in decisions:
            if d not in all_decision_nodes:
                all_decision_nodes.append(d)

    decision_set = set(all_decision_nodes)

    # Read target functions to detect gate markers (G1 marker set reuse)
    functions = _read_target_functions(entry_path)
    gate_markers = [
        "USER_CONFIRMATION_MANDATORY", "sovereignty_violation", "WAITING_USER",
        "sys.io.confirm", "sys.io.input", "sys.io.select",
        "user_gate", "USER_CONFIRM", "USER_CHOOSE", "USER_INPUT",
        "ask user", "user selects", "user MUST confirm", "user approves",
        "present for user", "collect user decisions",
    ]

    def _is_gate_node(node_name: str) -> bool:
        func_def = functions.get(node_name, {})
        if not isinstance(func_def, dict):
            return False
        if func_def.get("user_gate") is True:
            return True
        func_text = json.dumps(func_def, ensure_ascii=False).lower()
        for marker in gate_markers:
            if marker.lower() in func_text:
                return True
        return False

    # Parse branch structure from all mermaid graphs
    all_branches: List[Dict] = []
    for mermaid_text in mermaid_texts:
        all_branches.extend(_parse_mermaid_branches(mermaid_text))

    # Collect all nodes that belong to at least one branch
    nodes_in_branches: set = set()
    for branch in all_branches:
        for n in branch["branch_nodes"]:
            nodes_in_branches.add(n)

    # BRANCH-AWARE CHECK: For each branch, determine if walked or exempt
    for branch in all_branches:
        branch_node_set = set(branch["branch_nodes"])
        intersection = branch_node_set & nodes_in_path_set

        if not intersection:
            # UNWALKED branch: no nodes from this branch appear in nodes_in_path
            # -> EXEMPT entirely (legitimate unexecuted branch)
            branches_exempt += 1
            continue

        # WALKED branch: has intersection with nodes_in_path
        branches_walked += 1

        # Check all non-decision nodes in this branch
        for node_name in branch["branch_nodes"]:
            if node_name == "endNode":
                continue
            if node_name in decision_set:
                continue  # Decision nodes themselves are exempt from the check
            if node_name not in nodes_in_path_set:
                is_gate = _is_gate_node(node_name)
                severity_level = "CRITICAL" if is_gate else "WARN"
                completeness_violations += 1
                if is_gate:
                    gate_omissions += 1

                violations.append({
                    "node": node_name,
                    "violation_type": "completeness_violation",
                    "severity": severity_level,
                    "is_gate_node": is_gate,
                    "branch_decision": branch["decision_node"],
                    "branch_label": branch["branch_label"],
                    "branch_walked": True,
                    "detail": (
                        f"Node '{node_name}' is on walked branch "
                        f"'{branch['branch_label']}' (from decision "
                        f"'{branch['decision_node']}') but MISSING from "
                        f"nodes_in_path. "
                        f"{'GATE NODE — sovereignty enforcement bypassed!' if is_gate else 'Node on active branch not executed.'}"
                    ),
                })

    # Also check nodes NOT on any branch (main path nodes)
    # These are nodes that are not part of any decision branch — they are
    # on the unconditional path and should always be in nodes_in_path
    for node_name in all_graph_nodes:
        if node_name == "endNode":
            continue
        if node_name in decision_set:
            continue
        if node_name in nodes_in_branches:
            continue  # Already handled by branch-aware check above

        # This node is on the unconditional main path
        if node_name not in nodes_in_path_set:
            is_gate = _is_gate_node(node_name)
            severity_level = "CRITICAL" if is_gate else "WARN"
            completeness_violations += 1
            entry_path_omissions += 1   # P0 fix: unconditional main-path node (e.g. Start/NLU/PipelineEntry) missing = hard error -> BLOCK
            if is_gate:
                gate_omissions += 1

            violations.append({
                "node": node_name,
                "violation_type": "completeness_violation",
                "severity": severity_level,
                "is_gate_node": is_gate,
                "branch_decision": None,
                "branch_label": "main_path",
                "branch_walked": True,
                "detail": (
                    f"Node '{node_name}' is on unconditional main path but "
                    f"MISSING from nodes_in_path. "
                    f"{'GATE NODE — sovereignty enforcement bypassed!' if is_gate else 'Main path node not executed.'}"
                ),
            })

    # NODE_SUMMARY_RENDERED CHECK (B1b v5.26.0):
    # For each node in nodes_in_path that has been executed (present in
    # nodes_status), verify node_summary_rendered==true. Missing or false
    # means the orchestrator skipped step4 node info output for that node.
    # Gate nodes -> CRITICAL (NODE_SUMMARY_OMITTED). Other nodes -> WARN.
    nodes_status = index.get("nodes_status", {})
    node_summary_omissions = 0
    node_summary_gate_omissions = 0
    if isinstance(nodes_status, dict):
        for node_name in nodes_in_path:
            if node_name == "endNode":
                continue
            ns_entry = nodes_status.get(node_name)
            if not isinstance(ns_entry, dict):
                continue  # Node not yet executed — skip
            # Node was executed; check node_summary_rendered
            rendered = ns_entry.get("node_summary_rendered", False)
            if rendered is not True:
                is_gate = _is_gate_node(node_name)
                severity_level = "CRITICAL" if is_gate else "WARN"
                node_summary_omissions += 1
                completeness_violations += 1
                if is_gate:
                    node_summary_gate_omissions += 1
                    gate_omissions += 1
                violations.append({
                    "node": node_name,
                    "violation_type": "NODE_SUMMARY_OMITTED",
                    "severity": severity_level,
                    "is_gate_node": is_gate,
                    "branch_decision": None,
                    "branch_label": "node_summary_rendered",
                    "branch_walked": True,
                    "detail": (
                        f"Node '{node_name}' was executed (status={ns_entry.get('status')}) "
                        f"but node_summary_rendered is not true — orchestrator skipped or "
                        f"degraded step4 node info output. "
                        f"{'GATE NODE — sovereignty enforcement visibility bypassed!' if is_gate else 'Node info not rendered for user.'}"
                    ),
                })

    counts = {
        "total_graph_nodes": len(all_graph_nodes),
        "nodes_in_path_count": len(nodes_in_path),
        "completeness_violations": completeness_violations,
        "gate_omissions": gate_omissions,
        "entry_path_omissions": entry_path_omissions,
        "decision_nodes_exempt": len(all_decision_nodes),
        "branches_walked": branches_walked,
        "branches_exempt": branches_exempt,
        "node_summary_omissions": node_summary_omissions,
        "node_summary_gate_omissions": node_summary_gate_omissions,
        "audit_stage": "completeness-check",
        "audit_version": "5.26.0",
    }
    return counts, violations


# ---------------------------------------------------------------------------
# Pre-execution generation-stage audit (A3 v5.7.0)
# ---------------------------------------------------------------------------

def _read_target_functions(entry_path: str) -> Dict:
    """Read target AIAP entry file and extract functions dict.

    Handles both array (standard AISOP) and object AISOP format.
    Returns the functions dict or empty dict if not found.

    NOTE (QI-2 v5.7.0): This function is intentionally independent from
    generate_dispatch_plan.py's _read_target_functions(). Both implementations
    parse AISOP format independently to maintain verification independence —
    the audit must NOT share code with the generator it verifies. If the AISOP
    format changes, BOTH implementations must be updated. A shared integration
    test should verify format parity (see generate_dispatch_plan.py for the
    mirror note).
    """
    p = Path(entry_path)
    if not p.is_file():
        return {}

    try:
        with open(p, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    # Array format (standard AISOP)
    if isinstance(data, list):
        for msg in data:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") == "user":
                content = msg.get("content", {})
                if isinstance(content, dict) and "functions" in content:
                    return content["functions"]
        return {}

    # Object format
    if isinstance(data, dict):
        if "functions" in data:
            return data["functions"]
        content = data.get("content", {})
        if isinstance(content, dict) and "functions" in content:
            return content["functions"]

    return {}


def pre_execution_audit(
    cache_dir: str,
    entry_path: str,
) -> Tuple[Dict, List[Dict]]:
    """Pre-execution generation-stage audit (A3 v5.7.0).

    Independently recomputes should-be dispatch_plan from target AIAP
    (reading execute_mode fields, unset -> 'agent'), then compares vs
    _index.json::dispatch_plan written by generate_dispatch_plan.py.

    This is a VERIFICATION gate -- it does NOT trust generate_dispatch_plan.py's
    output. It performs its own independent computation from the AIAP source
    and checks that the tool produced the correct result.

    Any mismatch is a generation_violation.

    Returns (summary_counts, violations_list).
    """
    index = _load_index(cache_dir)
    violations: List[Dict] = []
    generation_violations = 0

    # Read actual dispatch_plan from _index.json
    actual_plan = index.get("dispatch_plan", {})
    if not isinstance(actual_plan, dict):
        return {
            "total_nodes": 0,
            "generation_violations": 1,
            "audit_stage": "pre-execution",
        }, [{
            "node": "_all",
            "expected": "dispatch_plan dict in _index.json",
            "actual": f"type={type(actual_plan).__name__}",
            "violation_type": "generation_violation",
            "detail": "dispatch_plan missing or not a dict in _index.json",
        }]

    # Read target AIAP functions for independent recomputation
    functions = _read_target_functions(entry_path)

    # Get nodes_in_path from _index.json
    nodes_in_path = index.get("nodes_in_path", [])
    if not isinstance(nodes_in_path, list) or not nodes_in_path:
        # fail-safe (plan20/15): empty/missing nodes_in_path must NOT silently pass the
        # gate -- fall back to auditing dispatch_plan's own nodes so tampering is still caught.
        nodes_in_path = list(actual_plan.keys())

    # Independent recomputation: for each node, determine should-be mode
    for node_name in nodes_in_path:
        func_def = functions.get(node_name, {})
        if not isinstance(func_def, dict):
            func_def = {}

        # Should-be mode: set -> use it, unset -> 'agent' (same logic as
        # generate_dispatch_plan.py, independently computed)
        should_be_mode = func_def.get("execute_mode", "agent")

        # Validate should_be_mode
        if should_be_mode not in ("agent", "inline"):
            should_be_mode = "agent"  # invalid defaults to agent

        # Get actual mode from dispatch_plan
        actual_entry = actual_plan.get(node_name)
        actual_mode = None
        if isinstance(actual_entry, dict):
            actual_mode = actual_entry.get("execute_mode", actual_entry.get("mode"))
        elif isinstance(actual_entry, str):
            actual_mode = actual_entry
        else:
            # Node missing from dispatch_plan entirely
            generation_violations += 1
            violations.append({
                "node": node_name,
                "expected": should_be_mode,
                "actual": "MISSING",
                "violation_type": "generation_violation",
                "detail": f"Node '{node_name}' missing from dispatch_plan",
            })
            continue

        # Compare
        if actual_mode != should_be_mode:
            generation_violations += 1
            violations.append({
                "node": node_name,
                "expected": should_be_mode,
                "actual": actual_mode,
                "violation_type": "generation_violation",
                "detail": (
                    f"dispatch_plan mode mismatch: AIAP declares "
                    f"execute_mode='{should_be_mode}' but dispatch_plan has "
                    f"'{actual_mode}'"
                ),
            })

    counts = {
        "total_nodes": len(nodes_in_path),
        "generation_violations": generation_violations,
        "audit_stage": "pre-execution",
    }
    return counts, violations


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

        # v5.6.1: agent-mode nodes use direct-write - the sub-agent reads expected_agent_id
        # and writes it verbatim (trusted, no audit). Skip agent_id integrity + timestamp
        # checks for agent-mode nodes (these were anti-forgery for the python-injected
        # agent_id). Inline path unchanged; fallback classification kept below.
        _plan_entry = index.get("dispatch_plan", {})
        _plan_entry = _plan_entry.get(node_name) if isinstance(_plan_entry, dict) else None
        _node_mode = _plan_entry.get("execute_mode") if isinstance(_plan_entry, dict) else (_plan_entry if isinstance(_plan_entry, str) else None)
        is_agent_mode = (_node_mode == "agent")

        # Integrity check: expected vs actual agent_id (inline only - agent direct-write trusted)
        if not is_agent_mode and expected_agent_id is not None and actual_agent_id != expected_agent_id:
            integrity_violations += 1
            violations.append({
                "node": node_name,
                "expected": expected_agent_id,
                "actual": actual_agent_id,
                "evidence_cache": fn,
                "violation_type": "integrity_violation",
            })

        # Timestamp ordering check (A4 v5.5.0; v5.6.1: inline/fallback only - agent direct-write trusted)
        ts_violation = None if is_agent_mode else _check_timestamp_ordering(index, cache, node_name)
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
        description="Audit run dir for dispatch integrity (v5.13.1)"
    )
    parser.add_argument("--cache_dir", required=True, help="Path to run cache directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary to stdout")
    parser.add_argument(
        "--pre-execution", action="store_true", dest="pre_execution",
        help="Run pre-execution generation-stage audit (A3 v5.7.0). "
             "Requires --entry_path. Independently recomputes should-be "
             "dispatch_plan from AIAP and verifies against _index.json."
    )
    parser.add_argument(
        "--completeness-check", action="store_true", dest="completeness_check",
        help="Run nodes_in_path completeness verification (A1 v5.13.1 branch-aware). "
             "Requires --entry_path. Independently reparses target AIAP mermaid "
             "graph and verifies walked branches have complete nodes_in_path coverage. "
             "Gate node omission on walked branch -> CRITICAL. Unwalked branches exempt."
    )
    parser.add_argument(
        "--entry_path", default=None,
        help="Path to target AIAP entry file. Required for --pre-execution and --completeness-check modes."
    )
    args = parser.parse_args()

    cache_dir = args.cache_dir
    if not os.path.isdir(cache_dir):
        print(f"ERROR: cache_dir not found: {cache_dir}", file=sys.stderr)
        return 3

    # --pre-execution mode (A3 v5.7.0)
    if args.pre_execution:
        if not args.entry_path:
            print("ERROR: --pre-execution requires --entry_path", file=sys.stderr)
            return 3
        if not os.path.isfile(args.entry_path):
            print(f"ERROR: entry_path not found: {args.entry_path}", file=sys.stderr)
            return 3

        counts, violations = pre_execution_audit(cache_dir, args.entry_path)
        total = counts.get("total_nodes", 0)
        gen_violations = counts.get("generation_violations", 0)

        # Severity for pre-execution: any generation_violation -> CRITICAL
        if gen_violations > 0:
            sev = "CRITICAL"
            exit_code = 2
        else:
            sev = "OK"
            exit_code = 0

        summary: Dict = {
            "cache_dir": cache_dir,
            "audit_version": "5.13.1",
            "audit_stage": "pre-execution",
            "total_nodes": total,
            "generation_violations": gen_violations,
            "severity": sev,
        }
        if violations:
            summary["violations"] = violations

        if args.json:
            print(json.dumps(summary, ensure_ascii=False))
        else:
            print(f"=== Dispatch Audit v5.13.1 [PRE-EXECUTION]: {cache_dir} ===")
            print(f"Total nodes in dispatch_plan: {total}")
            print(f"Generation violations:         {gen_violations}")
            print(f"RESULT: [{sev}]")
            if violations:
                print()
                print("Violation details:")
                for v in violations:
                    print(
                        f"  {v['node']}: expected={v['expected']}, "
                        f"actual={v['actual']}, detail={v.get('detail', '')}"
                    )

        return exit_code

    # --completeness-check mode (A1 v5.13.0)
    if args.completeness_check:
        if not args.entry_path:
            print("ERROR: --completeness-check requires --entry_path", file=sys.stderr)
            return 3
        if not os.path.isfile(args.entry_path):
            print(f"ERROR: entry_path not found: {args.entry_path}", file=sys.stderr)
            return 3

        counts, violations = verify_nodes_in_path_completeness(cache_dir, args.entry_path)
        comp_violations = counts.get("completeness_violations", 0)
        gate_omissions_count = counts.get("gate_omissions", 0)

        # Severity: any gate omission -> CRITICAL. Other omissions -> WARN.
        if gate_omissions_count > 0:
            sev = "CRITICAL"
            exit_code = 2
        elif comp_violations > 0:
            sev = "WARN"
            exit_code = 1
        else:
            sev = "OK"
            exit_code = 0

        summary: Dict = {
            "cache_dir": cache_dir,
            "audit_version": "5.26.0",
            "audit_stage": "completeness-check",
            "total_graph_nodes": counts.get("total_graph_nodes", 0),
            "nodes_in_path_count": counts.get("nodes_in_path_count", 0),
            "completeness_violations": comp_violations,
            "gate_omissions": gate_omissions_count,
            "decision_nodes_exempt": counts.get("decision_nodes_exempt", 0),
            "branches_walked": counts.get("branches_walked", 0),
            "branches_exempt": counts.get("branches_exempt", 0),
            "node_summary_omissions": counts.get("node_summary_omissions", 0),
            "node_summary_gate_omissions": counts.get("node_summary_gate_omissions", 0),
            "severity": sev,
        }
        if violations:
            summary["violations"] = violations

        if args.json:
            print(json.dumps(summary, ensure_ascii=False))
        else:
            print(f"=== Dispatch Audit v5.26.0 [COMPLETENESS-CHECK]: {cache_dir} ===")
            print(f"Total graph nodes:             {counts.get('total_graph_nodes', 0)}")
            print(f"nodes_in_path count:           {counts.get('nodes_in_path_count', 0)}")
            print(f"Completeness violations:       {comp_violations}")
            print(f"Gate node omissions (CRITICAL): {gate_omissions_count}")
            print(f"Decision nodes (exempt):       {counts.get('decision_nodes_exempt', 0)}")
            print(f"Branches walked:               {counts.get('branches_walked', 0)}")
            print(f"Branches exempt (unwalked):    {counts.get('branches_exempt', 0)}")
            print(f"Node summary omissions:        {counts.get('node_summary_omissions', 0)}")
            print(f"Node summary gate omissions:   {counts.get('node_summary_gate_omissions', 0)}")
            print(f"RESULT: [{sev}]")
            if violations:
                print()
                print("Violation details:")
                for v in violations:
                    print(
                        f"  {v['node']}: severity={v.get('severity', '')}, "
                        f"type={v.get('violation_type', '')}, "
                        f"is_gate={v.get('is_gate_node', False)}, "
                        f"detail={v.get('detail', '')}"
                    )

        return exit_code

    # Post-execution scan (existing behavior)
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

    summary = {
        "cache_dir": cache_dir,
        "audit_version": "5.13.1",
        "audit_stage": "post-execution",
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
        print(f"=== Dispatch Audit v5.13.1: {cache_dir} ===")
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
