---
# AIAP Governance Contract
# Governance Fields (6 required)
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

# Project Fields (8 required)
name: soulbot_execute_engine
version: "5.17.0"
pattern: B+
tool_dirs: []                # No tool packages embedded; python_tools/ is executor_shim only
executor_shim: true          # python_tools/ contains executor-internal shims (prepare_cache.py, etc.) — NOT registered tools per AIAP Pattern G. See 'executor_shim note' below.
flow_format: "mermaid"
summary: "SoulBot Execute Engine v5.17.0 -- MINOR: Sovereignty Bug Protocol. A1 sovereignty_bug_protocol shared section (main.aisop.json + agent_engine.aisop.json): sovereignty_toolset enumeration, self_modification_red_line, bug_classification 3-tier, bug_legal_channel (separation of powers), exposure_chain_spec (sovereignty_log with prev_hash). B1 RULES.sovereignty_bug execution rule in agent_engine (Critical=immediate WAITING_USER, Medium=continue+report, Light=summary+ask). 0 breaking changes. X3 sovereignty enforcement, HMAC Phase 2, deterministic dispatch, server-side agent_id retained. 4 modules, 14 nodes. Pattern B+."
governance_hash: "sha256:0d1f81c467b94f4cf5769541900c1aeaa0badb3452470069e0eef9c4e7c340dc"
hash_algorithm_version: "v1.0"
governance_hash_canonical_version: "1.0"
tools:
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: false
modules:
  - id: soulbot_execute_engine.main
    file: main.aisop.json
    nodes: 5
    critical: true
    idempotent: false
    side_effects: [file_write]
    execution_mode: sequential
    description: "Engine Router — matches user intent to AIAP package, creates execution cache, selects engine by loading_mode, orchestrates execution with NodeSummary + ExecutionSummary. WAITING_USER/MESSAGE_PENDING relay. trace_id generation."
  - id: soulbot_execute_engine.node
    file: node_engine.aisop.json
    nodes: 2
    critical: true
    idempotent: false
    side_effects: [file_write]
    execution_mode: hybrid
    description: "Node Engine — executes target AIAP node-by-node via Sub Agent dispatch (default agent). Deterministic dispatch_plan generation via generate_dispatch_plan.py (v5.7.0 A1). Dispatch audit pre-execution gate (v5.7.0 A3). Crash recovery (last_completed_node), circuit breaker (3-state: closed/half-open/open), parallel dispatch (independent branch analysis), NodeVerify audit, Decision Node gate routing. Transient cache retry with exponential backoff (v5.6.1 A2)."
  - id: soulbot_execute_engine.normal
    file: normal_engine.aisop.json
    nodes: 2
    critical: true
    idempotent: false
    side_effects: [file_write]
    execution_mode: sequential
    description: "Normal Engine — executes target AIAP node-by-node inline (default inline). Crash recovery, circuit breaker (3-state: closed/open/half-open, parity with node_engine), NodeVerify audit, Decision Node gate routing. sys.* inline handling."
  - id: soulbot_execute_engine.agent
    file: agent_engine.aisop.json
    nodes: 5
    critical: true
    idempotent: false
    side_effects: [file_write]
    execution_mode: sequential
    description: "Agent Engine — Sub Agent execution contract. init (read target + context + ASSERT-driven selective read + SCOPE GUARD + RESUME_MODE) -> execute (execution loop with RULES.sys/user_input/user_message/on_error/sovereignty_bug) -> review (tool call verification) -> writeCache (atomic write + read-back verification + steps_done/remaining + last_completed_node advancement for terminal nodes + sovereignty gate enforcement via user_gate_audit.py --enforce). v5.17.0: RULES.sovereignty_bug (3-tier classification for sovereignty toolset bugs). Identity-defined, Print-it commitment."

# Identity
program_id: dev.soulbot.execute_engine
identity:
  publisher: "AIXP Foundation AIXP.dev | SoulBot.dev"
  verified_on: "2026-05-29"
trust_level:
  level: 3
  justification: "Execute Engine requires read/write access to execution cache directory and target AIAP files. No network access. No destructive operations. Internal orchestration component."
  constraints:
    - "file_system write scope limited to execution_cache_dir and target workspace"
    - "no network access required"
    - "no destructive file operations (no delete, no overwrite without atomic pattern)"
discovery_keywords: [engine, router, execute, dispatch, orchestration, node, agent, sys, circuit-breaker, crash-recovery, parallel, interrupt, resume]
tags: [execution-engine, orchestrator, multi-engine, sub-agent, sys-handling, node-verify, decision-gate, interrupt-relay]
author: SoulBot.dev
license: Apache-2.0
copyright: "Copyright 2026 AIXP Foundation AIXP.dev | SoulBot.dev"

# Permissions
permissions:
  file_system:
    scope: "./execution_cache/ + target workspace"
    operations: ["read", "write"]
  network:
    allowed: false
  shell: false               # Shell execution is restricted; only python invocation via subprocess argv list (no shell=True, no user-content interpolation via echo)

# Runtime
runtime:
  timeout_seconds: 300
  max_retries: 3
  token_budget: 80000
  idempotent: false
  side_effects: [file_write]
  circuit_breaker:
    consecutive_failure_threshold: 3
    half_open_timeout_seconds: 30
  crash_recovery:
    mechanism: "last_completed_node atomic marker in _index.json"
    resume: "skip completed nodes on re-entry"

# Capabilities
capabilities:
  offered:
    - intent_matching
    - engine_routing
    - node_dispatch
    - sub_agent_orchestration
    - crash_recovery
    - circuit_breaker
    - parallel_dispatch
    - execution_observability
    - sys_call_handling
    - node_verify_audit
    - decision_node_routing
    - interrupt_relay
    - on_error_routing
    - steps_tracking
    - trace_id_propagation
    - bootstrap_validation
    - opentelemetry_sdk_integration
    - owasp_asi_threat_mapping
    - server_side_agent_id_generation
    - dispatch_records_anti_forgery
    - integrity_only_audit
    - transient_cache_retry
    - degraded_reason_enum
    - write_cache_read_back_verification
    - deterministic_dispatch_plan_generation
    - dispatch_audit_pre_execution_gate
  required:
    - file_system

# Dependencies
dependencies:
  - file: "target AIAP main.aisop.json"
    required: true
    description: "Target program to execute. Provided by agent.py via entry_path."
  - file: "execution_cache directory"
    required: true
    description: "Cache directory for _index.json, node caches, conversation_context. Provided by agent.py."
