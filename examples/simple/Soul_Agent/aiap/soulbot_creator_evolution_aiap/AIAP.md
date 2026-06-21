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
name: aiap_creator
version: "2.47.0"
pattern: D
flow_format: "mermaid"
summary: "AIAP Creator — 18-stage pipeline for creating, evolving, validating, simulating, and managing AIAP programs. 15 modules, 213 nodes, 1167 scenarios (A-AJ). Pattern D, Grade S (4.987). Supports Create/Evolve/Modify/Validate/Simulate/Compare/Discover/Deprecate/Export/Import/Explain/Package/Convert workflows. ThreeDimTest quality scoring, governance hash canonical v1.0 with QUAD-SYNC verification. v2.39.0: snapshot-timing spec fix — (A1 core) the snapshot_build.py + SNAPSHOT AUDIT block was moved OUT of review.aisop.json Finalize.step2 into a NEW finishing step5_5 that runs AFTER step3 governance_hash TRI-SYNC and AFTER step5 identity, so snapshot == final disk state (cache/100 root cause: snapshot was sealed before later governance writes drifted it stale); step2 keeps only NIHIL cleanup + quality-baseline persistence + history archival (snapshot inputs). (A2 self-heal) a terminal re-audit is appended as ReviewFinalize's absolute-last action — on residual hash_mismatch it rebuilds the snapshot (same --pipeline_run_id) + re-emits meta + re-audits, HARD_FAIL halt on a 2nd failure. (A3 reconcile) main.aisop.json ReviewFinalize.step7_5 reworded to point to review Finalize step5_5 as the SOLE snapshot execution point, removing the main/review cross-spec ordering contradiction. (C-D) summary/score baseline refreshed to current quality_baseline (4.987). Tools snapshot_build.py/snapshot_audit.py/governance_hash.py UNCHANGED (orchestration-order-only fix); absolute-path {DIR_OF_PIPELINE}/tool_dirs invocation, MANDATORY BLOCKING exit1 halt and C-1/C-2 HARD_FAIL rules preserved. governance_hash recomputed canonical v1.0 + QUAD-SYNC verified by tool_dirs/governance_hash.py (SOLE AUTHORITY)."
tools:
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: false
  - name: web_search
    required: false
    fallback: "degrade"
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
  - name: web_fetch
    required: false
    fallback: "degrade"
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
modules:
  - id: aiap_creator.main
    file: main.aisop.json
    nodes: 33
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: aiap_creator.generate
    file: generate.aisop.json
    nodes: 26
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: aiap_creator.research
    file: research.aisop.json
    nodes: 16
    critical: false
    idempotent: true
    side_effects: []
  - id: aiap_creator.modify
    file: modify.aisop.json
    nodes: 10
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: aiap_creator.review
    file: review.aisop.json
    nodes: 12
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: aiap_creator.simulate
    file: simulate.aisop.json
    nodes: 14
    critical: false
    idempotent: true
    side_effects: []
  - id: aiap_creator.observability
    file: observability.aisop.json
    nodes: 10
    critical: false
    idempotent: true
    side_effects: []
  - id: aiap_creator.nihil_density
    file: nihil_density.aisop.json
    nodes: 13
    critical: false
    idempotent: true
    side_effects: [file_write]
  - id: aiap_creator.convert
    file: convert.aisop.json
    nodes: 17
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: aiap_creator.advisor
    file: advisor.aisop.json
    nodes: 62
    critical: false
    idempotent: false
    side_effects: [file_write]
  - id: aiap.standard.core
    file: AIAP_Standard.core.aisop.json
    nodes: 0
    critical: true
    idempotent: true
    side_effects: []
  - id: aiap.standard.security
    file: AIAP_Standard.security.aisop.json
    nodes: 0
    critical: true
    idempotent: true
    side_effects: []
  - id: aiap.standard.performance
    file: AIAP_Standard.performance.aisop.json
    nodes: 0
    critical: false
    idempotent: true
    side_effects: []
  - id: aiap.standard.ecosystem
    file: AIAP_Standard.ecosystem.aisop.json
    nodes: 0
    critical: false
    idempotent: true
    side_effects: []
  - id: aiap.standard.runtime_extensions
    file: AIAP_Standard.runtime_extensions.aisop.json
    nodes: 0
    critical: true
    idempotent: true
    side_effects: []

