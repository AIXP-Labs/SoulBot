# Changelog

All notable changes to soulbot_execute_engine are documented in this file.

## [5.52.0] - 2026-07-04

ENGINE SELF-EVOLUTION (target = engine directory itself; only this one copy modified). MINOR, additive, breaks:none. Directed evolution: legislate the Axiom-0 ASK-PRINCIPLE ("multi-candidate routing ambiguity -> defer to the user") into the engine match/classify law, eliminating the two-law coexistence between match.uncertain's silent `route to classify` auto-pick and the registry-block trailer's already-declared ask-principle. That coexistence produced an observable behavior flip: the identical ambiguous input "创建一个 AISP 技能:…" once stopped-to-ask and once silently locked (cache/194). Human ruled MINOR at the EvolveStep gate — this cashes out an ALREADY-declared ask-behavior rather than flipping a contract predicate; zero contract impact on any target program (match/classify is engine-internal package-selection routing). Scope confined to main.aisop.json functions.match.uncertain + functions.classify; the 3 sibling engine modules (agent/node/normal) received version+name+description-note sync only.

### [CHANGE A1] match.uncertain multi-candidate disposition -> STOP-and-ask the user (Axiom 0)
- When >=2 specialized packages could cover the same intent AND the user did NOT explicitly name a package (by package name, or executor-protocol naming like "use X ...") -> the engine no longer auto-picks and no longer hands the choice to classify to auto-pick. Instead it presents a NUMBERED candidate list (one-line brief each, optional recommendation) and STOPS to ask the user to choose. Explicit user naming is ALWAYS absolute priority; a single unique match still routes directly as before; protocol words inside a product description (e.g. "create an AISP skill") do NOT constitute executor naming. TWO-SIDED GUARD: ask ONLY on a genuine >=2-candidate doubt, NEVER over-gate a clean single-candidate case (mirrors the runner v2.42.0->v2.43.0 sovereignty-gate conditionality arc).

### [CHANGE A2] classify realignment — no longer a covert multi-candidate auto-pick channel
- functions.classify (step1/step2/constraints) narrowed to match.Error single-package error-recovery. The old "use classification result to determine the correct AIAP package" auto-pick semantics are removed; an ambiguous classifier result hands back to the ask-the-user path (coupled to A1, non-contradictory), so the two laws no longer coexist. This is the cache/194 behavior-flip root fix.

### [ModifyStep FIXES] 3 in-scope Research2 fix candidates (prose/additive only)
- R2-FIX-1 (classify.constraints graph-label note): the `|uncertain|` mermaid edge is retained for structural continuity but its LIVE semantic is now ASK-THE-USER / match.Error single-package recovery, NOT multi-candidate auto-pick; any real topology change deferred to the human (topology byte-preserved). R2-FIX-2 (match.uncertain PENDING-SELECTION contract sketch): execution-cache state only, renames nothing. R2-FIX-3 (match.uncertain "use X" ambiguous naming-parse edge): explicit "use X"/bare-name routes directly ONLY if X resolves to exactly one package; ambiguous X falls through to the ask clause.

### [SCOPE GUARD / ZERO-REGRESSION]
- Only main.aisop.json match/classify routing law touched. execute / engineExec / endNode + ALL execution, dispatch, audit, red-line, and gate machinery UNCHANGED. python_tools NEVER touched; no cache/contract field renamed; graph topology byte-identical; protocol identity AIAP V1.0.0 preserved. Preserved-unchanged (C2 annotation): context_rule stickiness, no_match->soulbot_chat default, single-candidate direct route, explicit-naming priority.

### [GOVERNANCE]
- EvolveStep TRUE HALT — human reply 'all' accepted A1+A2 + semver ruling MINOR (v5.52.0), question_hash fa43571197f27f98. ReviewPresent conditional gate finalize_risk=FALSE (4 triggers all FALSE) -> spec-mandated AUTO-APPROVED (conditional gate, non-bypass). QualityGate GREEN weighted=4.72 Grade S score_scope=partial (only main.aisop.json scored; whole-program S baseline 4.949 PRESERVED per SCORE SCOPE GUARD). SimulateStep GREEN 29 scenarios 0 RED/0 YELLOW (cache/194 flip fixed); ValidateStep 0 blocking fail; NihilDensity ~0.00; Research3 compliance 0 GAP / 0 YELLOW / 0 RED (EU AI Act Art.14 human-oversight + NIST GOVERN decision-rights + ISO 42001 blocking-approval-gate + MCP SEP-2260 in-context elicitation directional endorsement; no new external framework triggered). 4 modules unified to 5.52.0. governance_hash via tool_dirs/governance_hash.py (canonical v1.0, SOLE AUTHORITY) + TRI-SYNC=3; attestation_chain advanced via tool_dirs/attestation_advance.py (SOLE AUTHORITY); .evolution_snapshot/v5.52.0/ via tool_dirs/snapshot_build.py (built LAST, snapshot_audit.py exit 0 mandatory). 0 breaking changes, all additive.