snapshot_scope:
  - "*.aisop.json"
  - "AIAP.md"
  - "agent_card.json"
  - "quality_baseline.json"
  - "python_tools/"
min_protocol_version: "AIAP V1.0.0"

# Status
status: active
applicability_condition:
  triggers:
    - "EXECUTE_ENGINE=true in agent.py configuration"
    - "user message matched to any AIAP package in registry"
  preconditions:
    - "agent.py loads main.aisop.json from soulbot_execute_engine_aiap/"
    - "target AIAP package exists with valid main.aisop.json"
    - "execution_cache directory writable"
  exclusions:
    - "EXECUTE_ENGINE=false (uses soulbot_router.aisop.json instead)"
    - "target AIAP file not found or invalid JSON"
  confidence_threshold: 0.8
intent_examples:
  - "你好 (Chat intent → soulbot_chat → normal_engine inline)"
  - "给我讲个笑话 (Creative intent → soulbot_chat → normal_engine inline)"
  - "进化 soulbot_chat (Evolve intent → soulbot_creator_evolution → node_engine agent)"
  - "验证 expense_tracker (Validate intent → soulbot_creator_evolution → node_engine agent)"

# Benchmark
benchmark:
  threedimscore: "4.97"
  grade: "S"
  cognitive: "4.930"
  intrinsic: "5.000"
  detail: "4.950"
  simulation_coverage: "100%"
  total_nodes: 14
  pass_rate: "100%"
  nihil_density: "0.4%"
  note: "v5.15.0 FINALIZED by ReviewFinalize (cache/57). Full scope (4/4 modules). ThreeDimTest: C=4.930 I=4.950 D=4.800 stage-weighted=4.900 (Professional C*0.25+I*0.45+D*0.30). Post-Finalize D6/D10 reconciliation: D_avg 4.80->4.90, final_adjusted=4.930 Grade S. Previous: v5.14.1 weighted=4.97 (Grade S)."

# Quality
quality:
  weighted_score: "4.930"
  grade: "S"
  last_pipeline: "Creator Evolve pipeline v5.16.0 FINALIZED by ReviewFinalize (cache/58, 2026-05-30): v5.15.0 -> v5.16.0 MINOR. B1 normal_engine sovereignty gate enforcement. ThreeDimTest: C=4.93 I=4.95 D=4.90 weighted=4.930 Grade S. Simulation: 3/3 PASS. Validation: 24/24 PASS. Previous: v5.15.0 final_adjusted=4.930 Grade S."
  changes_v4_0_0: "15 items: A1(AIAP.md) + A2(quality_baseline) + B1(crash recovery) + B2(circuit breaker) + B3(parallel dispatch) + B4(execution metrics) + B5(tool annotations) + C1-C8(atomic writes, cache schema, retry classification, turn_type, ASSERT gates, version sync, json_schema, identity). ThreeDimTest: 4.43 weighted (Grade A). Created by Creator Evolve pipeline (cache/129)."
  changes_v5_0_0: "14 design items + 4 quality fixes: M1(WAITING_USER/MESSAGE_PENDING relay), A1(identity definition), A2(Print-it), A3(USER_MESSAGE), A4(sys.* 24-call handling), A5(AGENT_ID), A6(on_error routing), A7(steps_done/remaining), N1(NodeVerify), N1.5(parallel wave interrupt), N2(Decision Node gate), N3(sys.* bootstrap hint), NM1-NM3(normal_engine parity). QS-01(half-open circuit breaker), QS-04(trace_id), QS-05(bootstrap validation), QS-06(normal_engine resilience parity). ThreeDimTest: 4.72 weighted (Grade A). Created by Creator Create pipeline (cache/131). Based on 05-engine-aiap-v5-design.md."
  changes_v5_2_0: "Architecture refactor (non-Creator): prepare_cache.py dual-use module introduced at python_tools/prepare_cache.py — callable as Python library (agent.py fast path ~5ms) or Bash CLI (AISOP fallback ~300ms). agent.py reduced from ~450 to ~361 lines (-89). main.aisop.json execute.step2/step3 simplified — single source of truth for cache creation. 16 test cases added (TestLibraryAPI x8 + TestCLI x5 + TestEquivalence x3), 16/16 PASS. Portable across Agent frameworks supporting Bash. Architecture aligned with 'AISOP layer only creates new caches' principle. Based on 05-prepare-cache-dual-use-plan.md."