# Optional Fields
governance_hash: "38b6acc70ea48096d90d2bd1244cd73179ab812ba7ccab24cd40b54bceb0ed78"
governance_hash_canonical_version: "1.0"
quality:
  weighted_score: 4.987
  grade: S
  last_pipeline: "fbcbcf9e-25df-434d-a09f-94bfb3be8c08"
  weighted_score_note: "v2.39.0 changed review.aisop.json (Finalize snapshot block moved to finishing step5_5 + terminal self-heal re-audit) + main.aisop.json (ReviewFinalize.step7_5 A3 reconcile + line18 summary C-D refresh); Generate2 partial re-score = 4.49 (changed_file_score). Whole-program weighted_score preserved from prior baseline (4.987) per SCORE SCOPE GUARD (generate2_score_scope=partial); pending full 18-module re-score."
  changed_file_score: 4.49
tags: [aiap, creator, pipeline, governance, meta, execution, strict_mode, density_metrics, strict_semantics, self_evolution, dsm, token_efficiency, evolution_fitness, attestation, insights, quality, threedimscore]
author: SoulBot.dev
license: Apache-2.0
copyright: "Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev"

# Security and Runtime Optional Fields
trust_level:
  level: 4
  justification: "AIAP Creator requires full read/write access to workspace for creating, evolving, and modifying AIAP programs. Network access needed for research stages (web_search, web_fetch)."
  constraints:
    - "file_system write scope limited to workspace_dir"
    - "network access limited to *.google.com and *.bing.com"
permissions:
  file_system:
    scope: "./"
    operations: ["read", "write"]
  network:
    allowed: true
    endpoints: ["*.google.com", "*.bing.com"]
runtime:
  timeout_seconds: 600
  max_retries: 3
  token_budget: 100000
  idempotent: false
  side_effects: [file_write]
capabilities:
  offered:
    - file_write
    - search
    - state_persistence
    - code_generation
  required:
    - file_read
ui:
  components:
    - type: dashboard
      title: "Pipeline Progress"
      data_source: pipeline_metadata
      refresh: "on_event"
    - type: form
      title: "Configuration"
      fields:
        - { name: quality_threshold, type: select, options: [strict, standard, relaxed], default: standard }
        - { name: research_mode, type: select, options: [structure, quality, compliance] }
    - type: visualization
      title: "Quality Trend"
      chart_type: line
      data_source: quality_baseline
  rendering: "mcp_apps_v1"

# Engineering Optional Fields
status: active
applicability_condition:
  triggers:
    - "user asks to create a new AIAP program"
    - "user asks to evolve an existing AIAP program"
    - "user asks to validate or simulate an AIAP program"
    - "user asks to modify a specific AIAP module"
    - "file with .aisop.json extension detected in workspace"
    - "user asks to discover or search for existing AIAP programs"
    - "user asks to deprecate or archive an AIAP program"
    - "user asks to export an AIAP program to SKILL.md format"
    - "user asks to import a SKILL.md file as an AIAP program"
    - "user asks to map AIAP tools to MCP protocol"
    - "user asks to discover programs from a remote registry"
    - "user asks to pack or package an AIAP program"
    - "user asks to unpack or verify a .aiap archive"
    - "user asks about UI components or dashboard for an AIAP program"
  preconditions:
    - "AIAP_Standard.core.aisop.json and extension files accessible in workspace"
    - "AIAP_Protocol.md accessible in workspace"
    - "workspace_dir writable"
  exclusions:
    - "input is not related to AIAP/AISOP format"
    - "user requests direct execution of an AIAP program (SoulBot executor responsibility)"
    - "target project uses non-AISOP format"
  confidence_threshold: 0.8
