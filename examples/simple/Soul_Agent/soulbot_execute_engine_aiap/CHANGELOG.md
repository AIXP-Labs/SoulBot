# Changelog

All notable changes to soulbot_execute_engine are documented in this file.

## [5.45.0] - 2026-06-16

ENGINE SELF-EVOLUTION (target=runner=live engine directory; runner-direct, only this one copy modified). MINOR, predetermined, NON-functional NEXT-NODE PLAN discipline-hardening. FINALIZED by Creator Evolve pipeline (cache/133) ReviewFinalize. Grade S, weighted 4.949 (deferred-excluded; full-D reconciled 4.952), ZERO-DELTA vs v5.44.0.

### [CHANGE A1] node_engine NEXT-NODE PLAN block (programExec.step3(b))
- will_render_node_info:true -> MUST_render_node_info:YES; will_output_next_node_plan:true -> MUST_output_next_node_plan:YES.
- Added embedded 3-step node_workflow ["1. Output NEXT-NODE PLAN and persist to _index", "2. Execute STRICTLY per NEXT-NODE PLAN", "3. Output node info"] + trailing RULE: "MUST ALL BE YES".
- Verbatim "planned_action:" prefix preserved.

### [CHANGE A2] normal_engine NEXT-NODE PLAN block (programExec.step3(b))
- Same 2 renames PLUS will_write_cache_via_agent_write_node_cache_py:true -> MUST_write_cache_via_agent_write_node_cache_py:YES.
- Added 4-step node_workflow (adds "3. Write node cache via agent_write_node_cache.py") + trailing RULE: "MUST ALL BE YES".

### [CHANGE A3] Mirror invariant + A4 prefix preservation
- Both modules carry identical trailing RULE: "MUST ALL BE YES"; node_engine 3-step omits write-cache (dispatched sub-agent self-writes via agent_engine.writeCache), normal_engine 4-step includes it (all-inline override) = JUSTIFIED ASYMMETRY. main.aisop.json next_node_plan untouched (references, does not define struct).

### [Un-weakened preservation]
- Verified present/un-weakened on disk: six-section node-info; NEXT-NODE PLAN EMIT TIMING (incl. "for EVERY node INCLUDING the inline entry nodes"); A1 v5.44.0 NODE_PLAN_OMITTED deterrence line (byte-unchanged); NodeVerify; crash recovery; 3-state circuit breaker; user_gate_audit.py --enforce LIVE; writeCache; normal_engine ALL-INLINE OVERRIDE + step3(d) always-inline; dispatch_audit pre-execution/completeness; four-way audit anchors.

### [LEVEL_C] Automatic Fixes
- C1: Version + name sync 5.44.0 -> 5.45.0 all 4 .aisop.json modules; main + agent_engine version+name ONLY (functions block byte-identical to v5.44.0).
- C2: Version sync AIAP.md / agent_card.json / quality_baseline.json -> 5.45.0.
- C3: evolution_history + version_history + changelog append (this entry).
- C4: Governance hash TRI-SYNC recompute via tool_dirs/governance_hash.py (canonical v1.0, SOLE AUTHORITY) -> f9ab34cf567d9a1d3a92ca0b36ba3e217db4c51a2aa78e342b79f04980bca289 (prior v5.44.0 c1f3b9a9912dd3797621f0b8e8e02ea6c4960724aba975863e8d814a76307604).
- C5: .evolution_snapshot/v5.45.0/ built LAST (after governance_hash + identity) via tool_dirs/snapshot_build.py; snapshot_audit.py exit 0.

### [Quality]
- ThreeDimTest: C=5.00 I=4.92 D=4.95 (deferred-excluded), weighted 4.949 Grade S; STEP6 P23 reconcile D6/D10 4.5 -> 5.0 (full-D 4.96, full weighted 4.952). regression_flags=[]. ValidateStep 12 authorized leaves / 0 collateral. EvolveStep TRUE HALT user "all"; ReviewPresent conditional gate finalize_risk=FALSE -> AUTO-APPROVED (non-bypass).