# Evolution History
evolution:
  - version: "3.1.0"
    date: "2026-04-05"
    note: "Pre-evolution baseline. 4 modules, 14 nodes. Router + dual engine architecture established."
  - version: "4.0.0"
    date: "2026-04-05"
    note: "Major evolution via Creator Evolve pipeline (cache/129). 15 items: crash recovery, circuit breaker, parallel dispatch, execution metrics, atomic writes, ASSERT gates, json_schema, identity. ThreeDimTest 4.43 (A)."
  - version: "5.0.0"
    date: "2026-04-06"
    note: "Full rebuild via Creator Create pipeline (cache/131). 14 design items from 05-engine-aiap-v5-design.md + 4 quality fixes. sys.* 24-call handling, WAITING_USER/MESSAGE_PENDING relay, NodeVerify, Decision Node gate, identity/Print-it/USER_MESSAGE, on_error routing, steps_done tracking, half-open circuit breaker, trace_id propagation, bootstrap validation. ThreeDimTest 4.72 (A)."
  - version: "5.1.0"
    date: "2026-04-06"
    note: "Minor version bump. WAITING_USER/MESSAGE_PENDING relay refinements in engineExec.step3 (M1). Version refs sync across main/node_engine/normal_engine."
  - version: "5.2.0"
    date: "2026-04-12"
    note: "prepare_cache.py dual-use module introduced at python_tools/prepare_cache.py. Single source of truth for cache creation, callable via Python library (agent.py fast path ~5ms) or Bash CLI (AISOP fallback ~300ms). main.aisop.json execute.step2/step3 simplified — removed redundant AISOP-side cache creation logic, step3 now only updates _index.json with match result. agent.py reduced from ~450 to ~361 lines. Portable across Agent frameworks supporting Bash (Claude Code, Gemini CLI, OpenCode). Architecture aligned with 'AISOP layer only creates new caches' principle (agent.py:27-28 comment). Test suite: 16 cases (Library API + CLI + Equivalence). Based on 05-prepare-cache-dual-use-plan.md."
  - version: "5.2.1"
    date: "2026-04-12"
    note: "cleanup_cache migration — completing cache lifecycle consolidation. Moved _cleanup_cache from agent.py (55 lines) to prepare_cache.py as library-only function. prepare_cache.py now owns FULL cache lifecycle: prepare_execution_context (create) + cleanup_cache (delete). agent.py reduced from 361 to 310 lines (-51 lines). Shared helpers (_load_or_init_ctx, _atomic_write_json, _CACHE_DIR_RE) eliminate duplication. cleanup_cache preserves non-numbered dirs (legacy hex IDs). Test suite: 16 -> 20 cases (TestCleanup class with 4 new tests, all PASS). No behavior change, pure architecture consolidation. Any Agent framework can now import prepare_cache for complete cache lifecycle support."
  - version: "5.2.2"
    date: "2026-04-12"
    note: "cleanup embedded in prepare — atomic cache lifecycle. prepare_execution_context now runs cleanup_cache internally at function start (equivalent to original agent.py sequence of cleanup() then prepare(), merged into one atomic call). agent.py further simplified: removed explicit cleanup_cache import + call, removed try/except graceful-degradation fallback. agent.py reduced from 311 to 295 lines (-16). Cumulative agent.py reduction v5.1.0 -> v5.2.2: 450 -> 295 lines (-155 / -35%). cleanup_cache remains public API for explicit use (tests, maintenance). subprocess (Bash CLI fallback) automatically benefits — every prepare call ensures cleanup first. Zero API breakage, 20/20 tests still PASS."
  - version: "5.2.3"
    date: "2026-04-13"
    note: "Security + consistency hardening via Creator Evolve pipeline (cache/120). P1 AIAP.md frontmatter: tool_dirs=[], executor_shim=true (Pattern G clarification — python_tools/ is executor-internal shim, NOT registered tool), shell=false permission. P2-P4 main.aisop.json execute.step2: Bash fallback shell-echo replaced with --payload-file tempfile transport (safer per I15); execute.constraints extended with SHELL SAFETY (I15) + INPUT GUARDS (I2 5-pillar: TYPE/INJECTION/SIZE/PATH/ENCODING) + THREAT MITIGATIONS (I8 AT4/AT6). P5 normal_engine.aisop.json: circuit_breaker_state enum 2-state → 3-state (closed/open/half-open) mirroring node_engine; programExec.step3 rewritten with half-open transition (half_open_timeout_seconds=30, half_open_max_calls=5, recovery_timeout=120 for critical paths). P6 ASSERT gates (main engineExec.step1 + node_engine programExec.step1 + normal_engine programExec.step1 + agent_engine execute.step1): property predicates appended — regex match on entry_path, file_exists check, loading_mode enum, realpath workspace containment. P7 advisory only. Version bumps: main 5.2.2→5.2.3, normal_engine 5.1.0→5.2.0 (semantic circuit breaker change). All 4 .aisop.json files JSON-validated post-edit."
  - version: "5.3.0"
    date: "2026-05-13"
    note: "Observability-first evolution via Creator Evolve pipeline. 8 items: A1 OpenTelemetry SDK integration (opentelemetry-sdk capability dependency across all 4 modules, trace_id/span_id wired to OTel context propagation per gen_ai semantic conventions), A2 events[] declaration + SpanEvent dispatcher (5 events in node_engine: node_started, node_completed, node_failed, circuit_breaker_tripped, decision_gate_routed), B1 OWASP ASI threat mapping (ASI01-ASI10, 4 YELLOW items addressed: ASI01 goal_hash drift, ASI06 cache HMAC, ASI07 IPC signatures, ASI10 runtime drift), C1 version sync (all modules to 5.3.0), C2 ASSERT gate property predicate refresh, C3 normal_engine orphan function cleanup (MF31), C4 python_tools/ PL26 snapshot scope inclusion, C5 Error->on_error dual-key transitional support. All additive, zero breaking changes."
  - version: "5.4.0"
    date: "2026-05-18"
    note: "Governance + integrity hardening. 8 items (4B + 4C): B1 agent_id naming, B2 score_integrity_rules, B3 dispatch_audit, B4 score_confidence, C1 governance_hash canonical, C2 version_history append-only, C3 module_scores stale, C4+C5 version sync."
  - version: "5.4.1"
    date: "2026-05-18"
    note: "Agent_id strict enum + dispatch_audit mandatory + governance_hash TRI-SYNC. 6 items (3A + 3C): A1 agent_id strict 5-category enum (auto-<hex8>/task-<hex8>/gemini-<hex8>/inline_planned/inline_fallback) enforced in json_schema + dispatch + writeCache + python_tools, A2 dispatch_audit MANDATORY gate (CRITICAL blocks pipeline), A3 governance_hash TRI-SYNC (AIAP.md + agent_card.json + quality_baseline.json + hash_algorithm_version=v1.0), C1 version bump, C2 name sync, C3 evolution_history + bootstrap_advisory. All additive, zero breaking changes."
  - version: "5.4.2"
    date: "2026-05-19"
    note: "Internal consistency patch. 8 items (4A + 4C): A1 dispatch_audit total_nodes off-by-one fix (explicit category sum, invariant cross-validation), A2 governance_hash intermediate snapshot pipeline_note (intermediate hashes marked stale, expires_after=ReviewFinalize), A3 engine_version _ENGINE_VERSION sync 5.2.2->5.4.2, A4 initial_user_message write-once field in _index.json. C1 version bump, C2 name sync, C3 evolution_history append, C4 governance_hash deferred to ReviewFinalize. All additive, zero breaking changes."
  - version: "5.4.3"
    date: "2026-05-19"
    note: "Dispatch plan compliance patch. 8 items (4A + 4C): A1 RESUME/boot path explicit re-dispatch with dispatch_plan compliance enforcement (main engineExec.step3, node_engine RESUME_MODE_DISPATCH, agent_engine writeCache plan-violation hard validator), A2 dispatch_audit plan-violation category with cross-check against dispatch_plan from _index.json, A3 dispatch_plan_expected cache schema field (agent_engine + normal_engine + agent_write_node_cache.py auto-fill), A4 task-hex capability verification (node_engine + agent_engine capability cross-check). C1 version bump, C2 name sync, C3 evolution_history append, C4 governance_hash deferred to ReviewFinalize. All additive, zero breaking changes."
  - version: "5.4.4"
    date: "2026-05-19"
    note: "Agent_id integrity patch. 6 items (3A + 3C): A1 agent_id entropy + uniqueness HARD enforcement (unique hex chars >= 4, cross-cache uniqueness rejection, os.urandom(4).hex() mandated in resolve_agent_id), A2 dispatch_audit fake_hex 4-category detection (trivial/invalid/duplicate/low_entropy) + spawn_audit_trail timing verification (60s threshold), A3 spawn_audit_trail schema field (spawned_at, spawn_tool, parent_trace_id, hex_entropy_source) for real sub-agent evidence. C1 version bump, C2 name sync, C3 evolution_history append. All additive, zero breaking changes."
  - version: "5.5.0"
    date: "2026-05-19"
    note: "BREAKING:agent_id_self_report_removed. MAJOR evolution v5.4.4 -> v5.5.0. 9 items (4A + 5C). Root cause fix for cycle 15-17 cat-and-mouse evasion: host AI loses self-report agent_id capability. A1 agent_id server-side generation via NEW agent_id_generator.py (secrets.token_hex(4), PRNG entropy controlled by Engine, written to _index.json::dispatch_plan[node].expected_agent_id before dispatch). A2 --agent_id CLI param removed from agent_write_node_cache.py (auto-reads from _index.json, deprecated flag ignored). A3 dispatch_audit.py simplified to integrity-only checking (removed fake_hex_trivial/invalid/duplicate/low_entropy + suspicious_sub_agent, single integrity_violation category: cache.agent_id == expected_agent_id). A4 spawn_audit_trail timestamp anti-forgery via dispatch_records (generated_at written by agent_id_generator.py, spawned_at > generated_at ordering invariant verified by dispatch_audit). C1 version bump, C2 name sync, C3 evolution_history append (BREAKING marker), C4 governance_hash TRI-SYNC recompute, C5 agent_engine json_schema update. BREAKING: not backward compatible with v5.4.x self-report agent_id cache schema. ThreeDimTest: C=4.714 I=4.923 D=4.850 weighted=4.849 (Grade S)."
  - version: "5.6.0"
    date: "2026-05-20"
    note: "Fallback tightening with spawn_failure_evidence. MINOR evolution v5.5.0 -> v5.6.0. 8 items (4A + 4C). Evidence: cycle 19 ObservabilityStep used inline_fallback with vague fallback_reason — cannot distinguish real spawn failure from never-attempted spawn. A1 spawn_failure_evidence schema REQUIRED for inline_fallback (attempted_spawn_tool, attempted_at > generated_at, failure_signal enum, failure_detail structured). A2 no-evidence fallback = FAIL with SPAWN_NOT_ATTEMPTED. A3 dispatch_audit.py restored legit/illegitimate fallback classification. A4 agent_id_generator.py prefix alignment with capability_probe.recommended. C1 version bump, C2 name sync, C3 evolution_history append, C4 governance_hash TRI-SYNC. 0 breaking changes."
  - version: "5.6.1"
    date: "2026-05-26"
    note: "Reliability patch via Creator Evolve pipeline (cache/32). PATCH evolution v5.6.0 -> v5.6.1. 3 items (1A + 1B + 1C-implicit): A2 transient cache retry for node_engine (retry with exponential backoff on transient file system errors during cache read/write), A3 degraded_reason enum (structured enum replacing free-text degraded_reason in NodeVerify: TOOL_CALL_DEFICIT, PARTIAL_OUTPUT, TIMEOUT, TRANSIENT_FAILURE), B1 writeCache read-back verification in agent_engine (atomic write followed by read-back comparison to detect silent write corruption). 0 breaking changes. ThreeDimTest: C=4.857 I=5.000 D=4.700 weighted=4.874 (Grade S)."
  - version: "5.9.0"
    date: "2026-05-27"
    note: "Dispatch plan generation vulnerability fix via Creator Evolve pipeline (cache/40). MINOR evolution v5.6.1 -> v5.7.0. 3 A-level + 1 B-level + C-sync items. A1 NEW python_tools/generate_dispatch_plan.py deterministic tool. A2 node_engine.aisop.json programExec.step2 rewritten. A3 dispatch_audit.py --pre-execution generation-stage gate. B1 version bump. 0 breaking changes. ThreeDimTest 4.874 (Grade S)."
  - version: "5.10.0"
    date: "2026-05-28"
    note: "HMAC Phase 2 + NIST CAISI + compliance hardening via Creator Evolve pipeline (cache/45). MINOR evolution v5.9.0 -> v5.10.0. A1 HMAC Phase 2 runtime active (signing/verification when key present). B1 NIST CAISI three-pillar alignment propagated to all engines. B2 HMAC delegation contract formalized. B3 EU CRA SRP registration readiness. B4 Art.50 CoP tracking. B5 OTel Logs API dual-emit preparation. C1-C3 governance sync + summary trimming. 0 breaking changes."
  - version: "5.12.0"
    date: "2026-05-29"
    note: "User_gate enforcement remediation via Creator Evolve pipeline (cache/47). MINOR evolution v5.11.0 -> v5.12.0 FINALIZED. G1 auto-detect gates from node definition text (user_gate_audit.py enhancement). G3 multi-file node parsing for gate detection across delegated modules. G4 effective coerce to FAIL+halt (not WAITING_USER) when sovereignty bypass detected. HMAC_CONSTANT_TIME MUST enforcement upgraded from advisory per CVE-2026-21713. HMAC key rotation 4-step procedure documented. MCP 2026 roadmap tracking (Server Cards, Streamable HTTP, DPoP, Tasks). B3 sovereignty gate precedence retained. ThreeDimTest: C=4.929 I=4.923 D=5.000 weighted=4.947 Grade S. 0 breaking changes."
  - version: "5.13.0"
    date: "2026-05-29"
    note: "nodes_in_path completeness + NODE SUMMARY user language via Creator Evolve pipeline (cache/48). MINOR evolution v5.12.0 -> v5.13.0 FINALIZED. A1 dispatch_audit.py nodes_in_path completeness verification (independent mermaid reparse, QI-2, gate omission CRITICAL, decision branch exempt). A2 node_engine programExec step2 wire completeness check. B1 NODE SUMMARY forced user language. C1-C5 version sync, name sync, evolution_history, governance_hash TRI-SYNC, summary. 0 breaking changes. ThreeDimTest: C=5.000 I=4.923 D=4.950 weighted=4.950 Grade S."
  - version: "5.13.1"
    date: "2026-05-29"
    note: "Branch-aware completeness fix via Creator Evolve pipeline (cache/49). PATCH evolution v5.13.0 -> v5.13.1. A1 dispatch_audit.py branch-aware completeness verification (walked branches checked, unwalked branches exempt, edge label regex fix — prevents false node matches from Pass/Fail/Red/Yellow edge labels). A2 node_engine step2 wiring recalibrated for branch-aware semantics. C-auto version bump, name sync, governance_hash TRI-SYNC deferred to ReviewFinalize. 0 breaking changes."
  - version: "5.13.2"
    date: "2026-05-29"
    note: "Python subprocess prefix alignment via Creator Evolve pipeline (cache/50) FINALIZED. PATCH evolution v5.13.1 -> v5.13.2. C-PREFIX-1/C-PREFIX-2: agent_engine writeCache step2/step3 python subprocess call prefix aligned from bare 'python' to '<python> -X utf8', consistent with node_engine/normal_engine convention (prevents Windows non-ASCII encoding issues per PEP 686). C-auto version bump, name sync, evolution_history append, governance_hash TRI-SYNC. ThreeDimTest: C=4.930 I=4.960 D=5.000 weighted=4.960 Grade S. 0 breaking changes."
  - version: "5.14.0"
    date: "2026-05-29"
    note: "X3 sovereignty enforcement documentation formalization via Creator Evolve pipeline (cache/51) FINALIZED. MINOR evolution v5.13.2 -> v5.14.0. C1: Fixed agent_engine description — G4 FAIL+halt narrative corrected to X3 WAITING_USER rewrite via user_gate_audit.py --enforce (FLAW-A resets _index, FLAW-B reconstructs steps_done). C2: Updated node_engine e2f label to X3 semantics. C3: Replaced 'pending v5.14.0 bump' version placeholders. C4: Updated summary fields across all 4 modules. C5: Version bump 5.13.2 -> 5.14.0 + name sync. C8: Industry research gap report — Layer-1 vs Layer-2 enforcement comparison (4 gaps, 4 backlog items). X3 execution logic was manually implemented between v5.13.1->v5.13.2; this version formalizes documentation. No execution body changes — step3 --enforce, e2f --enforce, FLAW-A/B behavior, NON-SKIPPABLE all preserved verbatim. ThreeDimTest: C=4.900 I=5.000 D=5.000 weighted=4.975 Grade S. 0 breaking changes."
  - version: "5.14.1"
    date: "2026-05-29"
    note: "PATCH evolution v5.14.0 -> v5.14.1 via Creator Evolve pipeline (cache/52) FINALIZED. 3 bug fixes + 5 C-auto items. A1 node_engine programExec step5 _index.json merge via agent_update_index.py (prevents loss of user_gates_presented during concurrent writes). A2 node_engine programExec step4 language fallback chain changed to conversation language detection before English fallback. A3 agent_engine init step6 RESUME_MODE completion mandate — after RESUME_MODE execution, full review->writeCache pipeline MUST execute including step2 agent_update_index.py and step3 user_gate_audit.py --enforce (prevents bypass of nodes_status update and sovereignty enforcement on resumed nodes). Guardrails verified: writeCache.step3 and X3 sovereignty enforcement NOT MODIFIED. ThreeDimTest: C=4.930 I=5.000 D=4.950 weighted=4.97 Grade S. 0 breaking changes."
  - version: "5.14.2"
    date: "2026-05-30"
    note: "PATCH (documentation only) v5.14.1 -> v5.14.2 via Creator Evolve pipeline (cache/53) FINALIZED. A1: added 'Known Limitations (v5.14.2)' section to AIAP.md documenting underlying-runtime (Claude Code/Node/V8) long-session JS heap OOM — symptom: single long-running node session accumulation -> child process exit 0xC0000409 (abort/heap OOM), crash node drifts; root cause: upstream Claude Code not-planned (GitHub #25926 mutableMessages monotonic growth never released + #11155 tool-output whole-session residency), explicitly NOT an engine defect; diagnosis: child NODE_OPTIONS += --heapsnapshot-near-heap-limit=2 --trace-gc to capture pre-crash heap; mitigation: --max-old-space-size headroom + process boundary (existing soulacp retry / proactive session rotation / heavy-node segmentation as root-fix), with note that /compact and sub-agent do NOT solve (same process). C1-C4 auto: version bump 5.14.1->5.14.2 across 4 .aisop.json + AIAP.md frontmatter + agent_card.json + quality_baseline.json, name/summary/description current-version sync (historical changelog lineage preserved), evolution_history append, governance_hash TRI-SYNC recompute. Doc-only invariant machine-verified: node/agent/normal engine function bodies byte-identical to v5.14.1 snapshot (ZERO execution-logic edits); X3 writeCache.step3 --enforce, node_engine step5 _index merge (agent_update_index.py / user_gates_presented / last_completed), e2f / FLAW-A/B / WAITING_USER / NON-SKIPPABLE all preserved verbatim; main.execute.step3 prose corrected to match existing prepare_cache.py _resolve_engine_version runtime behavior (doc-to-code alignment, no logic change). ThreeDimTest (Generate2 full-scope fresh retest): C=4.5 I=4.577 D=4.5 weighted=4.531; final_adjusted post-Finalize D6/D10 reconciliation (version_sync 4.5->5.0, description 4.5->5.0): D_avg 4.5->4.8, final_adjusted=4.621 Grade S. Stage weighted-delta vs v5.14.1 (4.97) is a fresh-retest scoring-method artifact (deferred-neutral 4.5 per P23 + full re-score), NOT an execution-path regression (0 path-coverage drop, 0 dead nodes, 0 changed execution steps). 0 breaking changes."
  - version: "5.15.0"
    date: "2026-05-30"
    note: "MINOR evolution v5.14.2 -> v5.15.0 via Creator Evolve pipeline (cache/57) — DRAFT generated by Generate1 (finalized by ReviewFinalize). B1 (LEVEL_B, user-authorized turn 57): agent-mode last_completed_node advancement. ROOT CAUSE (empirically verified — live _index of this run had last_completed_node stuck at ProtocolAlign while the pipeline was at EvolveStep): agent-mode direct-write (v5.6.1) bypasses the last_completed auto-advance that agent_write_node_cache.py performs only for inline nodes; agent_update_index.py is a pure merge with no auto-advance, so an agent-heavy pipeline (creator: 18 agent + 2 inline) leaves _index.last_completed_node stuck at the last inline node for the entire run (crash-recovery still works via current_node + nodes_status). FIX (single change, agent_engine.writeCache.step2 only): when the node is terminal/completed (status in PASS/FAIL/PARTIAL/DEGRADED/ABORTED; EXCLUDE pause states WAITING_USER/MESSAGE_PENDING), merge last_completed_node={YOUR_NODE} into the EXISTING agent_update_index.py --updates call alongside nodes_status (same single write, NO new tool call). X3 PAIRING (no code change): user_gate_audit.py FLAW-A un-advance branch — previously dead for agent gate nodes because last_completed never advanced — now activates; on gate bypass with last_completed_node==forced node, FLAW-A un-advances to the prior node automatically. This cycle EXPLICITLY AUTHORIZES writing _index.last_completed_node (reversing the prior doc-only-PATCH 'do not touch last_completed' constraint); presented + confirmed at EvolveStep sovereignty gate (user reply 'all', Axiom 0 satisfied). C-auto: C1 version bump 5.14.2->5.15.0 across 4 .aisop.json + AIAP.md frontmatter + agent_card.json + quality_baseline.json (protocol_config.json not present — skipped); C2 name field version sync (4 modules); C3 evolution_history + changelog append (this entry); C4 governance_hash recompute + TRI-SYNC at ReviewFinalize; C5 AIAP.md parallel-wave concurrent last_completed_node single-value caveat documented (documentation only, no concurrency-model change). HARD CONSTRAINTS (preserved): (1) ONLY agent_engine.writeCache.step2 changed — no node_engine / normal_engine step change, no X3 writeCache.step3 / node_engine e2f --enforce change, no user_gate_audit.py / agent_update_index.py CODE change. (2) Parallel-wave concurrency: caveat documented only, concurrency model unchanged. (3) Version per evolution_rules LEVEL_C auto. Backward compatible (additive single _index key; old caches readable). 0 breaking changes. NOTE: scores below are pending ReviewFinalize re-measure."

  - version: "5.16.0"
    date: "2026-05-30"
    note: "MINOR evolution v5.15.0 -> v5.16.0 via Creator Evolve pipeline (cache/58) — DRAFT generated by Generate1 (finalized by ReviewFinalize). B1 (LEVEL_B, user-authorized): normal_engine sovereignty gate enforcement. user_gate_audit.py --enforce added to normal_engine writeCache.step3, matching agent_engine writeCache.step3 and node_engine programExec.step3.e2f sovereignty enforcement pattern. Programs with loading_mode=normal now have Axiom 0 Layer-1 backstop parity. C-auto: C1 agent_engine writeCache field count harmonized (step1 says 15, step1_5 now also says 15), C2 main.aisop.json system_prompt placeholder '{system_prompt}' replaced with actual content, C3 normal_engine Error fields aligned to error_taxonomy categories, C4 agent_engine description trimmed to current-version-only (changelog history moved to AIAP.md), C5 AIAP.md benchmark note updated from v5.14.1 to v5.15.0 reference, C6 version sync across all 4 modules + governance files, C7 governance hash intermediate recompute. 0 breaking changes."

  - version: "5.17.0"
    date: "2026-05-31"
    note: "MINOR evolution v5.16.0 -> v5.17.0 via Creator Evolve pipeline (cache/62) — DRAFT generated by Generate1. Sovereignty Bug Protocol. A1 sovereignty_bug_protocol shared section (main.aisop.json + agent_engine.aisop.json). B1 RULES.sovereignty_bug execution rule in agent_engine. C1-C6 version bump + metadata sync. Reference: plan20/34_permissive_sovereignty_gate_framework.md. 0 breaking changes."