intent_examples:
  - "Create a personal expense tracker AIAP program"
  - "Evolve health_tracker from v1.1 to v1.2"
  - "Modify the search module of recipe_finder"
  - "Validate the code quality of expense_tracker"
  - "Simulate the execution paths of travel_planner"
  - "Search for any health-related AIAP programs"
  - "Deprecate old_tracker program"
  - "Export recipe_finder as SKILL.md"
  - "Import a SKILL.md file as an AIAP program"
  - "Map health_tracker tools to MCP protocol"
  - "Search remote registry for health-related AIAP programs"
  - "Package health_tracker as a .aiap file"
  - "Unpack and verify recipe_finder_v1.0.0.aiap"
  - "Add a Dashboard UI component to health_tracker"
discovery_keywords: [aiap, creator, aisop, pipeline, evolve, generate, validate, simulate, mcp, a2a, registry, agent_card, quality, governance, self_evolution, attestation, threedimscore, pattern_d]
dependencies:
  - file: AIAP_Protocol.md
    required: true
    description: "AIAP protocol specification used by ReadTemplate and research modules"
min_protocol_version: "AIAP V1.0.0"
identity:
  program_id: "aiap.dev/aiap_creator"
  publisher: "AIXP Labs AIXP.dev | SoulBot.dev"
  verified_on: "2026-06-17"
benchmark:
  threedimscore: 4.987
  grade: "S"
  simulation_coverage: "A(16)+B(13)+C(10)+D(10)+E(13)+F(8)+G(10)+H(14)+J(4)+K(7)+L(2)+M(22)+N(5)+O(6)+P(10)+Q(12)+R(404)+S(20)+T(19)+U(14)+V(18)+W(12)+X(21)+Y(11)+Z(16)+AA(22)+AB(29)+AC(37)+AD(40)+AE(35)+AF(38)+AG(40)+AH(38)+AI(45)+AJ(2) = 1023 scenarios"
  total_nodes: 213
  pass_rate: "997/997 (100%) — 0 RED, 10 YELLOW_accepted"
---

## Governance Declaration

AIAP Creator is the reference implementation and bootstrapping tool for the AIAP protocol.
This program follows the AIAP V1.0.0 protocol, with Axiom 0 (Human Sovereignty and Wellbeing)
as its immutable axiom, ensuring all outputs align with human sovereignty and benefit through
the three-domain governance chain (aisop.dev -> aiap.dev -> soulbot.dev).

AIAP Creator is itself an AIAP program (bootstrapping property) — it creates AIAP programs
while also following all AIAP rules itself.

## Feature Overview

AIAP Creator manages the complete lifecycle of AIAP programs through a 15-module (213 nodes), 18-stage pipeline (with automatic ProtocolAlign, NihilDensityStep, ReviewPresent + ReviewFinalize):

| Intent | Description | Pipeline |
|--------|-------------|----------|
| **Create** | Create a new AIAP program | Research -> Evolve -> Generate -> Modify -> QualityGate -> Validate -> Simulate -> PostSimulateGate -> Observability -> Review |
| **Evolve** | Evolve an existing AIAP program | Same as Create (with incremental diff analysis) |
| **Modify** | Modify a specific module | Research(quality) -> Modify -> Generate -> Validate -> [Simulate] -> [PostSimulateGate] -> Review |
| **Validate** | Validate code quality | ThreeDimTest 33+ checks (C1-C7, I1-I13, D1-D10) |
| **Simulate** | Simulate execution paths | Path tracing + scenario coverage (Categories A-X) |
| **Compare** | Compare two versions | Side-by-side diff display |
| **Discover** | Search existing programs | Workspace scan + federated registry query + semantic matching + related recommendations |
| **Deprecate** | Deprecate/archive a program | State transition + migration guide generation |
| **Export** | Export as SKILL.md | AIAP->SKILL.md field mapping + governance metadata preservation |
| **Import** | Import from SKILL.md | SKILL.md->AIAP skeleton generation + governance defaults |
| **Explain** | Explain AIAP concepts | Inline knowledge response |
| **Package** | Pack/unpack a program | advisor package sub-graph (pack -> .aiap / unpack -> verify) |
| **Convert** | Convert Mermaid↔JSON Flow format | Standalone bidirectional conversion (auto-direction, §4 topology transform, manifest, round-trip verification) |