## [5.44.0] - 2026-06-16

### [CHANGE A1] node-info Output append (7 places, verbatim identical)
- Append ONE verbatim sentence to every node-info Output sub-line, after "...drop a section." within the same Output bullet: "STRICTLY output the NEXT-NODE PLAN BEFORE EVERY node begins, NO exception, NEVER batched or skipped (omission = NODE_PLAN_OMITTED)."
- Coverage = EXACTLY 7: main.aisop.json 3 (Router.match / Router.cache-setup / dispatch-audit-summary engine-self node-infos); node_engine.aisop.json 2 (engine-self template + dispatched/per-node template); normal_engine.aisop.json 2 (mirror of node_engine). Same sentence everywhere — no engine-self/per-node variant.

### [CHANGE A2] next_node_plan will_ audit fields (node_engine / normal_engine only)
- Anchor: programExec.step3 (b) NEXT-NODE PLAN struct { node, execute_mode, expected_agent_id, planned_action, will_render_node_info }.
- node_engine.aisop.json: add will_output_next_node_plan: true.
- normal_engine.aisop.json: add will_output_next_node_plan: true AND will_write_cache_via_agent_write_node_cache_py: true.
- will_render_node_info KEPT verbatim (no rename, no delete, no synonymous field). main.aisop.json next_node_plan untouched (main only references, does not define the struct).

### [CHANGE A3] main FAST ENTRY contract untouched
- main.aisop.json FAST ENTRY execution contract ("...NEXT-NODE PLAN (per node_engine step3) then the full node-info; I will not skip nodes or shortcut." + DETERRENCE) left UNTOUCHED — no synonymous prose added, avoids nihil redundancy.

### [GH1] Inherited stale-tag cleanup
- 7 bare stale "(change A v5.41.0)" tags removed (main 3->0, node 4->0, normal already 0 cleaned prior run) per existing GH1/NihilDensity rules; the protected "JSON-VIA-FILE MANDATE, change A v5.41.0" brackets retained 1:1 in node_engine + normal_engine.

### [Un-weakened preservation]
- Each item verified present on disk, not weakened: six-section node-info; NEXT-NODE PLAN existing 5 fields + EMIT TIMING (incl. "for EVERY node INCLUDING the inline entry nodes"); NodeVerify; crash recovery; 3-state circuit breaker; sovereignty user_gate (writeCache user_gate_audit.py --enforce LIVE); writeCache; normal_engine ALL-INLINE OVERRIDE + step3(d) always-inline; dispatch_audit (pre-execution / completeness).

### [LEVEL_C] Automatic Fixes
- C1: Version + name sync 5.43.0 -> 5.44.0 all 4 modules; agent_engine version+name ONLY (functions block byte-identical to v5.43.0).
- C2: Version sync AIAP.md / agent_card.json / quality_baseline.json -> 5.44.0.
- C3: evolution_history + changelog append (this entry).
- C4: Governance hash TRI-SYNC recompute via tool_dirs/governance_hash.py (canonical v1.0, SOLE AUTHORITY).
- C5: Snapshot .evolution_snapshot/v5.44.0/ via tool_dirs/snapshot_build.py (snapshot_audit exit 0 mandatory).