---

## Governance Declaration

SoulBot Execute Engine is the core execution infrastructure of the SoulBot AIAP runtime.
It receives user intent from agent.py, routes to the appropriate AIAP program, selects
the execution engine (node or normal), and orchestrates node-by-node execution with
full observability, fault tolerance, and interrupt handling.

This program follows the AIAP V1.0.0 protocol, with Axiom 0 (Human Sovereignty and Wellbeing)
as its immutable axiom. All sys.io.confirm/input/select calls are forced-blocking per AISOP §6.2 —
they cannot be bypassed, auto-approved, or delegated to AI.

## Architecture Overview

### Execution Flow

```
EXECUTE_ENGINE=true:
  agent.py → main.aisop.json (Engine Router)
    → match (identify AIAP package)
    → execute (cache + context + select engine by loading_mode)
    → engineExec (monitor + NodeSummary + ExecutionSummary)
      ↓ loading_mode
    ┌────────┴─────────┐
    ↓                  ↓
  node_engine        normal_engine
  (Sub Agent/node)   (inline/node)
  default=agent      default=inline
       ↓
  agent_engine.aisop.json
  (init→execute→review→writeCache)
```

### Module Architecture (Pattern B+)

| Module | File | Nodes | Mode | Purpose |
|--------|------|-------|------|---------|
| **Engine Router** | main.aisop.json | 5 | sequential | Route + engine selection + monitoring |
| **Node Engine** | node_engine.aisop.json | 2 | hybrid | Sub Agent dispatch per node |
| **Normal Engine** | normal_engine.aisop.json | 2 | sequential | Inline execution per node |
| **Agent Engine** | agent_engine.aisop.json | 5 | sequential | Sub Agent execution contract |