## [5.51.0] - 2026-07-03

ENGINE SELF-EVOLUTION (target = live engine directory; only this one copy modified, highest risk). MINOR, additive, breaks:none. Directed evolution: extend the v5.50.0 CONTRACT RED-LINE HARD_FAIL hard-gate to the INLINE execution path + make the B2 audit trail actually land on disk (empirically both cache/188 mixed and cache/189 all-inline runs had ZERO 'redline' trace — the v5.50.0 build/tag/land logic lived only in the agent-dispatch path). agent_engine v5.50.0 red-line donor anchors (init.step1 map build, execute.step3 tag, execute.step6 HARD_FAIL route, writeCache.step2 per-node audit) are UNCHANGED and remain authoritative; the v5.51.0 change lives entirely in node_engine/normal_engine programExec.step3(d) inline branches + step5, mirroring the donor so inline execution enforces contract red-lines identically to agent dispatch.

### [CHANGE A1] node_engine inline red-line HARD_FAIL parity (programExec.step3(d))
- The inline execution branch now builds redline_map from the target's declared non_negotiable[] entries (same protocol-agnostic PREDICATE + B3 form-based exclusion table as agent_engine.init.step1), tags the matching ':sys.assert'-form step is_redline=true, and routes a tagged assertion_error to HARD_FAIL (no retry / no DEGRADED / no skip / no continue) writing hard_fail=true + redline_triggered={rule_index,rule_text,enforced_by,node,step,failed_expr,failed_value}. programExec.step3 STOPs on the FIRST hard_fail (independent of the 3-consecutive circuit breaker) via the sovereignty-halt channel. Byte-exact field shape parity with agent_engine execute.step6 + node cache json_schema.

### [CHANGE A2] normal_engine inline red-line HARD_FAIL parity + IN-PLACE wording fix
- Same inline HARD_FAIL parity as A1 applied to normal_engine (all-inline engine — every node takes the inline path, so this is its ONLY red-line enforcement site). Corrected misleading IN-PLACE wording in the affected step so the inline execution semantics read unambiguously.

### [CHANGE B1] Run-level red-line audit landing (node_engine + normal_engine step5)
- When the target DECLARED contract red-lines (redline_map NON-EMPTY this run), step5 merges a run-level summary into _index.json under the DISTINCT additive key redline_map_audit_run { declared_count, hits:[{node,step,rule_index,enforced_by}], triggered:bool }. This is a NEW run-level roll-up key, deliberately NOT the same key as the per-node redline_map_audit written by agent_engine.writeCache.step2 (Research2 FIX-1: avoids an _index _deep_merge collision + 'triggered' clobber in mixed agent+inline runs where the two shapes differ). COEXISTENCE CONTRACT: per-node redline_map_audit (agent path) and run-level redline_map_audit_run (this landing) are DISTINCT top-level _index keys with distinct shapes — they coexist without collision and a strict reader parses both cleanly. This guarantees an all-inline run (whose nodes never invoke agent_engine.writeCache.step2 as a spawned sub-agent) STILL records the run-level audit trail, closing the cache/188 + cache/189 zero-trace gap.

### [ZERO-REGRESSION GUARANTEE]
- EMPTY-GUARD: when redline_map is EMPTY (ordinary AIAP target — no declared contract red-line) NO step is tagged, hard_fail is never set, and redline_map_audit_run is OMITTED entirely (not written as empty {}) — the AIAP-program _index/cache shape stays BYTE-IDENTICAL to prior behavior.

### [LEVEL_C] Automatic Fixes
- C1: MINOR bump 5.50.0 -> 5.51.0 across all 4 .aisop.json + AIAP.md + agent_card.json + quality_baseline.json. breaks:none rationale (user-legislated at EvolveStep): fulfilling an already-declared hard-gate on the inline path is an application of existing v5.50.0 red-line legislation (an "should-have-fired gate now fires" hardening), NOT a contract flip — no prior compliant AIAP-target behavior changes; a violating execution was never compliant. Same MINOR/breaks:none judgment as the v5.50.0 gate itself.

### [Boundaries held]
- python_tools NEVER modified; NO cache/contract field renamed (redline_map_audit / hard_fail / redline_triggered keys preserved verbatim — redline_map_audit_run is a purely ADDITIVE new key); engine protocol identity 'AIAP V1.0.0' verbatim x4; program_id dev.soulbot.execute_engine.* unchanged; agent_engine v5.50.0 red-line donor logic byte-identical. No other execution/dispatch/audit/gate logic touched.