### Module Architecture (Pattern D)

- **main.aisop.json** — Pipeline orchestrator (33 nodes, 2 sub_mermaid: main 15 + pipeline 18, hybrid normal/node mode)
- **protocol_config.json** — Protocol metadata config (execution, density metrics, strict semantics, self-evolution verification, DSM, token efficiency, volume monitor)
- **generate.aisop.json** — Generator (26 nodes, sub_mermaid architecture, MF1-MF38 cross-module audits)
- **research.aisop.json** — Shared research module (16 nodes, fractal_exempt, 3-mode reuse)
- **modify.aisop.json** — Modifier (10 nodes)
- **review.aisop.json** — Reviewer (12 nodes, +AutoFixEngine)
- **simulate.aisop.json** — Simulator (14 nodes, +YellowRemediationGuide, +ContractCheck, delegation parameter completeness)
- **observability.aisop.json** — Telemetry analysis (10 nodes)
- **advisor.aisop.json** — Advanced advisor (62 nodes, fractal_exempt, 9 sub-graphs)
- **convert.aisop.json** — Format converter (17 nodes, Mermaid↔JSON Flow bidirectional)
- **AIAP_Standard.core.aisop.json** — Core quality standard
- **AIAP_Standard.security.aisop.json** — Security extension
- **AIAP_Standard.ecosystem.aisop.json** — Ecosystem extension
- **AIAP_Standard.performance.aisop.json** — Performance extension
- **AIAP_Standard.runtime_extensions.aisop.json** — Runtime extensions

## Usage

### Entry File

`main.aisop.json` — AI Agent loads this file to start AIAP Creator. Main is the pipeline orchestrator containing intent routing and pipeline sequencing across 2 sub_mermaid graphs.

### Tool Requirements

| Tool | Required | Purpose |
|------|----------|---------|
| file_system | Yes | Read/write AISOP files |
| web_search | No | Search best practices during research stages |
| web_fetch | No | Deep web research |

### Prerequisites

- AIAP_Standard.core.aisop.json (and extension files) and AIAP_Protocol.md accessible in target directory
- AI Agent supports the file_system tool

## Example Interactions

**Scenario 1: Create a New Program**

- User: "Create a personal expense tracker AIAP program"
- Agent: Executes full Pipeline -> generates expense_tracker_aiap/ directory with AIAP.md + main + modules

**Scenario 2: Evolve an Existing Program**

- User: "Evolve health_tracker from v1.1 to v1.2 with monthly report functionality"
- Agent: Analyzes existing structure -> proposes LEVEL_A/B changes -> user confirms -> generates new version

**Scenario 3: Validate Quality**

- User: "Validate the code quality of recipe_finder"
- Agent: Runs ThreeDimTest -> outputs three-dimensional scores + traffic light classification

## Applicability

**Applicable**: Creating, evolving, modifying, validating, simulating, discovering, and deprecating AIAP programs; SKILL.md bidirectional conversion; MCP tool mapping; federated registry discovery (with MCP/A2A endpoint discovery); AIAP packaging/unpackaging (with tool_dirs directory and Code Trust Gate); UI component declaration generation; Pattern G embedded tool directory (tool_dirs) validation and auto-generation; Pattern E/F->G migration guidance; auto-fix proposal generation and application; YELLOW persistence tracking and remediation guide; automated quality verification (lint_report); MCP 2025 alignment (Tasks primitive, Elicitation, Extensions, AAIF governance); A2A v1.0 alignment (JSON-RPC/gRPC/REST multi-binding, JWS signed Agent Cards, Linux Foundation AAIF governance); Safety Card generation (risk_level, data_handling, limitations in agent_card.json); NIST AI Agent Standards Initiative reference
**Not applicable**: Direct execution of AIAP programs (that is the SoulBot executor's responsibility); non-AISOP format projects

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. <www.aiap.dev>