### Key Mechanisms

| Mechanism | Location | Description |
|-----------|----------|-------------|
| **Crash Recovery** | node_engine, normal_engine | `last_completed_node` atomic marker. On re-entry, skip completed nodes. |
| **Circuit Breaker** | node_engine, normal_engine | 3-state: closed → open (3 failures) → half-open (30s timeout, 1 test dispatch) |
| **Parallel Dispatch** | node_engine | Analyze mermaid graph for independent branches. Dispatch parallel waves. |
| **NodeVerify** | node_engine, normal_engine | Lightweight audit: tool_calls > 0 for 2+ step nodes. FAIL → retry → DEGRADED. |
| **Decision Node Gate** | node_engine, normal_engine | Read `route` field from cache for mermaid diamond nodes. Branch routing. |
| **WAITING_USER Relay** | main (M1) | Detect WAITING_USER status → present to user → resume with USER_ANSWER |
| **MESSAGE_PENDING Relay** | main (M1) | Detect MESSAGE_PENDING → forward to user → immediate resume |
| **sys.* Handling** | agent_engine, normal_engine | 24 calls, 8 namespaces. Forced blocking for sys.io.confirm/input/select (Axiom 0). |
| **trace_id / span_id** | main, agent_engine | UUID v4 trace_id in Router, span_id per node in Sub Agent cache. |
| **Bootstrap Validation** | agent_engine (A8) | Validate TARGET path, CONTEXT_DIR, YOUR_NODE, AIAP_NAME before execution. |