### [ReviewFinalize]
- Grade S; Generate2 partial like-for-like weighted 4.79; score_scope=partial -> whole-program weighted PRESERVED 4.949/S (SCORE SCOPE GUARD; regression_flags=[]; ZERO-DELTA). governance_hash f8d69e68 -> cc3fdc11 (TRI-SYNC=3 AIAP.md/agent_card.json/quality_baseline.json, read-back PASS) computed by SOLE-AUTHORITY tool_dirs/governance_hash.py (canonical v1.0: 4 *.aisop.json sorted-ASCII, per-file JCS json.dumps, 0x1E RS join, SHA-256); attestation_chain synced via SOLE-AUTHORITY tool_dirs/attestation_advance.py to chain_length 48; .evolution_snapshot/v5.51.0/ built + snapshot_audit exit 0; 0 collateral (python_tools byte-clean). NOTE: a prior finalize pass had written a NON-canonical hash ff3236d2 (hand-rolled NUL-framing method, NOT the SOLE-AUTHORITY tool); this pass authoritatively recomputed with governance_hash.py and corrected TRI-SYNC + attestation + version_history/evolution_history citations to cc3fdc11.

## [5.50.0] - 2026-07-02

ENGINE SELF-EVOLUTION (target = live engine directory; only this one copy modified, highest risk). MINOR, additive. FINALIZED by Creator Evolve pipeline (cache/186) ReviewFinalize. CONTRACT RED-LINE HARD_FAIL HARD-GATE SEMANTICS. Grade S; Generate2 partial weighted 4.7813 (C=4.5 cognitive-cap / I=4.9846 / D 4.85 deferred); ReviewFinalize P23 full-D changed_file_score 4.8063; score_scope=partial -> whole-program weighted PRESERVED 4.949; SIMULATE=GREEN; regression_flags=[]. governance_hash 544c809f -> f8d69e68 (TRI-SYNC=3); attestation_chain 45 -> 46; snapshot v5.50.0 audit exit 0.

### [CHANGE A1] Contract red-line HARD_FAIL hard-gate (LEVEL_A)
- Protocol-agnostic PREDICATE (NOT an 'is-AISP' branch): when a TARGET package declares a non_negotiable red-line array whose entries carry an enforced_by binding (canonical user.content.aisp_contract.non_negotiable[].enforced_by), each ':sys.assert'-form binding is treated as a HARD GATE.
- agent_engine.init.step1 builds redline_map {rule_index, rule_text, enforced_by, form-based scope}. execute.step3 tags the matching sys.assert step is_redline=true. execute.step6 routes a tagged assertion_error to HARD_FAIL: no retry / no DEGRADED / no skip / no continue.

### [CHANGE B1] Structured stop-record redline_triggered
- On HARD_FAIL, cache carries hard_fail=true + redline_triggered={rule_text, rule_index, enforced_by, node, step, failed_expr, failed_value} surfacing the breached red-line to the human.

### [CHANGE B2] redline_map_audit trail
- Read-only diagnostic summary written into _index.json (ADDITIVE key, no field rename); emitted only when redline_map is non-empty.

### [CHANGE B3] enforced_by-FORM exclusion table
- ':sys.assert' IN scope; ':sys.io.confirm'/':sys.io.read' already Axiom-0 hard; 'tools' AND 'aisop.main' EXPLICITLY EXCLUDED from the single-assert hard gate (aisop.main is whole-flow-carried with no single assert step — user-legislated resume refinement, same rationale as 'tools').
- node_engine/normal_engine programExec.step3 STOP on the FIRST hard_fail (independent of the 3-consecutive circuit breaker) via the sovereignty-halt channel.

### [ZERO-REGRESSION GUARANTEE]
- For ordinary AIAP programs (predicate FALSE -> redline_map EMPTY) NO step is tagged, hard_fail is never set, redline_map_audit is not emitted — cache shape byte-identical. Verified end-to-end this run: the executing TARGET (soulbot_creator_evolution_aiap) is an ordinary AIAP program (0 contract red-lines) -> ZERO-REGRESSION path exercised.

### [LEVEL_C] Automatic Fixes
- C1-C4: version + name sync 5.49.0 -> 5.50.0 (4 .aisop.json + AIAP.md + agent_card.json + quality_baseline.json); embedded doc-schema (hard_fail/redline_triggered) sync; metadata sync.

### [Boundaries held]
- python_tools NEVER modified; NO cache/contract field renamed; engine protocol identity 'AIAP V1.0.0' verbatim x4; program_id dev.soulbot.execute_engine.* unchanged. No other execution/dispatch/audit/gate logic touched.

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
