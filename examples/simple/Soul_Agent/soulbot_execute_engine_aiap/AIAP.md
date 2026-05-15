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
version: "5.3.0"
pattern: B+
tool_dirs: []                # No tool packages embedded; python_tools/ is executor_shim only
executor_shim: true          # python_tools/ contains executor-internal shims (prepare_cache.py, etc.) — NOT registered tools per AIAP Pattern G. See 'executor_shim note' below.
flow_format: "mermaid"
summary: "SoulBot Execute Engine v5.3.0 — Router + dual Engine orchestration (node/normal) + Sub Agent contract + OpenTelemetry SDK integration + OWASP ASI threat mapping. 4 modules, 14 nodes. v5.3.0: A1 OpenTelemetry SDK (opentelemetry-sdk capability dependency, trace_id/span_id wired to OTel context propagation), A2 events[] + SpanEvent dispatcher (5 events in node_engine), B1 OWASP ASI01-ASI10 threat mapping (goal_hash drift, cache HMAC, IPC signatures, runtime drift), C1-C5 maintenance (version sync, ASSERT refresh, normal_engine orphan cleanup, python_tools snapshot scope, Error->on_error dual-key). Pattern B+."
governance_hash: "sha256:90bc4a0a8a0acbf8de06cd5b0b3d4c4d1b76191342d7ad99875147ff192015c9"
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
    description: "Node Engine — executes target AIAP node-by-node via Sub Agent dispatch (default agent). Crash recovery (last_completed_node), circuit breaker (3-state: closed/half-open/open), parallel dispatch (independent branch analysis), NodeVerify audit, Decision Node gate routing."
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
    description: "Agent Engine — Sub Agent execution contract. init (read target + context + ASSERT-driven selective read + SCOPE GUARD + RESUME_MODE) -> execute (execution loop with RULES.sys/user_input/user_message/on_error) -> review (tool call verification) -> writeCache (atomic write + steps_done/remaining). Identity-defined, Print-it commitment."

# Identity
program_id: dev.soulbot.execute_engine
identity:
  publisher: "AIXP Foundation AIXP.dev | SoulBot.dev"
  verified_on: "2026-04-06"
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
  threedimscore: 4.95
  grade: "S"
  cognitive: 4.93
  intrinsic: 4.92
  detail: 5.00
  simulation_coverage: "18/18 GREEN"
  total_nodes: 14
  pass_rate: "112/113 validation (99.1%)"
  nihil_density: "PASS (M-score 0.32 LOW)"
  note: "v5.3.0 ReviewFinalize final_adjusted_score 4.95 (Grade S). Previous baseline v5.0.0: 4.72 (Grade A). D6/D8/D10 reconciled post-Finalize to 5.0 (version sync + agent_card + quality_baseline governance hash tri-sync)."

# Quality
quality:
  weighted_score: 4.95
  grade: S
  last_pipeline: "Creator Evolve pipeline v5.3.0 (2026-05-13): observability-first evolution (OTel SDK + events[] + OWASP ASI threat mapping)"
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