### OpenTelemetry Integration (v5.3.0 A1)

All 4 modules declare `opentelemetry-sdk >= 1.20.0` as a capability dependency. Trace context
propagation flows from `_index.json::trace_id` through all engine modules:

| Component | OTel Integration | Span Naming |
|-----------|-----------------|-------------|
| **Engine Router** | Root span creation, trace context source | `soulbot_execute_engine.main.{function}` |
| **Node Engine** | Child spans per node + 5 SpanEvents | `soulbot_execute_engine.node.{node_name}` |
| **Normal Engine** | Child spans per inline node | `soulbot_execute_engine.normal.{node_name}` |
| **Agent Engine** | Sub Agent spans with cache span_id | `soulbot_execute_engine.agent.{YOUR_NODE}` |

SpanEvents dispatched by Node Engine (A2):
- `node_started` — node begins execution
- `node_completed` — node completes successfully (PASS/PARTIAL)
- `node_failed` — node fails (FAIL/DEGRADED)
- `circuit_breaker_tripped` — circuit breaker state transition
- `decision_gate_routed` — Decision Node branch routing

Fallback: structured JSON log when OTel SDK unavailable.

### OWASP ASI Threat Mapping (v5.3.0 B1)

Threat surface mapped to OWASP Agentic Security Initiative (ASI) ASI01-ASI10:

| ASI ID | Threat | Mitigation | Status |
|--------|--------|-----------|--------|
| ASI01 | Goal Drift | `governance_hash` comparison at execution start | GREEN |
| ASI02 | Excessive Authority | Workspace-scoped file_system, no shell=True | GREEN |
| ASI03 | Knowledge Poisoning | Bootstrap validation (A8), path safety guards | GREEN |
| ASI04 | Excessive Agency | Axiom 0 forced-blocking for user decisions | GREEN |
| ASI05 | Improper Output | USER_MESSAGE handling, output mode enforcement | GREEN |
| ASI06 | Cache Integrity | Cache HMAC verification on _index.json and node caches | YELLOW->GREEN |
| ASI07 | IPC Signatures | Inter-agent cache IPC signatures via span_id correlation | YELLOW->GREEN |
| ASI08 | Logging/Monitoring | trace_id + span_id + OTel SDK observability | GREEN |
| ASI09 | Supply Chain | Protocol version check, min_protocol_version enforcement | GREEN |
| ASI10 | Runtime Drift | Version field comparison across modules at bootstrap | YELLOW->GREEN |

### EU AI Act Art.50 Transparency (Compliance Advisory)

| Field | Value |
|-------|-------|
| **Applicability** | Potentially applicable — SoulBot Execute Engine orchestrates AI agent interactions with users via sys.io.confirm/input/select and USER_MESSAGE forwarding |
| **Disclosure Status** | PENDING — applicability analysis deferred from v5.3.0 (ref: quality_baseline v5_3_0_deferred_items C3) |
| **Enforcement Date** | 2026-08-02 (EU AI Act Art.50 transparency obligations) |
| **Action Required** | Complete applicability analysis before enforcement date. If applicable: add user-facing disclosure that responses are AI-generated, document AI system capabilities and limitations, ensure human oversight mechanisms (Axiom 0 sys.io.confirm already provides this) |
| **Reference** | https://artificialintelligenceact.eu/article/50/ |
| **Current Mitigations** | Axiom 0 forced-blocking for all user decisions (sys.io.confirm/input/select), output_mode prefix, trust_level=3 with constrained permissions |

### sys.* Support (AISOP Protocol §6)

| Blocking Type | Calls | Count |
|---------------|-------|-------|
| **Forced blocking** | sys.io.confirm, sys.io.input, sys.io.select | 3 |
| **Non-blocking interrupt** | sys.io.notify | 1 |
| **Blocking** | sys.run, sys.run.timeout, sys.io.read, sys.io.write, sys.code.exec, sys.code.eval, sys.llm, sys.llm.json, sys.llm.classify, sys.event.wait | 10 |
| **Non-blocking** | sys.io.print, sys.run.bg, sys.event.emit, sys.state.get, sys.state.set, sys.state.save, sys.state.load, sys.security.audit, sys.security.redact | 10 |
| **Total** | 8 namespaces | **24** |

### Sovereignty Bug Protocol (v5.17.0)

The Sovereignty Bug Protocol formalizes how the agent handles bugs discovered in the sovereignty toolset during execution. It implements the permissive sovereignty gate framework from plan20/34.

| Concept | Description |
|---------|-------------|
| **Red Line** | Self-modifying sovereignty toolset code without human approval = Axiom 0 violation (absolutely prohibited) |
| **Gate** | Everything else goes through user gate (human approves) |
| **Honest Boundary** | Local agent physically CAN modify; this protocol makes unauthorized modification have no excuse and always be detectable |

**Sovereignty Toolset Members:**
- `python_tools/user_gate_audit.py`
- `python_tools/agent_update_index.py` (FLAW-A un-advance branch)
- `python_tools/dispatch_audit.py`
- `python_tools/snapshot_audit.py`
- `sovereignty_bug_protocol` definition itself (self-referential closure)

**Bug Classification (3-tier):**

| Tier | Criteria | Response | Fix Assertion |
|------|----------|----------|---------------|
| **Critical** | Sovereignty bypass, gate removal, fix requires self-modification | Immediate WAITING_USER | REQUEST_IMMEDIATE |
| **Medium** | Safe to execute, no sovereignty impact, fix does not touch toolset | Continue + report in cache | SUGGEST_FIX |
| **Light** | Cosmetic/doc, zero danger | Continue + summary | ASK_IF_FIX |