### Quality
- ThreeDimTest: S grade (C=5.00, I=4.92, D=4.95 deferred-excluded). Source-of-truth recompute C*0.25 + I*0.45 + D*0.30 = 4.949. Zero-delta vs v5.43.0 (4.949); regression_flags=[].
- Validation: 18 changed leaves (8 version/name + 10 content) / 0 added / 0 removed / collateral=0 vs v5.43.0 snapshot; A1 NODE_PLAN_OMITTED grep=7, A2 will_output_next_node_plan=2 + will_write_cache_via_agent_write_node_cache_py=1, agent_engine functions byte-identical; 7 GH1 tag cleans.
- Simulation: GREEN (18/18 pass / 0 red / coverage 100%).
- Gates: EvolveStep UNCONDITIONAL gate TRUE HALT (user 'all'); ReviewPresent conditional gate finalize_risk=FALSE -> auto_approved (non-bypass).
- 0 breaking changes, fully backward compatible. A1/A2 are prose+field non-functional discipline strengthening; no machine-measurable static lift; A2 will_ fields reuse the existing agent-declared next_node_plan struct (no new tool, no new injection surface). Boundary (principle 7): only text/fields changed; runtime rendering/gating/reconciliation behavior unchanged; E1 band-out reconciliation SG is out of scope.
- Compliance: EU AI Act Art.50, EU CRA, ISO 42001, OWASP ASI, NIST CAISI (sovereignty gate preserved = Axiom 0 unweakened).

## [5.43.0] - 2026-06-16