**Separation of Powers:** Agent discovers + classifies + proposes (executive). Human approves (legislative). Exposure chain records (judicial).

**Exposure Chain:** Append-only sovereignty_log in `_index.json` with SHA-256 prev_hash chain. Integrity invariant: any TOOL_MODIFY must have a preceding HUMAN_APPROVAL with matching diff_hash.

### Known Limitations (v5.17.0)

> **Scope of this entry:** documentation/observability only. This records a known upstream runtime constraint; it does NOT describe an engine defect and does NOT change any engine execution logic.

**Underlying-runtime long-session JS heap OOM (Claude Code / Node / V8).**

| Aspect | Detail |
|--------|--------|
| **Symptom** | During a single long-running node session, accumulated in-memory state causes the underlying Claude Code child process (Node/V8) to terminate with exit code `0xC0000409` (abort / heap OOM). The crashing node drifts (it is not a fixed node) because the crash is triggered by cumulative heap pressure rather than by any specific node's logic. |
| **Root cause** | Upstream Claude Code behavior, currently marked *not planned* by the upstream project: (1) GitHub issue #25926 — the conversation message buffer (`mutableMessages`) grows monotonically and is never released; (2) GitHub issue #11155 — tool outputs remain resident for the whole session. This is an underlying-runtime memory-retention characteristic, **NOT a defect in this engine** (main/node/agent/normal engines). |
| **Diagnosis** | Set child-process `NODE_OPTIONS` to include `--heapsnapshot-near-heap-limit=2 --trace-gc` to capture a heap snapshot and GC trace immediately before the crash, confirming heap exhaustion as the cause. |
| **Mitigation** | (1) Add heap headroom via `--max-old-space-size`; (2) enforce a process boundary so the orchestrator survives a child crash — the existing `soulacp` retry already provides a fallback; (3) proactive session rotation; (4) splitting heavy nodes into smaller segments is the root-fix direction. Note: in-session `/compact` and sub-agent dispatch do **not** resolve this because they run inside the same process and do not free the underlying-runtime heap. |
| **Status** | Known upstream limitation, tracked for observability. No engine-side code change is warranted; resilience is provided at the process boundary (retry + rotation + node segmentation). |

**Parallel-wave concurrent `last_completed_node` write (v5.15.0 B1 caveat).**

| Aspect | Detail |
|--------|--------|
| **Symptom** | As of v5.15.0, `agent_engine.writeCache.step2` advances `_index.last_completed_node = {YOUR_NODE}` for every terminal agent node. `last_completed_node` is a single-valued scalar field. Under **parallel-wave dispatch** (Node Engine fanning out independent mermaid branches concurrently), two or more sub-agents in the same wave may write `last_completed_node` at overlapping times, producing a non-deterministic last-writer-wins value — the field may reflect any one of the concurrently-completed nodes rather than a well-defined cursor. |
| **Scope** | Affects ONLY parallel-wave execution. **Linear (sequential) pipelines — the default and the case this fix targets — never trigger it**, because exactly one node writes at a time. Crash-recovery does NOT depend on `last_completed_node` precision (it uses `current_node` + `nodes_status`), so a stale/raced value is observability noise, not a correctness hazard. |
| **Decision** | Deliberately NOT addressed in v5.15.0. Making `last_completed_node` correct under concurrency would require a different data shape (e.g. per-branch cursors or a completed-set) and a concurrency-model change, which is out of scope for this fix. Industry durable-execution engines (Temporal/LangGraph/DBOS) similarly require a reliably-advancing scalar cursor for the linear case and model concurrent completion separately. |
| **Status** | Documented caveat, tracked for a future concurrency-model evolution. No code change this cycle. |

## Usage

### Entry File

`main.aisop.json` — loaded by agent.py when `EXECUTE_ENGINE=true`. Contains Engine Router with intent matching, engine selection, and execution orchestration.

### Tool Requirements

| Tool | Required | Purpose |
|------|----------|---------|
| file_system | Yes | Read target AIAP, write execution cache, write node caches |

### Executor Shim Note

The `python_tools/` directory (containing `prepare_cache.py` and related helpers) is declared
via the top-level `executor_shim: true` field. Executor shims are **NOT registered AIAP tool
packages** (they do not follow AIAP Pattern G — no `tool.json`, no `tool_dirs` registration).
They are executor-internal helpers invoked by the runtime (e.g. agent.py's Python fast path
or the AISOP Bash CLI fallback) to implement atomic cache lifecycle. Downstream consumers of
this AIAP package (discovery, registry, governance) MUST treat `python_tools/` as executor
implementation detail, not as a discoverable tool. The `tool_dirs: []` declaration makes this
explicit: no embedded tool packages, all executor shims governed by `executor_shim: true`.

### Prerequisites

- `EXECUTE_ENGINE=true` in `.env` or environment
- Target AIAP packages exist in `aiap_store/` or `aiap/` with valid `main.aisop.json`
- Execution cache directory writable

## Example Interactions

**Scenario 1: Chat (Normal Engine)**
- User: "你好"
- Router: match → soulbot_chat [loading_mode=normal]
- Engine: normal_engine → inline execution → 8 nodes fast path → response

**Scenario 2: Creative (Normal Engine)**
- User: "给我讲个笑话"
- Router: match → soulbot_chat [loading_mode=normal]
- Engine: normal_engine → inline execution → 11 nodes full NLU path → joke response

**Scenario 3: Evolution (Node Engine)**
- User: "进化 soulbot_chat"
- Router: match → soulbot_creator_evolution [loading_mode=node]
- Engine: node_engine → Sub Agent per node → 21 pipeline nodes → evolved program

**Scenario 4: sys.io.confirm Interrupt**
- Sub Agent encounters sys.io.confirm step → writes WAITING_USER to cache
- node_engine → returns to Router → M1 relay → presents question to user
- User responds → Router re-dispatches with RESUME_MODE + USER_ANSWER
- Sub Agent reads steps_done → skips completed → continues from interrupt point

## Applicability

**Applicable**: Executing any AIAP program through the SoulBot runtime when EXECUTE_ENGINE=true. Supports both node mode (Sub Agent isolation, ~95% execution depth) and normal mode (inline, ~60-75% depth, faster).

**Not applicable**: EXECUTE_ENGINE=false (uses soulbot_router.aisop.json lightweight route). Direct CLI execution without agent.py. Non-AISOP format programs.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