### [CHANGE A1-A4] normal_engine.aisop.json ALL-INLINE-ization
- Background: normal_engine.aisop.json was a copy of node_engine (normal identity applied) that still carried per-node sub-agent dispatch. This evolution makes it all-inline — keeping node discipline structure, removing sub-agent dispatch.
- A1: generate_dispatch_plan call site now forces execute_mode='inline' for ALL nodes (no per-node agent/inline decision; inline nodes agent_id='inline_planned'); dispatch_audit downgraded to a pre-execution NO-OP.
- A2: programExec.step3 node-loop (d) always takes the inline execution path (orchestrator runs agent_engine.aisop.json init->execute->review->writeCache in place, NEVER spawns a sub-agent); 6 dangling d.0 / agent_id_generator references swept inline-consistent; DORMANT-BUT-KEPT block (agent guards e2e/e2e'/spawn_failure_evidence inert, not deleted).
- A3: dispatch_audit -> no-op (no agent nodes to audit, no violations reported); --completeness-check KEPT EXACTLY as a mode-agnostic post-hoc gate.
- A4: summary/description + 3 observability gen_ai_span_types rewritten to reflect "Normal Engine: node structure + all-inline execution (no sub-agent dispatch)".
- PRESERVED un-weakened: six-section node-info, NEXT-NODE PLAN, NodeVerify, crash recovery, 3-state circuit breaker, sovereignty user_gate (writeCache user_gate_audit --enforce LIVE for all terminal nodes, mode-agnostic), writeCache. agent_engine REUSED UNCHANGED by the inline path.
- NihilDensity GH1 incidentally cleaned 4 inherited "(change A v5.41.0)" inline tags (3 in step3, 1 in step5) — user-approved EXPECTED/ACCEPTABLE.

### [LEVEL_C] Automatic Fixes
- C1: Version + name sync 5.42.0 -> 5.43.0 all 4 modules (main/node_engine/agent_engine/normal_engine), no fork; main/node_engine/agent_engine version+name only (content byte-stable).
- C2: Version sync AIAP.md / agent_card.json / quality_baseline.json -> 5.43.0.
- C3: evolution_history + changelog append (this entry).
- C4: Governance hash TRI-SYNC recompute via tool_dirs/governance_hash.py (canonical v1.0, SOLE AUTHORITY).
- C5: Snapshot .evolution_snapshot/v5.43.0/ via tool_dirs/snapshot_build.py (snapshot_audit exit 0 mandatory).

### Quality
- ThreeDimTest: S grade (C=5.00, I=4.92, D=4.95 deferred-excluded; full-D=4.96, full weighted=4.952). Source-of-truth recompute C*0.25 + I*0.45 + D*0.30 = 4.949. Zero-delta vs v5.42.0 (4.949); regression_flags=[].
- Validation: 11 authorized leaves (2 name+version + 9 content) / 0 collateral vs v5.42.0 snapshot; 4 NihilDensity tag cleans.
- Simulation: GREEN (20 scenarios, 18 pass / 2 yellow-advisory / 0 red / coverage 100%).
- Gates: EvolveStep UNCONDITIONAL gate TRUE HALT (user 'all'); ReviewPresent conditional gate finalize_risk=FALSE -> auto_approved (non-bypass).
- 0 breaking changes, fully backward compatible. All-inline-ization is a structural execution-model refactor preserving every discipline structure un-weakened; no machine-measurable static lift.
- Compliance: EU AI Act Art.50, EU CRA, ISO 42001, OWASP ASI, NIST CAISI (sovereignty gate preserved = Axiom 0 unweakened).

## [5.41.0] - 2026-06-15

### [CHANGE A] ENG-STDIN strong mandate (JSON always via file, off the command line)
- A1: Every spec instruction writing _index.json (agent_update_index.py) or a node cache (agent_write_node_cache.py) converted to canonical "Write JSON to CONTEXT_DIR temp file (_tmp_*.json) -> --updates-file=<path> / --data-file=<path>" with three prohibitions (NO inline --updates/--data; NO printf|echo '{...}' | python; NO cd ... && compound). Landing points: agent_engine writeCache.step2 + inline-mode agent_write_node_cache prose; node_engine programExec.step3 all agent_update_index calls (dispatch_plan/current_node/nodes_status/next_node_plan) + constraints TOOL CALL DISCIPLINE upgraded to file-based canonical; main 3 engine-self render_claim writes (execute.step1/execute.step3/engineExec.step8) STDIN/args-list -> --updates-file; normal_engine node cache write segment -> --data-file. FORWARD-EFFECTIVE: drives the next engine run from v5.41.0.

### [CHANGE B] EU AI Act Art.50 penalty correction (single field)
- B1: main.aisop.json eu_ai_act_art50.penalties_context "Up to 35M EUR or 7% global turnover" -> "Up to 15M EUR or 3% of worldwide annual turnover" (Art.50 transparency = Art.99(4) €15M/3%; old 35M/7% is the Art.5 prohibited-practices tier Art.99(3), mis-assigned).
- Y1: agent_card.json penalties_context synced to corrected 15M/3% (spec<->metadata drift removed).

### [LEVEL_C] Automatic Fixes
- C1: Version + name sync 5.40.0 -> 5.41.0 all 4 modules (main/node_engine/agent_engine/normal_engine), no fork.
- C2: Version sync AIAP.md / agent_card.json / quality_baseline.json -> 5.41.0.
- C3: evolution_history + changelog append (this entry).
- C4: Governance hash TRI-SYNC recompute via tool_dirs/governance_hash.py (canonical v1.0, SOLE AUTHORITY).
- C5: Snapshot .evolution_snapshot/v5.41.0/ via tool_dirs/snapshot_build.py (snapshot_audit exit 0 mandatory).

### Quality
- ThreeDimTest: S grade (C=5.00, I=4.96, D=4.85 raw; deferred-excluded weighted=4.949, full=4.929). Zero-delta vs v5.40.0 (4.949); regression_flags=[].
- Validation: 22/22 leaf checks PASS (0 blocking, 1 deferred advisory) vs v5.40.0 snapshot.
- Simulation: GREEN.
- Gates: EvolveStep TRUE HALT (user 'all + Y1'); ReviewPresent conditional gate finalize_risk=FALSE -> auto_approved (non-bypass).
- 0 breaking changes, fully backward compatible. Change A is prompt-level discipline (no dispatch/data-contract change); change B/Y1 are passive compliance-string corrections.
- Compliance: EU AI Act Art.50 (penalty tier corrected), EU CRA, ISO 42001, OWASP ASI, NIST CAISI.

## [5.20.0] - 2026-06-04

### [LEVEL_B] Functional Changes
- B1: main.aisop.json engineExec step key renaming -- non-standard keys (step1_integrity, step1_lite) renamed to sequential format (step2, step3) with downstream step numbers shifted (step2->step4, step3->step5, step4->step6, step5->step7, step6->step8). Fixes STEP_KEY_FORMAT YELLOW per UN/CEFACT JSON Schema NDR and AWS Step Functions sequential naming convention.
- B2: normal_engine.aisop.json inlineEnd Error field addition -- terminal node now has error handling (retry(1)->circuit-breaker->fallback(proceed with inline_warning)->inform(User)), fixing INLINEEND_ERROR YELLOW per RFC 9457 Problem Details pattern.

### [LEVEL_C] Automatic Fixes
- C1: Version bump 5.19.0 -> 5.20.0 all 4 .aisop.json + AIAP.md + agent_card.json + quality_baseline.json
- C2: Name field version sync to v5.20.0 (main/node_engine/normal_engine/agent_engine)
- C3: evolution_history append v5.20.0 entry to AIAP.md + quality_baseline.json
- C4: Governance hash TRI-SYNC recompute at ReviewFinalize

### Quality
- ThreeDimTest: S grade (C=5.000, I=4.962, D=4.950, weighted=4.968)
- Validation: 44/44 PASS (v5.19.0: 42/44, 2 YELLOW fixed this cycle)
- Simulation: 22/22 PASS, 100% coverage
- 0 breaking changes, fully backward compatible
- Compliance: EU AI Act Art.50, EU CRA, ISO 42001, OWASP ASI, NIST CAISI

## [5.19.0] - 2026-06-04

### [LEVEL_B] Functional Changes
- B1: node_engine step4 EXPLAIN forced per-summary [PHYSICAL READ] user_language anchor -- orchestrator MUST physically re-read _index.json::user_language before each Node Summary, preventing language drift in long pipelines (root cause: prompt adherence decay)

### [LEVEL_C] Automatic Fixes
- C1: Version bump 5.18.0 -> 5.19.0 all modules
- C2: Name field version sync to v5.19.0
- C3: evolution_history append v5.19.0 entry
- C4: Governance hash TRI-SYNC recompute

### Quality
- ThreeDimTest: S grade (C=5.00, I=4.96, D=5.00, weighted=4.982)
- Assert coverage: 25 asserts, 18/18 MF28b, 100% GREEN
- Direction continuity: 0.95 HIGH (continues v5.18.0 User Language Anchor)
- Compliance: NIST AI RMF, EU AI Act, ISO 42001, MCP, NIST CAISI

## [5.16.0] - 2026-05-30

### [LEVEL_B] Functional Changes
- B1: Added sovereignty gate enforcement (user_gate_audit.py --enforce) to normal_engine writeCache.step3, achieving Axiom 0 Layer-1 backstop parity across all 3 engines

### [LEVEL_C] Automatic Fixes
- C1: Harmonized agent_engine writeCache field count references (12 -> 15)
- C2: Fixed main.aisop.json system_prompt placeholder
- C3: Aligned normal_engine Error fields to error_taxonomy
- C4: Trimmed agent_engine description to current-version-only
- C5: Updated AIAP.md benchmark note to v5.15.0
- C6: Version sync across all modules (5.15.0 -> 5.16.0)
- C7: Governance hash TRI-SYNC recompute

### Quality
- ThreeDimTest: S grade (C=4.93, I=4.95, D=4.90, weighted=4.930)
- Simulation: 3/3 PASS (GREEN)
- Validation: 24/24 PASS
- Compliance: EU AI Act Art.50, EU CRA, ISO 42001, OWASP ASI, NIST CAISI

## [5.15.0] - 2026-05-30

### [LEVEL_B] Functional Changes
- B1: Agent-mode last_completed_node advancement in agent_engine.writeCache.step2

### [LEVEL_C] Automatic Fixes
- C1-C5: Version sync, name sync, evolution_history, governance_hash TRI-SYNC, parallel-wave caveat doc

### Quality
- ThreeDimTest: S grade (C=4.93, I=4.95, D=4.90, weighted=4.930)
