# AIAP Structural Specification

---

## Table of Contents

**Part I: Protocol Foundations**
1. [Protocol Declaration](#1-protocol-declaration)
2. [Core Definitions: AISOP = Language, AIAP = Rules](#2-core-definitions)
3. [AIAP.md Rules](#3-aiapmd-rules)

**Part II: Structural Specification**
4. [Node = Functional Responsibility](#4-node--functional-responsibility)
5. [Functional Node Count](#5-functional-node-count)
6. [Progressive Node Guidelines](#6-progressive-node-guidelines)
7. [fractal_exempt Annotation](#7-fractal_exempt-annotation)
8. [Pattern Selection](#8-pattern-selection)
9. [Pattern A-G Detailed Definitions](#9-pattern-a-g-detailed-definitions)
10. [main.aisop.json Rules](#10-mainaisopjson-rules)
11. [Functional Module Rules](#11-functional-module-rules)
12. [Independent Function Judgment](#12-independent-function-judgment)
13. [Sub_AIAP Split Rules](#13-sub_aiap-split-rules)
14. [Pattern Upgrade Convergence Handling](#14-pattern-upgrade-convergence-handling)
15. [Dual-Stream Rules](#15-dual-stream-rules)

**Part III: Security & Runtime**
16. [Trust Levels](#16-trust-levels)
17. [Permission Boundaries](#17-permission-boundaries)
18. [Integrity Verification](#18-integrity-verification)
19. [Runtime Constraints](#19-runtime-constraints)
20. [Error Handling Protocol](#20-error-handling-protocol)

**Part IV: Engineering Capabilities**
21. [Discovery Protocol](#21-discovery-protocol)
22. [Dependency Resolution](#22-dependency-resolution)
23. [Program Lifecycle](#23-program-lifecycle) — including [§23.5 Creator Pipeline Stages (Reference Implementation)](#235-creator-pipeline-stages-reference-implementation)
24. [Orchestration Patterns](#24-orchestration-patterns)

**Part V: Quality & Compatibility**
25. [Version Compatibility](#25-version-compatibility)
26. [Documentation Completeness Levels](#26-documentation-completeness-levels)

**Appendices**
- [Appendix A: PL24 Auto-Fix Protocol](#appendix-a-pl24-auto-fix-protocol)
- [Appendix B: PL25 License & Copyright Declaration](#appendix-b-pl25-license--copyright-declaration)
- [Appendix C: Category M — Tool Directory Simulation Scenarios](#appendix-c-category-m--tool-directory-simulation-scenarios-m1-m20)
- [Appendix D: NO_SELF_MODIFY Rule](#appendix-d-no_self_modify-rule)
- [Appendix E: INSIGHTS Mechanism — Optional Runtime Insight Recording](#appendix-e-insights-mechanism--optional-runtime-insight-recording)
- [Appendix F: Node Gate — Node-Level Execution Assertion](#appendix-f-node-gate--node-level-execution-assertion)
- [Appendix G: sys.* System Call Governance (AISOP V1.0.0)](#appendix-g-sys-system-call-governance-aisop-v100)

---

## Part I: Protocol Foundations

---

## 1. Protocol Declaration

```
AIAP Structural Specification
Protocol: AIAP V1.0.0
Authority: aiap.dev
Seed: aisop.dev
Axiom 0: Human Sovereignty and Wellbeing

This document defines the structural specification for AIAP programs, including:
- AIAP.md project declaration rules
- Pattern A-G fractal patterns
- Node counting and splitting strategies
- Security, runtime, discovery, dependency, lifecycle, and orchestration protocols

All AIAP programs must follow this specification.
AISOP file format (.aisop.json) as underlying language is not governed by this document.
```

### 1.1 Normative Artifacts and Their Roles

This protocol is documented in four artifact families. When they conflict, the order of precedence is declared below:

| Artifact | Role | Authority |
|----------|------|-----------|
| `AIAP_Protocol.md` (and `AIAP_Protocol_cn.md` translation) | Structural specification, rules, patterns, governance | **Authoritative** for program structure and rules |
| `standards/AIAP_Standard.*.aisop.json` | Formal rule definitions (MF / PL / I / C / D / K series codes) | **Authoritative** for machine-verifiable rule semantics |
| `aiap.proto` | Runtime data structures and governance service APIs | **Authoritative** for data object schemas and service contracts |
| `standards/` extension files (security / ecosystem / performance / runtime_extensions) | Domain-specific rule extensions | Authoritative within their domain |

**Conflict resolution**: when any artifact appears to contradict another, this Markdown specification is the tie-breaker for *rules and structure*; `aiap.proto` is the tie-breaker for *data shapes and API signatures*. Translations (e.g. `AIAP_Protocol_cn.md`) are always non-normative — the English text governs in case of divergence.

---

## 2. Core Definitions

> AISOP is the programming language, AIAP is the programming rules.

| Concept | Analogy | Definition |
|------|------|------|
| **AISOP** | Programming language (Python) | AI program language — defines file format (`.aisop.json`), Mermaid + JSON flow control flow + functions |
| **AIAP** | Programming rules (coding standards/design patterns) | Governance protocol — defines how programs should be written, quality standards, security guards, axiom constraints |
| **AIAP Program** | A standards-compliant project | A complete project written in AISOP language following AIAP rules |
| **AIAP Creator** | Project scaffolding (`create-react-app`) | Tool for creating AIAP programs — is itself an AIAP program (bootstrapping) |

### 2.0.1 Two Languages, One Governance

```
AISOP:
  AI program language supporting two flow formats:
  - Mermaid string: AI sees the full visual graph
  - JSON flow object: machine-parseable, code-native
  Entry: ASSERT RUN aisop.main
  File: .aisop.json

Governance (AIAP):
  Axiom 0, trust levels, security, quality standards, patterns, lifecycle
  — all apply regardless of which flow format is used.
```

| Dimension | Mermaid | JSON Flow |
|-----------|---------|-----------|
| Control flow format | Mermaid flowchart | JSON nodes + edges |
| Readability | Visual, AI-native | Structural, code-native |
| Entry point | `ASSERT RUN aisop.main` | `ASSERT RUN aisop.main` |
| File extension | `.aisop.json` | `.aisop.json` |
| Best for | Complex AI reasoning, visual flow | Programmatic generation, strict validation |

```
Naming conventions:
  .aisop.json  →  AISOP language format identifier
  _aiap        →  Program type identifier (what rules the directory follows)
  AIAP.md      →  Project declaration (similar to pyproject.toml / pom.xml)
```

### 2.1 File Field Responsibilities

> Each field has one and only one responsibility. Information appears in only one place.

**AISOP files (`.aisop.json`)**:

| Field | Responsibility | Content |
|------|------|------|
| `axiom_0` | **Immutable Foundation** | Fixed value: `Human_Sovereignty_and_Wellbeing` (required) |
| `id` | Identity | Unique identifier for programs and modules |
| `name` | Name | Product name + version number |
| `version` | Version | Semantic version number |
| `summary` | Capability overview | One sentence describing "what I can do" |
| `description` | Detailed description | Architecture, history, patterns, implementation details |
| `flow_format` | **Flow graph format** | `"mermaid"`, `"jsonflow"`, or `"hybrid"`. Default: `"hybrid"` (required) |
| `system_prompt` | **Behavioral guidelines** | Defines how the agent should behave (the sole behavior definition layer) |
| `loading_mode` | **Loading strategy** | `"normal"` = load full program, `"node"` = on-demand function loading, `"lite"` = AI loads functions as needed. Default: `"normal"` |
| `params` | **Input parameters** | Program input parameter declarations (optional) |
| `output_mode` | **Output Layer** | Defines L0 structured output format and L1 output format (optional field) |
| `instruction` | **Execution instruction** | Fixed as `ASSERT RUN aisop.main` (immutable constant) |
| `user_input` | **Reserved field** | Runtime placeholder `"{user_input}"` — substituted by executor with actual user message. Optional: usage depends on program role (e.g., required for route entry files, not needed for sub-modules). |
| `aisop.main` | Execution graph | Main flow graph (Mermaid or JSON flow) — all execution starts here |
| `functions` | Execution logic | Specific steps and constraints for each node |

### 2.2 instruction Immutable Constant

```
Rule: The instruction field of every AISOP file must be exactly: ASSERT RUN aisop.main
```

**Rationale**:
- `RUN` is a machine execution instruction, not a natural language suggestion. Analogous to Dockerfile `RUN`, SQL `SELECT`.
- `aisop.main` is a JSON structural path, pointing to the `content.aisop.main` execution graph.
- Program identity is provided by the `id` field; no need to repeat in instruction.
- Capability description is provided by `summary`/`description`; no need to repeat in instruction.

```
C language analogy:
  int main() { ... }     ← Entry is always main, uniform across all programs
  ASSERT RUN aisop.main   ← Entry is always aisop.main, asserted execution, uniform across all AISOP files
```

**sub_mermaid**: Even if the aisop object contains multiple graphs (e.g., `main`, `orchestrate`, `memory`), the entry point is still `aisop.main`. The main graph routes to sub-graphs internally through params.

### 2.3 system_prompt Behavioral Layer Rules

```
Rule: system_prompt is the behavioral layer — defines how the agent should behave, not what it is or how it's built.
```

**Must include**:
1. **Role positioning** — the agent's behavioral role (not the product name)
2. **Domain behavioral guidelines** — behavioral constraints specific to the domain
3. `Mirror User's exact language and script variant.` — multilingual requirement
4. `Align Axiom 0: Human Sovereignty and Wellbeing.` — Axiom 0 seal

**Must not include**:
- Product name or version number → already in `name` + `version` fields
- Architecture or pattern details → already in `description` field
- Module filenames or delegation logic → already in `functions` field
- Capability lists → already in `summary` field

```
Format template:
  "{behavioral role}. {domain guidelines}. Mirror User's exact language and script variant.
   Align Axiom 0: Human Sovereignty and Wellbeing."

Good example:
  "Personal expense tracking assistant. Prioritize numerical precision.
   Protect user financial privacy. Mirror User's exact language and script variant.
   Align Axiom 0: Human Sovereignty and Wellbeing."

Bad example:
  "Expense Tracker v1.0.0. Pattern B router: delegate data operations
   to record.aisop.json. Mirror User's exact language and script variant.
   Align Axiom 0: Human Sovereignty and Wellbeing."
   ↑ Contains product name+version(name), architecture(description), filenames(functions)
```

### 2.4 output_mode Output Layer Rules

Rule: `output_mode` defines the agent's structured output format (L0) and user-facing output format (L1).

**Field structure**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `L0` | string | Yes | Structured JSON output format and schema |
| `L1` | string | Yes | Output language rule (includes helpfulness directive) |
| `output` | string | Yes | Which layer to show: `"L1"` or `"L0+L1"` |

**Default L0**: `"Output JSON in ENGLISH: {intent, confidence, route, state, op}"` — structured execution evidence with 5 standard fields.

**Default**: When `output_mode` is omitted, the runtime agent's default output mode applies. This ensures backward compatibility with existing AISOP files.

**Security Override Rule**: Modules with `id` containing "safety" or tagged with `security: true` in their system content MUST have `output_mode.output` locked to `"L1"`. Global or parent-level `output: "L0+L1"` settings do NOT propagate to security modules. This prevents exposure of security detection logic to users.

### 2.5 loading_mode Loading Strategy Rules

Rule: `loading_mode` controls how the runtime agent loads function definitions from the file.

| Mode | Behavior | Use Case |
|------|----------|----------|
| `normal` (default) | All functions injected at once | Files with ≤15 nodes, sufficient token budget |
| `node` | Only current node's function provided per execution | Large files (>15 nodes), token-constrained environments |
| `lite` | AI loads functions as needed | Simple programs, minimal overhead |

**Default**: When `loading_mode` is omitted, `"normal"` is assumed.

**Generator rule**: Creator MUST include `"loading_mode": "normal"` in every generated `.aisop.json` file's system content.

---

## 3. AIAP.md Rules

Every `{name}_aiap/` directory **must** contain an AIAP.md file. AIAP.md is the project's governance contract and discovery entry point.

### 3.1 Required Fields (YAML frontmatter)

**Governance Fields (6)**:

| Field | Type | Description |
|------|------|------|
| `protocol` | string | AIAP version number, e.g., `"AIAP V1.0.0"` |
| `authority` | string | Governance authority domain, fixed as `aiap.dev` |
| `seed` | string | Language seed domain, fixed as `aisop.dev` |
| `executor` | string | Execution platform domain, fixed as `soulbot.dev` |
| `axiom_0` | string | Core axiom, fixed as `Human_Sovereignty_and_Wellbeing` |
| `governance_mode` | string | `NORMAL` or `DEV` |

**Project Fields (8)**:

| Field | Type | Description |
|------|------|------|
| `name` | string | Project name (snake_case) |
| `version` | string | Current version (semver, synchronized with main.aisop.json) |
| `pattern` | string | Structural pattern `A|B|C|D|E|F|G` |
| `flow_format` | string | Flow graph format: `"mermaid"`, `"jsonflow"`, or `"hybrid"`. Default: `"hybrid"`. |
| `summary` | string | Concise feature overview (recommended ≤500 characters) |
| `tools` | list/object | Tool declarations (see §3.3) |
| `modules` | list | Module inventory (see §3.4) |
| `license` | string | SPDX license identifier or `proprietary` (see Appendix B) |

### 3.2 Optional Fields (YAML frontmatter)

**Basic Optional Fields**:

| Field | Type | Description |
|------|------|------|
| `governance_hash` | string | Governance hash (see §18) |
| `quality` | object | `{weighted_score, grade, last_pipeline}` |
| `description` | string | Agent Skills compatible field — skill description |
| `tags` | list | Classification tags |
| `author` | string | Author information |
| `copyright` | string | Copyright notice (e.g. `"Copyright 2026 AIXP Labs AIXP.dev"`) |
| `tool_dirs` | list | Pattern G tool directory declarations (see §9 Pattern G) |
| `capabilities` | object | Runtime capability declarations `{offered, required}` |

**Security & Runtime Optional Fields** (Part III):

| Field | Type | Default | Description |
|------|------|--------|------|
| `trust_level` | number (0-4) \| string | 3 | Trust level (see §16). Integer T0-T4 is canonical; string form (e.g. `"T3"`, or protocol-specific like AIVP `"V0-V4 VTrust model"`) accepted for cross-protocol compatibility. |
| `permissions` | object | null | Permission boundaries (see §17) |
| `runtime` | object | null | Runtime constraints (see §19) |

**Engineering Optional Fields** (Part IV):

| Field | Type | Default | Description |
|------|------|--------|------|
| `status` | string | "draft" | Lifecycle state (see §23) |
| `deprecated_date` | string | null | Deprecation date |
| `successor` | string | null | Replacement program name |
| `intent_examples` | list | [] | Semantic routing anchors (see §21) |
| `discovery_keywords` | list | [] | Keyword index |
| `dependencies` | list | [] | Cross-project dependencies (see §22) |
| `min_protocol_version` | string | null | Minimum protocol version (see §25) |
| `benchmark` | object | null | Quality benchmark declaration |
| `identity` | object | null | Program identity and provenance (see I11) — `{ program_id, publisher, verified_on }` |

### 3.3 tools Field Specification

**Compact format** (backward compatible):

```yaml
tools: [file_system, shell]
```

**Structured format** (recommended):

```yaml
tools:
  - name: file_system
    required: true
    min_version: "1.0"
  - name: shell
    required: false
    fallback: "degrade"       # Degrade when unavailable
```

| Attribute | Type | Default | Description |
|------|------|--------|------|
| `name` | string | (required) | Tool name |
| `required` | boolean | true | Whether the tool is required |
| `min_version` | string | null | Minimum version requirement |
| `fallback` | string | null | Degradation strategy when unavailable: `"degrade"` / `"skip"` / `"error"` |

### 3.4 modules Field Specification

```yaml
modules:
  - id: health_tracker.record
    file: record.aisop.json
    nodes: 7
    critical: true              # Whether it is a critical module (default true)
    idempotent: true            # Whether it is idempotent (default false)
    side_effects: [file_write]  # Side effect declarations (default [])
```

| Attribute | Type | Default | Description |
|------|------|--------|------|
| `id` | string | (required) | Module unique identifier `{project}.{module}` |
| `file` | string | (required) | Filename |
| `nodes` | number | (required) | Number of functional nodes |
| `critical` | boolean | true | Whether to trigger FATAL on failure (see §20) |
| `idempotent` | boolean | false | Whether repeated execution is safe |
| `side_effects` | list | [] | Side effect list: `file_write`, `file_delete`, `api_call`, `shell_exec` |

Empty `side_effects` list = pure function (no side effects).

### 3.5 Markdown Body

**Required sections**:

| Section | Content |
|---|------|
| **Governance Declaration** | Declare adherence to AIAP protocol + Axiom 0 alignment |
| **Feature Overview** | List core features by module/intent |
| **Usage** | Entry file, tool requirements, prerequisites |

**Recommended sections** (when status=active):

| Section | Content |
|---|------|
| **Example Interactions** | 1-3 typical usage scenario input/output examples |
| **Applicable Conditions** | Clearly state scenarios where the program is and is not applicable |

**Optional sections**:

| Section | Content |
|---|------|
| **Data Storage** | Data file paths and formats |
| **Configuration** | Configurable params and defaults |
| **Quality Status** | ThreeDimTest scores, Pipeline history |
| **Version History** | Major version change summaries (structured format see §25) |
| **Error Handling** | Common errors and user handling instructions |

**File ending**: Must end with the AIAP closing seal.

| governance_mode | Seal Format |
|----------------|---------|
| NORMAL | `Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev` |
| DEV | `[L0_BOOT: Success] [L1_REPORT: Success] [endNode_Align Axiom 0: Human Sovereignty and Wellbeing]. Version: AIAP V1.0.0. www.aiap.dev` |

### 3.6 Creator Auto-Maintenance Rules

| Trigger Event | Creator Behavior |
|---------|-------------|
| **Create** | Auto-generate AIAP.md, populate all required fields, set status to draft |
| **Evolve** | Update version, modules, quality, summary (if changed) |
| **Modify** | Update version, quality |
| **Validate** | Check AIAP.md existence and field completeness (D8 check) |
| **QualityGate Pass** | If status=draft, automatically upgrade to active |
| **version_history snapshot** | Save AIAP.md snapshot in `{version}/` directory |

---

## Part II: Structural Specification

---

## 4. Node = Functional Responsibility

> Nodes match functions, main routes and dispatches, modules are self-contained, shared logic is extracted separately, no infinite splitting.

Each Mermaid node represents one functional responsibility of a module, similar to a function in a Python file. The number of nodes is naturally determined by functional complexity, not imposed by external hard limits.

```
Python analogy:
  record.py has 4 functions → record.aisop.json has 4 functional nodes
  query.py has 6 functions  → query.aisop.json has 6 functional nodes
  Node count follows function count, not quotas
```

---

## 5. Functional Node Count

```
Functional nodes = Total Mermaid nodes - Start - endNode
```

Start and endNode are the fixed structural framework of every AISOP file (similar to Python's `if __name__`), they don't reflect functional complexity and are not counted.

Example:

```
graph TD
    Start --> Parse --> Validate{OK?} --> Save --> Alert --> endNode
                                       --> AskFix --> Parse
```

Total nodes 7, functional nodes 5 (Parse, Validate, Save, Alert, AskFix).

---

## 6. Progressive Node Guidelines

Applies to all `.aisop.json` files (including main):

```
Functional nodes 3-12  → Normal, no prompt
Functional nodes 13-15 → ADVISORY — Suggest checking for split opportunities, provide specific suggestions
Functional nodes 16+   → RECOMMENDED — Strongly recommend splitting, provide split plan
```

- Both levels are WARNING, not FAIL
- Functionally cohesive large modules can annotate `fractal_exempt` to skip the suggestion
- Minimum requirement: >=3 functional nodes + (>=1 tool call OR >=3 steps)

---

## 7. fractal_exempt Annotation

When a module's functional nodes exceed 12 but the flow is highly cohesive, annotate in `system.content`:

```json
{
    "fractal_exempt": "The pipeline's 13 stages form a continuous pipeline; splitting would cause context fragmentation"
}
```

After annotation, Creator skips the progressive split suggestion for that file. Equivalent to Python's `# noqa`.

## 7.1. sub_mermaid Decomposition Rules

When a module's complexity exceeds thresholds but splitting into separate files would break functional cohesion, use sub_mermaid decomposition — multiple Mermaid graphs within a single `.aisop.json` file.

### 7.1.1. Structure

The `aisop` object contains multiple graph keys. `main` is always the entry point:

```json
{
  "aisop": {
    "main": "graph TD\n    Start[...] --> SubA[aisop.sub_a]\n    SubA --> SubB[aisop.sub_b]\n    ...",
    "sub_a": "graph TD\n    SubAStart[...] --> ...",
    "sub_b": "graph TD\n    SubBStart[...] --> ..."
  }
}
```

Rules:
- Entry point: always `ASSERT RUN aisop.main` (instruction immutable constant)
- Main graph references sub-graphs via `NodeName[aisop.sub_name]` syntax
- All functions from all sub-graphs share a single flat `functions` dictionary
- Parameters are defined once at root level and shared across all sub-graphs
- Each sub-graph has its own Start node and End node

### 7.1.2. Decomposition Priority

When complexity exceeds §6 thresholds, apply decomposition in this order:

```
Priority 0 — sub_mermaid (in-file sub-graph decomposition)
  Same file, shared context, no cross-file contracts needed.
  Preferred when:
    (a) Nodes share params and working context
    (b) Sub-graphs have data dependencies (output of one feeds next)
    (c) Splitting into files would duplicate shared parsing/setup logic

Priority 1 — sub_aisop (file-level split)
  Per §13 split rules. Required when:
    (a) Sub-graphs use entirely different tool sets (§13 Priority 1)
    (b) Sub-graphs are independently testable and deployable
    (c) A single sub-graph exceeds 16 functional nodes after sub_mermaid

Priority 2 — Sub_AIAP (directory-level split)
  Per §13. Required when sub_aisop files form a full independent program.
```

### 7.1.3. Execution Modes

Sub-graphs execute in one of the following modes. Declare the mode in `fractal_exempt`:

| Mode | Description | Example |
|------|-------------|---------|
| **Mutually Exclusive** | Main routes to exactly one sub-graph per invocation | advisor: 8 sub-graphs, TypeGate selects 1 |
| **Sequential** | Main calls sub-graphs in fixed order, each feeds the next | generate: scaffold → content → tooling |
| **Conditional** | Main selects a subset of sub-graphs based on runtime conditions | (future use) |
| **Hybrid** | Combines above modes (e.g., sequential stages where one stage uses conditional routing) | (future use) |

### 7.1.4. Node Counting Rules

For files with sub_mermaid:

1. **Total functional nodes** = sum of (functional nodes per sub-graph).
   Per-graph functional nodes = total graph nodes − Start − endNode.

2. **Single-path maximum** = functional nodes traversed in the longest execution path:
   - Mutually exclusive: main functional nodes + max(sub-graph functional nodes)
   - Sequential: main functional nodes + sum(all sub-graph functional nodes)
   - Conditional: main functional nodes + sum(selected sub-graph functional nodes)

3. **Threshold application**: Apply §6 thresholds to single-path maximum, not total.
   If single-path maximum exceeds 16, `fractal_exempt` annotation is required.

4. **fractal_exempt format** for sub_mermaid files:
   `"{total} functional nodes distributed across {N} sub_mermaid sub-graphs
   ({breakdown}). Sub-graphs execute {mode}. Maximum single-path execution
   {max} nodes."`

### 7.1.5. Function Body Complexity (Second Dimension)

Node count alone does not capture intra-function complexity (e.g., a single Generate node with 23 directives in step1). Apply a second-dimension check:

- **Steps per function**: count step keys (step1, step2, ..., stepN)
- **Directives per step**: count named directive blocks within a step
  (identified by UPPERCASE LABEL: pattern, e.g., "TOOL ANNOTATIONS:", "INCREMENTAL GENERATION:")

Thresholds:
- 8+ steps in one function → ADVISORY: consider sub_mermaid decomposition
- 15+ directives in one step → ADVISORY: consider splitting into multiple functions
- 20+ directives in one step → RECOMMENDED: decompose via sub_mermaid or file split

---

## 8. Pattern Selection

```
Number of independent functions → Pattern:
  1 function              → A: Script (single file)
  2+ functions            → B: Package (multiple files)
  2+ functions + complex shared → C: Package + Shared
  Sub-modules also need splitting → D: Nested Package
  With memory layer       → E: Package + Memory
  Multi-AIAP program ecosystem → F: Ecosystem
  With embedded tool directory → G: Embedded Runtime
```

---

## 9. Pattern A-G Detailed Definitions

### Pattern A: Script

```
{name}_aiap/
├── AIAP.md                     # Required: governance contract
└── main.aisop.json             # All logic
```

Applicable: todo list, timer, calculator, and other single-function programs. No hard limits. Progressive guidelines apply.

### Pattern B: Package

```
{name}_aiap/
├── AIAP.md                     # Required: governance contract
├── main.aisop.json             # Router: intent recognition → dispatch
├── {func1}.aisop.json          # Functional module (self-contained; see rule below)
├── {func2}.aisop.json
└── {func3}.aisop.json
```

Module independence rule: Pattern B modules MUST NOT directly `RUN` each other. Inter-module communication flows through `main.aisop.json` (the router), keeping the topology star-shaped. If two modules need to share non-trivial logic, use Pattern C instead.

Example:
```
expense_tracker_aiap/
├── AIAP.md                     # Governance contract
├── main.aisop.json             # Intents: record / query / budget / report
├── record.aisop.json           # Validate → Write → Confirm
├── query.aisop.json            # Parse → Read → Filter → Format
├── budget.aisop.json           # Set → Check → Alert
└── report.aisop.json           # Aggregate → Analyze → Display
```

### Pattern C: Package + Shared

```
{name}_aiap/
├── AIAP.md                     # Required: governance contract
├── main.aisop.json             # Router
├── {func1}.aisop.json
├── {func2}.aisop.json
└── shared.aisop.json           # Complex shared logic called by 2+ modules
```

Applicable: Pattern B packages where 2+ modules need to reuse non-trivial logic (validation chains, formatters used across modules, multi-step data-transform pipelines). Prefer Pattern B when each module's own system_prompt can absorb the shared concern (e.g. output style, single regex). Prefer Pattern D when the reusable piece has its own 2+ sub-functions worth nesting.

Shared rule: Create only when 2+ modules reuse **complex operations**. Simple sharing (formatting/style) goes in each module's system_prompt.

### Pattern D: Nested Package

```
{name}_aiap/
├── AIAP.md                     # Required: governance contract
├── main.aisop.json             # Top-level router
├── {simple_func}.aisop.json    # Simple module
└── {complex}_sub_aiap/         # Complex module (has sub-structure)
    ├── AIAP.md                 # Sub-package governance contract (if independently published)
    ├── main.aisop.json         # Sub-router
    ├── {sub1}.aisop.json
    └── {sub2}.aisop.json
```

Nesting rule: Maximum 2 levels, nest only when the sub-module itself has 2+ sub-functions.

#### Pattern D Example: AIAP Creator

```
aiap_creator_aiap/
├── AIAP.md                     # Governance contract (AIAP V1.0.0)
├── main.aisop.json             # Top-level orchestrator (28 functional nodes, fractal_exempt)
│   └── Intents: Create, Evolve, Modify, Validate, Simulate, Compare, Explain, General
│   └── Pipeline: Research→Evolve→Generate→Modify→QualityGate→Validate→Simulate→Observability→Review
├── generate.aisop.json         # Generator (11 functional nodes)
├── research.aisop.json         # Shared research module (15 functional nodes, fractal_exempt, 3-mode reuse)
├── review.aisop.json           # Reviewer (11 functional nodes)
├── simulate.aisop.json         # Simulator (10 functional nodes)
├── modify.aisop.json           # Modifier (10 functional nodes)
├── observability.aisop.json    # Telemetry analysis (9 functional nodes)
├── advisor.aisop.json          # Advanced advisor (52 functional nodes, fractal_exempt, 8 mutually exclusive sub-graphs)
├── AIAP_Standard.core.aisop.json         # Core quality (C1-C7, I1-I13 subset, D1-D7, MF1-MF36 incl. MF28b, PL core subset)
├── AIAP_Standard.security.aisop.json     # Security extension (I8-I15, D8-D10, AT1-AT7 incl. AT7 Confirmation Bypass, Code Trust Gate)
├── AIAP_Standard.ecosystem.aisop.json    # Ecosystem extension (MF10-MF19, PL ecosystem subset, Categories F-M)
├── AIAP_Standard.performance.aisop.json  # Performance extension (PL13-PL28, QRG1-QRG5)
└── AIAP_Protocol.md            # Structural specification (Protocol-level)
```

Characteristics:
- 8+4 modules (8 executable modules + 4 STANDARD extension files), ~146 functional nodes total
- main is a pure orchestrator (sequential delegation, no business logic), annotated fractal_exempt
- research reuses 3 modes via ModeGate (structure/quality/compliance), annotated fractal_exempt
- advisor uses sub_mermaid sub-graphs (8 mutually exclusive sub-graphs), actual single-path maximum 15 nodes (main 8 + largest sub-graph 7)
- Communication topology is star-shaped (main orchestrates), no direct inter-module communication

### Pattern E: Package + Memory

```
{name}_aiap/
├── AIAP.md                     # Required: governance contract
├── main.aisop.json             # Router
├── {func1}.aisop.json
├── {func2}.aisop.json
└── memory/                     # Memory layer
    ├── schema.json             # Memory field definitions (episodic/semantic/working)
    ├── decay_config.json       # Decay strategy params
    └── context_manager.json    # Context budget and loading strategy
```

Applicable: AIAP programs requiring cross-session memory, personalization, or RAG retrieval. Use advisor.aisop.json (advisor_type='memory') to generate memory/ directory content.

### Pattern F: Ecosystem

```
{ecosystem_name}/
├── AIAP.md                     # Required: ecosystem-level governance contract
├── blueprint.json              # Ecosystem blueprint (components, interfaces, topology)
├── {component1}_aiap/          # Independent component (Pattern A-E)
│   ├── AIAP.md                 # Required: component-level governance contract
│   └── main.aisop.json
├── {component2}_aiap/
│   ├── AIAP.md
│   └── ...
└── shared/                     # Cross-component shared data contracts
    └── data_contracts.json
```

Applicable: Complex systems with 3+ AIAP program components collaborating. Use advisor.aisop.json (advisor_type='orchestrate') to design ecosystem blueprints.

#### blueprint.json Component Interface Declaration

```json
{
    "ecosystem": "soulbot_ecosystem",
    "protocol": "AIAP V1.0.0",
    "components": ["component_a_aiap", "component_b_aiap"],
    "interfaces": [
        {
            "name": "health_data_query",
            "provider": "component_a_aiap",
            "consumer": "component_b_aiap",
            "contract": "shared/data_contracts.json#health_query",
            "mode": "sequential"
        }
    ]
}
```

#### AIAP.md `sub_aiaps` Field (Pattern F)

Pattern F programs MAY declare peer sub-AIAPs in their `AIAP.md` frontmatter under the `sub_aiaps` key. The corresponding proto definition is `SubAiapRef` in `aiap.proto` (authoritative for schema).

```yaml
sub_aiaps:
  - name: research_aiap
    path: ./research_aiap/
    version: "1.0.0"
    pipeline_position: 1
  - name: draft_aiap
    path: ./draft_aiap/
    version: "1.0.0"
    pipeline_position: 2
```

| Field | Required | Type | Purpose |
|-------|:--------:|------|---------|
| `name` | Yes | string | Logical name; must match `name` in the sub-AIAP's own AIAP.md |
| `path` | Yes | string | Relative path to the sub-AIAP directory (contains its own AIAP.md) |
| `version` | Yes | string | SemVer of the sub-AIAP pinned by this orchestrator |
| `pipeline_position` | Yes | int | 1-indexed pipeline stage; enforced by PL15 Pipeline Ordering |

**Axiom 0 propagation (§G.2.4):** the orchestrator MUST NOT structurally bypass, auto-approve, or remove a sub-AIAP's `sys.io.confirm` steps. Any such bypass is a FATAL Axiom 0 violation enforced by MF32.

**Recursion limits (§17.3):** sub-AIAP invocations count toward the recursion depth limit (default 3). Override via `runtime.max_recursion_depth` in the orchestrator's AIAP.md.

### Pattern G: Embedded Runtime

```
{name}_aiap/
├── AIAP.md                     # Required: governance contract (with tool_dirs field)
├── agent_card.json             # Program self-description (unconditional since P11)
├── main.aisop.json             # Router
├── {func1}.aisop.json
├── {func2}.aisop.json
├── python_tools/               # Python tool implementations
│   ├── README.md               # Required: tool description, interfaces, security constraints
│   ├── requirements.txt        # Frozen versions (== pinning, >= / * / ~= prohibited)
│   ├── *.py                    # Tool code
│   └── mcp_adapter.py          # Creator auto-generated MCP stdio endpoint
├── ts_tools/                   # TypeScript tool implementations
│   ├── README.md
│   ├── package.json            # Exact versions (^ ~ prohibited)
│   ├── package-lock.json       # Lock transitive dependencies
│   └── *.ts
├── go_tools/                   # Go tool implementations
│   ├── README.md
│   ├── go.mod + go.sum         # Dependency lock
│   └── bin/tool                # Pre-compiled binary (recommended)
├── rust_tools/                 # Rust tool implementations
│   ├── README.md
│   ├── Cargo.toml + Cargo.lock
│   └── target/release/tool     # Must be pre-compiled
├── shell_tools/                # Shell scripts (T4 + manual audit only)
│   ├── README.md
│   └── tool.sh / tool.ps1
├── mcp_tools/                  # MCP Server definition layer
│   ├── README.md
│   └── mcp_server.json         # MCP Server manifest + runtime declaration
├── a2a_tools/                  # A2A bridge configuration layer (optional, Pattern F/G only)
│   ├── README.md
│   └── bridge_config.json
├── n8n_tools/                  # n8n workflow automation layer (optional)
│   ├── README.md
│   ├── workflow.json
│   └── config.json
├── aiap_tools/                 # AIAP sub-program tools (optional)
│   ├── README.md               # Required: sub-program inventory, invocation interface, security constraints
│   ├── data_cleaner_aiap/      # A complete AIAP program used as a tool
│   │   ├── AIAP.md
│   │   ├── main.aisop.json
│   │   └── transform.aisop.json
│   └── report_gen_aiap/        # Another AIAP program
│       ├── AIAP.md
│       └── main.aisop.json
├── other_tools/                # Open extension layer (optional)
│   └── README.md               # Required: invocation method, interfaces, security constraints
└── memory/                     # Pattern E memory layer (optional)
    └── ...
```

Inherits: All rules from Pattern E or F

Additional requirements:
- AIAP.md must include a `tool_dirs` field declaring tool directories
- `mcp_tools/mcp_server.json` must exist
- I13 Embedded Code Safety rules apply (10 sub-checks)
- MF16 Tool Directory Consistency rules apply
- Minimum trust level: T3
- Requires Code Trust Gate verification

Characteristics:
- CLI executors have native shell tools and can directly execute bundled code
- No intermediate layer or pre-installed tools needed
- Self-contained, independently deployable

#### Supported tool_dirs Directory Types

| Type | Runtime | Dependency Lock | Use Cases |
|------|--------|---------|---------|
| `python_tools/` | Python 3.9-3.13 | `requirements.txt` (== pinning) | Data processing, AI/ML, file operations |
| `ts_tools/` | Node.js/Deno/Bun | `package-lock.json` | Web API, JSON processing, type safety |
| `go_tools/` | Go or pre-compiled binary | `go.sum` | High concurrency, CLI, low latency |
| `rust_tools/` | Pre-compiled binary | `Cargo.lock` | High performance, memory safety, WASM |
| `shell_tools/` | bash / pwsh | None | System scripts (T4 only) |
| `mcp_tools/` | stdio transport | `mcp_server.json` | MCP ecosystem tools |
| `a2a_tools/` | A2A protocol | `bridge_config.json` | Inter-agent collaboration (bridge config, Pattern F/G only) |
| `n8n_tools/` | n8n instance | `workflow.json` | Multi-service integration |
| `aiap_tools/` | AIAP Executor | `AIAP.md` (per sub-program) | AIAP programs as callable tools |
| `other_tools/` | Custom | README.md | Open extension |

#### mcp_server.json Format

```json
{
  "schema_version": "mcp-1.0",
  "server_id": "file:///./mcp_tools",
  "transport": "stdio",
  "runtime": "python3.11",
  "entry_point": "python_tools/mcp_adapter.py",
  "exposed_tools": [
    {
      "name": "process_data",
      "description": "Process input data and return structured result",
      "inputSchema": {
        "type": "object",
        "required": ["data"],
        "properties": {
          "data": { "type": "string" }
        }
      }
    }
  ],
  "file_hashes": {
    "python_tools/data_processor.py": "sha256_hash_value",
    "python_tools/mcp_adapter.py": "sha256_hash_value"
  },
  "governance": {
    "aiap_protocol": "AIAP V1.0.0",
    "trust_level": 3,
    "governance_hash": "filled by Creator ReviewStep"
  }
}
```

#### Code Trust Gate

Pattern G programs must pass the Code Trust Gate security verification upon loading:

```
Load Pattern G program
    ↓
Code Trust Gate:
  1. governance_hash verification (covers all files including tool_dirs source code)
  2. Static analysis: import/require declarations vs permissions.network
  3. File hash verification (against mcp_server.json file_hashes)
  4. Trust level check (Pattern G minimum T3)
  5. Dependency lock file verification
    ↓
  [T3 mode] Requires human review confirmation
  [T4 mode] Auto-pass
    ↓
Start MCP Server (stdio)
    ↓
AIAP program execution (invokes tools via MCP)
```

##### Recursive Code Trust Gate for aiap_tools/

When aiap_tools/ directory is detected during Code Trust Gate:

```
Code Trust Gate (existing steps 1-5 above)
    ↓
Step 6: Shell audit (existing)
    ↓
Step 7: Detect aiap_tools/ directory?
    ↓ Yes
Initialize call_stack = []
Push parent.program_id to call_stack
For each aiap_tools/{name}_aiap/:
  1. Read AIAP.md — extract program_id, trust_level, permissions, governance_hash
  2. CIRCULAR DEPENDENCY CHECK: if program_id in call_stack → FAIL (CIRCULAR_DEPENDENCY)
  3. Push program_id to call_stack
  4. TRUST CEILING CHECK: trust_level <= parent.trust_level → or FAIL
  5. PERMISSION SUBSET CHECK: permissions ⊆ parent.permissions → or FAIL
  6. GOVERNANCE HASH CHECK: recompute and verify → or FAIL
  7. RECURSION DEPTH CHECK: current_depth < 3 → or FAIL
  8. If sub-program is Pattern G with aiap_tools/ → recurse (depth + 1)
  9. Pop program_id from call_stack (finally semantics — even on failure)
    ↓
[Any sub-program fails] → Entire Code Trust Gate FAIL
    ↓ No aiap_tools/ or all pass
Continue normal MCP Server startup
```

#### I13 Embedded Code Safety (10 Sub-Checks)

Applicable: Pattern G programs (with tool_dirs). Pattern A-F marked N/A.

| Sub-Check | Description |
|--------|------|
| **(a) CODE INTEGRITY** | SHA-256 hashes of all source/binary files in tool_dirs/ must be recorded in mcp_server.json file_hashes |
| **(b) NETWORK DECLARATION** | Detect network access APIs (requests/fetch/net/http, etc.); if present, permissions.network.allowed must be true |
| **(c) FILE SYSTEM SCOPE** | File write operations must not exceed permissions.file_system.scope |
| **(d) DEPENDENCY VERSION PINNING** | Python: == pinning; TS/JS: ^ ~ prohibited; Go: go.sum must exist; Rust: Cargo.lock must exist |
| **(e) MCP PROXY REQUIRED** | All code tools must be exposed through the mcp_tools/ layer; executor direct subprocess execution of source files is prohibited |
| **(f) SHELL AUDIT** | When shell_tools/ exists, trust_level must be ≥ T4 |
| **(g) AIAP TRUST CEILING** | When aiap_tools/ exists: each sub-program's trust_level must be <= parent's trust_level |
| **(h) AIAP PERMISSION SUBSET** | When aiap_tools/ exists: sub-program permissions.file_system.scope must be within parent scope; sub-program permissions.network.endpoints must be subset of parent endpoints |
| **(i) AIAP RECURSION DEPTH** | aiap_tools/ nesting depth must not exceed 3. Verify by traversing sub-program tool_dirs for nested aiap_tools/ |
| **(j) AIAP GOVERNANCE HASH** | Each sub-program's governance_hash must be verified (recomputed and compared to AIAP.md declaration) |

#### MF16 Tool Directory Consistency

Applicable: Pattern G programs.

| Check | Description |
|------|------|
| **(a)** | mcp_server.json exists at the declared path |
| **(b)** | mcp_server.json exposed_tools entries have corresponding declarations in AIAP.md tools[] |
| **(c)** | AIAP.md tools[] entries referencing mcp_server exist in exposed_tools |
| **(d)** | agent_card.json exists at program root and fields match AIAP.md (unconditional since P11) |
| **(e)** | When aiap_tools/ exists: each sub-directory must contain a valid AIAP.md with all 6 required governance fields present |
| **(f)** | Each aiap_tools/ sub-program's AIAP.md governance fields structurally complete (protocol, authority, seed, executor, axiom_0, governance_mode all present and non-empty) |
| **(g)** | Each aiap_tools/ sub-program's tool_dirs declarations (if any) match actual directory structure within the sub-program |
| **(h)** | Parent AIAP.md tools[] entries using `aiap:{name}` prefix must have corresponding sub-programs in aiap_tools/{name}_aiap/ |

#### aiap_tools/ Invocation Protocol

aiap_tools/ enables AIAP programs to invoke other AIAP programs as tools, creating a native tool-level relationship without requiring an MCP Server intermediary.

##### Invocation Mechanism

1. Parent program references a sub-program tool in its AISOP functions using the `aiap:{name}` prefix
2. Executor detects `aiap:` prefix and locates `aiap_tools/{name}_aiap/` in program root directory
3. Executor reads sub-program's `AIAP.md` and verifies trust and permissions (see Code Trust Gate extension)
4. Executor loads sub-program in a child execution context with inherited constraints
5. Sub-program executes and returns result to parent's calling node

##### Security Constraints

- **Trust Ceiling**: Sub-program's `trust_level` MUST be <= parent's `trust_level`
- **Permission Subset**: Sub-program's `permissions` scope MUST be a subset of parent's `permissions`
- **Recursion Depth**: Maximum nesting depth of aiap_tools is 3 (parent → child → grandchild → great-grandchild)
- **Circular Dependency Prevention**: Executor MUST maintain a call stack of program IDs; if a program ID appears twice in the stack, execution MUST fail with CIRCULAR_DEPENDENCY error
- **Governance Integrity**: Sub-program's `governance_hash` MUST verify before execution

##### Resource Isolation

| Resource | Isolation Strategy |
|----------|-------------------|
| memory/ | Sub-program uses own memory/ only, cannot access parent memory/ |
| Logs | Sub-program logs prefixed with `[aiap:{name}]`, merged into parent log stream |
| Temp files | Sub-program temp files in `aiap_tools/{name}_aiap/.tmp/`, cleaned after execution |
| Environment | Sub-program does NOT inherit parent environment variables |
| token_budget | Sub-program allocated from parent's remaining token_budget |

##### Error Propagation

```
Sub-program GREEN        → Parent step completes normally
Sub-program AMBER/YELLOW → Parent receives WARNING, follows fallback strategy
Sub-program RED/FAIL     → Parent receives ERROR, triggers Error handling
Sub-program TIMEOUT      → Executor force-terminates, parent receives TIMEOUT_ERROR
```

Timeout controlled by Executor (not parent AISOP node). Priority: AISOP function timeout_seconds > sub-program AIAP.md runtime.timeout_seconds > default 60s.

call_stack cleanup: Executor guarantees pop on failure (finally semantics).

##### README.md Requirements

aiap_tools/README.md MUST contain:

| Section | Content |
|---------|---------|
| Overview | Purpose of aiap_tools/ directory |
| Sub-Program Inventory | For each sub-program: name, summary, pattern, trust_level |
| Invocation Interface | Calling convention (aiap:{name}), input/output contracts |
| Security Constraints | Trust inheritance, permission boundaries, recursion limits |

##### Version Compatibility

- Sub-program's `min_protocol_version` MUST be <= parent's `protocol` version
- When parent evolves, sub-program versions are NOT automatically bumped (independent lifecycle)
- Parent's AIAP.md SHOULD declare sub-program version expectations in `dependencies[]`

#### Backward Compatibility

- The tool_dirs field is entirely optional
- Programs without tool_dirs (Pattern A-F) are unaffected
- I13 and MF16 are marked N/A for non-Pattern G programs
- The governance_hash algorithm is unchanged for non-Pattern G programs

---

## 10. main.aisop.json Rules

main follows the same progressive node guidelines as functional modules. The distinction is a **qualitative constraint** (not a quantitative one):

**Pattern A**: main is the only file, contains all logic, no special constraints.

**Pattern B+**: main is a router:
- Contains only routing logic + lightweight inline handling
- No business logic (data processing, file I/O, complex validation)
- tools = union of all sub-module tools
- The number of routing nodes is naturally determined by the number of intents
- Invocation method: intent recognition → read corresponding sub-file → AI Agent executes

```
Determining whether a node belongs to main:
  ≤2 steps + no tool calls → OK (lightweight inline, e.g., Explain, General)
  >2 steps or has tool calls → should be placed in sub_aisop
```

---

## 11. Functional Module Rules

- Fully self-contained (independent system_prompt / tools / params / functions)
- Does not depend on other modules' internal implementations
- Module internal depth is determined by function, progressive guidelines apply
- Minimum requirement: >=3 functional nodes + (>=1 tool call OR >=3 steps)

---

## 12. Independent Function Judgment

Can be described in one sentence + does not share dedicated tools/state + can be tested independently → separate into its own file

- Level 1 tools (file_system, shell) are general infrastructure and do not count as "shared tools"
- Modules that read/write the same data file via file_system can still be independent (each responsible for different operations)
- "Shared state" refers to runtime memory state or dedicated connections, not persisted data files

---

## 13. Sub_AIAP Split Rules

When Creator suggests splitting, analyze split boundaries in the following priority order:

```
Priority 1 — Tool boundaries:
  Node group A uses web_search + web_fetch
  Node group B uses only file_system
  → Natural boundary, split into independent sub_aiap

Priority 2 — Data flow stages:
  Clear stage boundaries in a linear pipeline (research → generate → test)
  → Each stage is a sub_aiap candidate

Priority 3 — Functional independence:
  Meets the three conditions for independent function judgment
  → Split into sub_aiap
```

**Patterns that must not be split**:
- Convergence node groups (many-to-one fan-in pattern) → keep in the same sub_aiap
- Error recovery loops (Error → Retry → original node) → keep in the same sub_aiap
- Tightly coupled nodes sharing the same tool + state → keep in the same sub_aiap

---

## 14. Pattern Upgrade Convergence Handling

When upgrading from Pattern A→B and splitting files, existing convergence/display nodes (e.g., Respond, Display, Output) need special handling:

```
Convergence node determination:
  Does the node have >2 steps or tool calls?
    → Does not meet main inline criteria, must be assigned to a sub-module

  Do multiple sub-modules need this node's logic?
    → Each sub-module creates its own dedicated version (customized to its output format)
    → Do not create shared.aisop.json (unless logic is complex and completely identical)

  Only one sub-module uses it?
    → Directly include in that sub-module
```

Example:
```
Pattern A (before split):
  SearchRecipes → ReadRecipe → NutritionAnalysis → Respond → endNode
  SaveCollection → Respond → endNode
  CompareView → Respond → endNode
  (Respond is a full-path convergence point, 4 steps + tool references)

Pattern B (after split):
  search.aisop.json:  ...→ SearchRespond → endNode  (search result display)
  collection.aisop.json: ...→ CollectionRespond → endNode (collection operation display)
  (Each sub-module has a dedicated Respond, content customized per module output)
```

---

## 15. Dual-Stream Rules

Complex projects (Pattern D+) may optionally provide both human-readable and AI-optimized versions:

```
{name}_aiap/
├── AIAP.md
├── main.human.aisop.json      # Human-readable version (full key names)
├── main.ai.aisop.json         # AI-optimized version (compressed key names)
└── ...
```

Rules:
- Both versions must have completely identical logical semantics
- `.human` version uses full key names, convenient for human review
- `.ai` version uses abbreviated key names, reducing token consumption
- AI Agent preferentially loads the `.ai` version, loads the `.human` version for debugging
- Non-dual-stream projects still use a single `.aisop.json` (without `.human` or `.ai` prefix)

---

## Part III: Security & Runtime

---

## 16. Trust Levels

AIAP programs declare their permission requirements and execution modes through `trust_level`.

### 16.1 Four-Tier Trust Definition

| Tier | Name | Meaning | Permission Scope |
|------|------|------|---------|
| **T1** | Metadata-Only | Read AIAP.md frontmatter only | Does not load .aisop.json content |
| **T2** | Instruction-Read | Can read .aisop.json instruction content | Cannot execute any tool calls |
| **T3** | Supervised | Requires human approval or sandbox environment for execution | Each tool call requires confirmation |
| **T4** | Autonomous | Executes autonomously within declared permission boundaries | Follows permissions field constraints |

### 16.2 Relationship Between Trust Levels and Capabilities

| trust_level | Executable Operations | Typical Use Cases |
|-------------|-------------|---------|
| T1 | Read summary, name, description | Program directory indexing, search result display |
| T2 | Read complete flowcharts, function definitions | Code review, documentation generation, teaching |
| T3 | Execute all tool calls under human supervision | First-run new programs, high-risk operations |
| T4 | Autonomously execute all declared tool calls | Verified production programs |

### 16.3 Declaration Method

```yaml
# AIAP.md frontmatter
trust_level: 3    # Default value, optional field
```

When trust_level is not declared, the executor **MUST** treat it as T3 (Supervised).

**T4 evolution rule (Axiom 0 invariant):** A program evolving from T1/T2/T3 to T4 MUST simultaneously declare a complete `permissions` field (§17). Evolution that raises trust_level to T4 without a `permissions` declaration is FATAL — the executor must reject the program. This closes the loophole where a missing `permissions` field on a newly-T4 program would grant unchecked autonomy.

### 16.4 Trust Levels and sys.io.confirm (AISOP V1.0.0)

| trust_level | sys.io.confirm Behavior |
|-------------|------------------------|
| T1 | No sys.* execution — not applicable |
| T2 | No sys.* execution — not applicable |
| T3 | sys.io.confirm forced-blocking — human confirmation required every time |
| T4 | sys.io.confirm forced-blocking — human confirmation still required |

T3 vs T4 distinction:
- T3: All tool calls require confirmation (sys.io.confirm is one of many)
- T4: Only sys.io.confirm-marked operations require confirmation (others execute autonomously)

T4 programs execute autonomously within declared permission boundaries. However, `sys.io.confirm` steps are **NOT** autonomous — they always require human confirmation regardless of trust_level. This is an Axiom 0 invariant.

`sys.io.confirm` serves as the bridge from T3 "full supervision" to T4 "selective supervision" — T4 programs use `sys.io.confirm` to precisely mark which operations require human participation.

### 16.5 Cross-Protocol Trust Representations

AIAP `trust_level` is canonically an integer T0-T4. However, programs implementing sibling protocols (AIBP / AIVP / AISP) may declare trust_level using that protocol's native representation, and AIAP validators **MUST** accept both canonical integer and string forms.

**Accepted forms** (validator: `aiap_schema.trust_level`):

| Form | Example | Used by |
|------|---------|---------|
| Integer 0-4 | `3`, `4` | AIAP programs (canonical) |
| String "T" prefix | `"T3"`, `"t2"` | Shorthand in governance docs |
| Protocol-specific string | `"V0-V4 VTrust model"` | AIVP programs (commercial V-Trust) |
| Object with `level` key | `{"level": 3, "authentication": "oauth2"}` | Extended metadata form (agent_card compatibility) |

**Rejected forms**:
- Empty string `""`
- Boolean `true`/`false`
- Other types (float, list, null for REQUIRED field)

**Validator behavior** (`governance_consistency`):
- Normalizes all forms to integer via `_normalize_trust_level` before comparison (e.g. `"T3"` → `3`, `{"level": 3}` → `3`)
- Pure strings like `"V0-V4 VTrust model"` compared by string equality across the four governance files
- **All 4 governance files MUST declare the same normalized trust_level** (main.aisop.json, agent_card.json, quality_baseline.json, AIAP.md)

**Precedence**: Within a single AIAP, prefer the canonical integer form. String forms exist for protocol interop, not stylistic choice.

See Appendix G for full sys.* governance rules.

---

## 17. Permission Boundaries

T4 (Autonomous) programs **must** declare permission boundaries through `permissions`. This field is optional for T1-T3 programs.

### 17.1 Declaration Format

```yaml
# AIAP.md frontmatter
permissions:
  file_system:
    scope: "./data/"            # Read/write scope restriction (relative to project root)
    operations: ["read", "write"]
  shell:
    allowed: false              # Prohibit shell calls
  network:
    allowed: false              # Prohibit network calls
```

### 17.2 Permission Types

| Permission | Attribute | Description |
|------|------|------|
| **file_system** | `scope` | Directories allowed for access (glob syntax) |
| | `operations` | Allowed operations: `read`, `write`, `delete` |
| **shell** | `allowed` | Whether shell execution is allowed |
| | `allowlist` | List of allowed commands (only when allowed=true) |
| **network** | `allowed` | Whether network requests are allowed |
| | `endpoints` | List of allowed URL patterns |

### 17.3 Executor Responsibilities

The executor (SoulBot) **must** do the following when running T4 programs:
1. Read the `permissions` declaration
2. Verify whether tool calls are within the declared scope before execution
3. Out-of-scope calls → Reject execution + Report security violation

**Sub-program recursion limits.** When one AIAP program invokes another via `RUN aisop.*` (Pattern D nested packages or Pattern F ecosystem components), the executor MUST enforce a default recursion depth limit of **3** to prevent runaway call chains. Programs MAY override this by declaring `runtime.max_recursion_depth: <N>` in AIAP.md frontmatter (§19). Exceeding the effective limit is FATAL.

### 17.4 sys.* Permission Mapping (AISOP V1.0.0)

AISOP V1.0.0 sys.* system calls are subject to existing permission boundaries:

| Permission | sys.* Mapping |
|------------|---------------|
| `file_system.scope` | `sys.io.read/write` file paths must be within scope |
| `file_system.operations` | `sys.io.read` requires "read", `sys.io.write` requires "write" |
| `shell.allowed` | `false` → prohibits `sys.run` (all variants) |
| `shell.allowlist` | `sys.run` commands must be on the allowlist |
| `network.allowed` | `sys.run` network operations and `sys.llm` external model calls are restricted |
| `network.endpoints` | `sys.llm` external model API endpoints must be in the allowed list |

**New permission type** for `sys.code.exec`:

```yaml
permissions:
  code_execution:
    allowed: false              # Whether sys.code.exec is permitted
    languages: []               # Allowed language list (e.g., ["python", "javascript"])
    sandbox: "required"         # Sandbox requirement level
```

When the executor encounters a `sys.*` step:
1. Parse the `sys.*` call type and arguments
2. Verify whether the permission declaration allows this operation
3. Permission insufficient → Reject execution + Report security violation (FATAL)
4. Permission sufficient → Execute the operation

Modules containing `sys.io.write` SHOULD declare `side_effects: [file_write]`. Modules containing `sys.run` SHOULD declare `side_effects: [shell_exec]`. This follows naturally from §3.4 module specification.

See Appendix G for full sys.* governance rules.

---

## 18. Integrity Verification

### 18.1 governance_hash Algorithm

```
governance_hash = SHA-256(
    All .aisop.json file contents (concatenated in alphabetical order by filename, CRLF→LF normalized)
)

Pattern G Extension:
  The .aisop.json file set remains unchanged. File hashes of tool_dirs/ are recorded
  in the file_hashes field of mcp_server.json, indirectly covered by governance_hash.
  The governance_hash algorithm for programs without tool_dirs remains unchanged (backward compatible).
```

Output format (canonical v1.0): pure 16-character hexadecimal (e.g., `"d2f1165dcf8b928d"`). Legacy format `"sha256:{64-hex}"` is accepted by validators for backward compatibility but new writes use canonical v1.0.

### 18.2 Requirement Rules

| trust_level | governance_hash |
|-------------|----------------|
| T1-T2 | Optional |
| T3 | Recommended |
| T4 | Recommended |
| Published to Registry | Required |

### 18.3 Verification Process

Creator ValidateStep performs verification:
1. Compute the SHA-256 hash of the current files
2. Compare with the governance_hash declared in AIAP.md
3. Mismatch → WARNING: "Integrity check failed — files may have been modified outside Creator pipeline"

---

## 19. Runtime Constraints

### 19.1 Declaration Format

```yaml
# AIAP.md frontmatter
runtime:
  timeout_seconds: 300          # Per-execution timeout (default: executor-determined)
  max_retries: 3                # Maximum retry count (default: 3)
  token_budget: 50000           # Token budget limit (default: unlimited)
  idempotent: false             # Whether overall execution is idempotent (default: false)
  side_effects:                 # Overall side effect declarations
    - file_write
    - api_call
```

### 19.2 Field Descriptions

| Field | Meaning | Purpose |
|------|------|------|
| `timeout_seconds` | Timeout limit for a single complete execution | Prevent infinite execution |
| `max_retries` | Maximum retry count for RECOVERABLE errors | Control retry overhead |
| `token_budget` | Token consumption limit for a single execution | Cost control |
| `idempotent` | Whether repeated execution produces the same result | Orchestrator determines if safe retry is possible |
| `side_effects` | List of side effects for the overall program | Orchestrator assesses execution risk |

### 19.3 Relationship with modules

- Program-level `runtime.side_effects` = Union of all module `side_effects`
- Program-level `runtime.idempotent` = true when all critical modules are `idempotent`
- Module-level attributes (§3.4) provide fine-grained control; program-level attributes provide a quick overview

---

## 20. Error Handling Protocol

### 20.1 Error Classification

| Category | Meaning | Strategy |
|------|------|------|
| **RECOVERABLE** | Transient failures (network timeout, file lock, API throttling) | Retry per `max_retries`, exponential backoff |
| **DEGRADABLE** | Non-critical module failure (`critical: false`) | Skip failed module, execute in degraded mode, mark WARNING |
| **FATAL** | Critical module failure (`critical: true`) or security violation | Stop immediately, report error, produce no output |

### 20.2 Retry Strategy

```
Retry interval: 1s, 2s, 4s, 8s, ... (exponential backoff, base=2)
Maximum retries: runtime.max_retries (default 3)
Maximum interval: min(2^retry_count, 30) seconds
Each retry must log: error reason + retry count + timestamp
```

### 20.3 Degradation Behavior

When a module execution fails and the module has `critical: false`:
1. Skip that module's output
2. Mark in the final result: `"DEGRADED: {module_name} skipped due to {error}"`
3. Does not affect the overall success/failure determination
4. Final result includes a list of degraded modules

### 20.4 Termination Conditions

Each AIAP program execution terminates under the following conditions:

| Termination Type | Condition | Result |
|---------|------|------|
| **Successful Termination** | All critical modules completed + output passes validation | Return complete result |
| **Timeout Termination** | `runtime.timeout_seconds` reached | Return completed portion + timeout marker |
| **Error Termination** | FATAL-level error triggered | Return error report, no partial results |
| **Degraded Termination** | Successful termination but with skipped modules | Return degraded result + degradation report |
| **Rejection Termination** | `sys.io.confirm` rejected by user + no `on_error` handler | Return rejection report (which confirm was rejected, user response) |
| **Assertion Termination** | `sys.assert` failed + no `on_error` handler | Return assertion report (failed expression, actual vs expected values) |

### 20.5 sys.* Error Types (AISOP V1.0.0)

AISOP V1.0.0 §6.12 defines 6 standard error types from system calls. These are classified into the existing error categories:

| Error Type | Source | Classification | Handling Strategy |
|-----------|--------|----------------|-------------------|
| `confirm_rejected` | `sys.io.confirm` | FATAL(confirm) | User explicitly rejected; `on_error` route or abort |
| `confirm_timeout` | `sys.io.confirm` | FATAL(confirm) | Timeout with no response; abort (never silently approve) |
| `assertion_error` | `sys.assert` | FATAL(assert) | Condition is false; abort immediately |
| `command_error` | `sys.run` | RECOVERABLE | Command failed; retryable |
| `command_timeout` | `sys.run.timeout` | RECOVERABLE | Command timed out; retryable |
| `io_error` | `sys.io.read/write` | RECOVERABLE | File operation failed; retryable |

**FATAL behavior extension** (aligned with AISOP §6.12):

FATAL means "abort current node execution":
- If an `on_error` handler exists → route to handler node (handler decides next steps)
- If no `on_error` handler → abort entire program execution

`on_error` is the standard error routing mechanism from AISOP §5.2.4. AIAP does not override it.

**FATAL(confirm) special rules:**
- Cannot be auto-retried (deterministic: user has already decided)
- Cannot be auto-approved (Axiom 0 constraint)
- Can be routed via `on_error` to a handler node
- Handler is allowed to: log audit trail, notify user, perform cleanup, choose alternative path (e.g., degraded operation)
- Handler is prohibited from: auto-approving, bypassing confirmation, simulating user response

**FATAL(assert) special rules:**
- Cannot be retried (deterministic failure = always fails under same conditions)
- Can be routed via `on_error` to a handler node

**sys.* retry rules:**

| sys.* Call | Retryable? | Reason |
|-----------|-----------|--------|
| `sys.io.confirm` | No | FATAL(confirm) — user decision is final |
| `sys.io.input/select` | No auto-retry | Forced-blocking — may prompt user to re-enter |
| `sys.assert` | No | Deterministic failure = always fails |
| `sys.run` | Yes | Subject to `retry_policy` |
| `sys.run.timeout` | Yes | Subject to `retry_policy` |
| `sys.code` | Yes | Subject to `retry_policy` |
| `sys.llm` | Yes | Subject to `retry_policy` |
| `sys.io.read/write` | Yes | Transient issues (file lock, etc.) |

Principle: Deterministic failures are not retried. Transient failures may be retried.

---

## Part IV: Engineering Capabilities

---

## 21. Discovery Protocol

### 21.1 Discovery Layers

| Layer | Method | Mechanism | Token Cost |
|------|------|------|-----------|
| **L1 Passive Discovery** | File system scan | Scanner traverses directories, identifies `_aiap/` directories containing AIAP.md | ~50-80/program |
| **L2 Semantic Discovery** | Intent matching | Match user queries against `intent_examples` by semantic similarity | 0 (pre-computed) |
| **L3 Registry Discovery** | Registry query | Query published programs via AIAP Registry (aiap.dev) | ~100/query |

### 21.2 L1 Scanning Protocol

The scanner should search for AIAP programs in the following order:

1. `*_aiap/` subdirectories under the current working directory
2. Configured AIAP library paths (e.g., `~/.aiap/library/`)
3. Dependency paths declared in the project's `aiap.config`

For each discovered AIAP program:
1. Read AIAP.md YAML frontmatter (L1 metadata, ~50-80 tokens)
2. Register to the available program inventory (name + summary + status)
3. Load full content only when matched (L2+L3)

### 21.3 L2 Semantic Matching

```yaml
# AIAP.md frontmatter
intent_examples:
  - "Record today's weight"
  - "View this week's blood pressure trend"
  - "Generate monthly health report"
discovery_keywords:
  - health
  - tracking
  - wellness
```

Matching process:
1. Convert `intent_examples` to embedding vectors
2. When a new query arrives, compute cosine similarity with existing vectors
3. Similarity exceeds threshold → candidate match
4. Rank using `summary` + `discovery_keywords`

### 21.4 Invocation Modes

| Mode | Trigger Method | Matching Mechanism |
|------|---------|---------|
| **Explicit Invocation** | User specifies program name (e.g., "use health_tracker") | Exact match on `name` field |
| **Implicit Invocation** | LLM automatically selects based on user intent | Semantic matching on `summary` + `intent_examples` |

---

## 22. Dependency Resolution

### 22.1 Dependency Declaration

```yaml
# AIAP.md frontmatter
dependencies:
  - name: shared_utils_aiap
    version: "^1.0.0"           # semver range constraint
    required: true
  - name: analytics_aiap
    version: ">=2.0.0"
    required: false              # Optional dependency
    fallback: "skip"             # When unavailable: "skip" / "degrade" / "error"
```

### 22.2 Version Constraint Syntax

| Syntax | Meaning | Match Examples |
|------|------|---------|
| `"1.2.3"` | Exact version | 1.2.3 only |
| `"^1.2.0"` | Compatible updates | >=1.2.0 and <2.0.0 |
| `"~1.2.0"` | Patch updates | >=1.2.0 and <1.3.0 |
| `">=1.0.0"` | Minimum version | >=1.0.0 |

### 22.3 Resolution Strategies

1. **Flat Resolution** (default) — All dependencies are resolved at the same level; when version conflicts arise, the highest compatible version satisfying all constraints is selected
2. **Isolated Resolution** — In Pattern F Ecosystem, each component resolves dependencies independently, interacting through `data_contracts`

### 22.4 Conflict Resolution

When multiple AIAP programs depend on different versions of the same program:
- Automatically select the highest version satisfying all constraints
- If no version can satisfy all constraints → Report conflict, require human decision
- Conflict report includes: conflicting dependency name, source of each constraint, possible solutions

---

## 23. Program Lifecycle

### 23.1 Lifecycle States

| State | Meaning | AIAP.md Field | Creator Behavior |
|------|------|-------------|-------------|
| **draft** | In development, unstable | `status: draft` | Automatically set during Create phase |
| **active** | Production-ready | `status: active` | Automatically upgraded after first QualityGate pass |
| **deprecated** | Planned for deprecation | `status: deprecated` + `deprecated_date` + `successor` | Manually marked by human |
| **archived** | Archived, read-only | `status: archived` | Automatically archived 90 days after deprecated_date |

### 23.2 State Transitions

```
draft → active → deprecated → archived
                      ↓
              (successor takes over)
```

### 23.3 Deprecation Protocol

1. Mark `status: deprecated` + set `deprecated_date`
2. Add deprecation notice in the AIAP.md governance declaration section
3. If a replacement program exists, set the `successor` field
4. Deprecation window: remains available for at least 90 days after `deprecated_date`
5. Transitions to archived after the window period ends

### 23.4 Archival Protocol

AIAP programs in archived state:
- Retain complete directory structure, no files are deleted
- AIAP.md retains complete version history
- No longer accept Evolve/Modify operations
- Only Validate operations are allowed (for auditing)
- Executor should return WARNING + recommend successor when encountering an archived program

### 23.5 Creator Pipeline Stages (Reference Implementation)

Several sections of this specification (notably Appendix G.2.3) reference stages of the reference Creator implementation. These stage names are informative, not normative — any implementer-equivalent pipeline that enforces the same invariants is acceptable.

| Stage | Purpose |
|-------|---------|
| **ResearchStep** | Gathers context, existing quality baseline, and upstream standards |
| **EvolveStep** | Plans structural changes between version N and N+1 |
| **Generate** | Produces `.aisop.json` bodies per the evolution plan |
| **ModifyStep** | Applies targeted edits to pre-existing nodes |
| **ValidateStep** | Runs formal rules (MF / PL / I / C / D series) and integrity checks |
| **SimulateStep** | Dry-runs the program under sampled inputs |
| **ReviewPresent** | Presents diffs and detected changes to the human reviewer for approval; the gate where `sys.io.confirm` message-level changes are confirmed as semantically equivalent (Appendix G.2.2) |
| **ReviewFinalize** | Locks the version, updates AIAP.md version history, commits governance_hash |

### 23.6 Generator Pipeline `target_aiap_dir` Handoff

Generator-type pipelines (Creator Evolve / Create / Modify) produce or modify a **target** AIAP distinct from the pipeline's own AIAP. The executor's cache index (`.execution_cache/{turn_id}/_index.json`) SHOULD record the resolved target directory so downstream audit can verify the **generated artifact**, not only the **generator**.

**Field contract** (when a pipeline produces/modifies another AIAP):

```json
// .execution_cache/{turn_id}/_index.json
{
  ...
  "aiap_name": "soulbot_creator_evolution",
  "target_aiap_dir": "D:/.../aiap_store/soulbot_yijing_divination_aiap"
}
```

**Semantics**:
- **Optional field** — absent for non-generator pipelines (chat, direct tool use, etc.)
- **Absolute path** to the target AIAP directory (not filename, not relative)
- **Write point**: generator pipeline's earliest stage that resolves the target (e.g. `PipelineStart` in Creator) — MUST atomic-merge with existing `_index.json`
- **Read point**: pipeline end node (e.g. `endNode` in Creator's delegating engine) — when present, passes `--target_aiap_dir=<path>` to `pipeline_execution_ended.py` for Layer 3 two-phase audit:
  - **Phase 1**: self-check on pipeline's `--aiap_dir` (generator itself)
  - **Phase 2**: generated-output check on `--target_aiap_dir` (target governance_consistency + aiap_schema)
- **Modes that write this field**: Create, Evolve, Modify
- **Modes that SKIP**: Validate, Simulate, Compare, Explain, Discover, Deprecate, Export, Import, Package, Convert, General (standalone operations without a target)

**Rationale**: Without `target_aiap_dir`, the post-pipeline audit layer sees only the generator's own data (e.g. the generator's `quality_baseline.json`) rather than the freshly-written target AIAP. The `target_aiap_dir` handoff ensures **generated artifacts** are audited for governance compliance, closing the generator-output blindspot.

---

## 24. Orchestration Patterns

AIAP programs support four orchestration patterns, declared through semantic annotations in Mermaid flowcharts.

### 24.1 Pattern 1: Sequential

Already fully covered by the current AIAP Pipeline. Modules execute in the order defined by `-->` in the Mermaid flowchart.

```mermaid
Start --> ModuleA --> ModuleB --> ModuleC --> endNode
```

Applicable: Default pattern for Pattern A-E.

### 24.2 Pattern 2: Parallel

```mermaid
Start --> fork{Parallel Fork}
fork --> ModuleA
fork --> ModuleB
ModuleA --> join{Join}
ModuleB --> join
join --> End
```

- `fork` node distributes tasks to multiple modules
- `join` node waits for all concurrent modules to complete
- No data dependencies between concurrent modules
- Applicable: When independent subtasks can be processed in parallel

### 24.3 Pattern 3: Conditional

```mermaid
Start --> Classify{Classification}
Classify -->|Type A| ModuleA
Classify -->|Type B| ModuleB
Classify -->|Other| ModuleDefault
```

- Conditional branches are annotated using the `|label|` syntax on Classify nodes
- The current Mermaid flowchart already supports this syntax; no new format is needed
- Applicable: Intent routing, input type dispatching

### 24.4 Pattern 4: Handoff

Applicable for cross-component control transfer in Pattern F Ecosystem:

```
handoff_context = {
    "source": "component_a_aiap",
    "target": "component_b_aiap",
    "intent": "process_health_data",
    "payload": { ... },
    "metadata": { "timestamp": "...", "trace_id": "..." }
}
```

Process:
1. The initiator packages the complete context as `handoff_context`
2. The receiver restores state from `handoff_context`
3. The receiver returns `handoff_result` upon completion
4. The initiator confirms the result or initiates a new handoff

---

## Part V: Quality & Compatibility

---

## 25. Version Compatibility

### 25.1 Protocol Version Compatibility Guarantees

| Version Range | Compatibility Guarantee |
|---------|---------|
| AIAP V1.x.y | Backward compatible within the same major version |
| AIAP V2.0.0+ | May introduce breaking changes, migration guide provided |

### 25.2 Program Version Specification

AIAP program versions follow semver:

| Version Change | Meaning | Example |
|---------|------|------|
| **major** (x.0.0) | Breaking change — input/output format changes | 1.0.0 → 2.0.0 |
| **minor** (x.y.0) | New feature — backward compatible | 1.0.0 → 1.1.0 |
| **patch** (x.y.z) | Bug fix/improvement — backward compatible | 1.1.0 → 1.1.1 |

### 25.2.1 Pattern E — Standard Files Version Independence

Pattern E (Multi-Module) AIAP programs bundle two version lines:

1. **Program implementation version** — declared in `main.aisop.json` / `agent_card.json` / `quality_baseline.json` / `AIAP.md`, follows the program's own semver lifecycle.
2. **Protocol standard version** — declared in `AIAP_Standard.*.aisop.json` files (`.core` / `.security` / `.ecosystem` / `.performance` / `.runtime_extensions`), tracks the AIAP Protocol specification version.

**These two version lines MUST NOT be required to match.** The Standard files represent the **AIAP Protocol standard** the program complies with, not the program's own code version.

**Validator rule** (`governance_consistency._check_multi_file`):
- Filename pattern: files matching `AIAP_Standard.*.aisop.json` are **EXEMPT** from multi-file version uniformity check
- Non-Standard `.aisop.json` program modules (`main`, `advisor`, `generate`, etc.) **MUST** share the same version
- Version drift among program modules remains an ERROR (detects real bugs like forgotten file update)

**Rationale**: A program implementing AIAP Protocol v1.0.0 can iterate internally (v1.0.0 → v(N.M.P)) without needing to "re-version" the protocol standard it implements. Conflating the two yields false ERROR on every Pattern E AIAP.

### 25.3 Minimum Protocol Version

```yaml
# AIAP.md frontmatter
min_protocol_version: "AIAP V1.0.0"
```

The executor checks before loading a program: if the executor's supported protocol version < `min_protocol_version` → Reject loading + Prompt upgrade.

### 25.4 Version Changelog Format

It is recommended to use a structured format in the optional "Version History" section of AIAP.md:

```markdown
## Version History

### v1.2.0 (2026-03-01)
- **Added**: Monthly report trend analysis
- **Improved**: Query performance optimization

### v1.1.0 (2026-02-15)
- **Added**: Blood pressure recording feature
- **Fixed**: Date parsing boundary error
```

Change type labels: `Added` / `Improved` / `Fixed` / `Removed` / `Security`

---

## 26. Documentation Completeness Levels

### 26.1 Three-Tier Classification

| Level | Requirements | Applicable To |
|------|------|------|
| **Level 1** (Minimum) | AIAP.md required sections (Governance Declaration + Feature Overview + Usage) | All AIAP programs |
| **Level 2** (Recommended) | + Example Interactions + Applicable Conditions | Programs with `status=active` |
| **Level 3** (Complete) | + Error Handling + Version History + All optional fields | Programs published to Registry |

### 26.2 Checklist for Each Level

**Level 1 (Minimum)**:
```
[ ] AIAP.md exists
[ ] 13 required frontmatter fields are complete
[ ] Governance Declaration section exists
[ ] Feature Overview section exists
[ ] Usage section exists
[ ] Closing seal exists
```

**Level 2 (Recommended)**:
```
[ ] All Level 1 checks passed
[ ] Example Interactions section exists (1-3 scenarios)
[ ] Applicable Conditions section exists (applicable + not applicable)
[ ] quality optional fields are populated
[ ] status = active
```

**Level 3 (Complete)**:
```
[ ] All Level 2 checks passed
[ ] Error Handling section exists
[ ] Version History section exists (structured format)
[ ] trust_level is declared
[ ] permissions is declared (if trust_level >= T3)
[ ] runtime is declared
[ ] intent_examples is populated
[ ] governance_hash is computed
[ ] benchmark is populated
```

---

## Appendix A: PL24 Auto-Fix Protocol

Applicable: When AutoFixEngine generates fix proposals.

| Constraint | Description |
|------|------|
| **(a) SCOPE** | Fixes limited to 1-3 files, symbol changes ≤ 10, line changes ≤ 50 |
| **(b) CONFIDENCE** | Auto-apply when confidence ≥ 0.85, otherwise submit as suggestion requiring human approval |
| **(c) RATE LIMIT** | Maximum 1 auto-fix per object per day, to prevent infinite loops |
| **(d) AUDIT** | All auto-fixes logged to observability.lint_report |
| **(e) ROLLBACK** | All auto-fixes are rollbackable (git format) |
| **(f) NO LOGIC CHANGE** | Limited to format/style/missing declarations/version constraint fixes; algorithm or business logic changes are prohibited |

---

## Appendix B: PL25 License & Copyright Declaration

Applicable: All AIAP programs, especially for aiap-store distribution.

### B.1 Core Rules

| Rule | Description |
|------|------|
| **(a) LICENSE FIELD** | AIAP.md must include a `license` field |
| **(b) SPDX VALIDITY** | Value must be a valid SPDX identifier (e.g., "Apache-2.0", "MIT") or "proprietary" |
| **(c) PROPRIETARY** | When license is "proprietary", `terms_url` or `contact` must be provided |
| **(d) STORE** | The license field is mandatory for distribution through aiap-store |

### B.2 Field Attributes

| Attribute | Value |
|------|-----|
| Field Name | `license` |
| Type | `string` |
| Required | **Mandatory** (§3.1 required field) |
| Default | `proprietary` (treated as all rights reserved when not declared) |
| Format Specification | SPDX standard identifiers (see https://spdx.org/licenses/) |

### B.2.1 Companion Field: `copyright`

| Attribute | Value |
|------|-----|
| Field Name | `copyright` |
| Type | `string` |
| Required | Optional (§3.2 optional field) |
| Default | Empty (no copyright claim) |
| Format | Free-text copyright notice (e.g. `"Copyright 2026 AIXP Labs AIXP.dev"`) |

### B.3 Common SPDX Values Reference

| Value | Meaning |
|----|------|
| `MIT` | MIT License (most permissive) |
| `Apache-2.0` | Apache 2.0 (includes patent protection) |
| `GPL-3.0` | GPL v3 (strong copyleft) |
| `proprietary` | Proprietary / All rights reserved |
| `CC-BY-4.0` | Creative Commons Attribution (suitable for documentation-type programs) |

### B.4 Default Value Behavior

- The `license` field is **mandatory** (§3.1 required field)
- When not specified by user during creation, defaults to `proprietary`
- The `copyright` field is **optional** — when omitted, written as empty placeholder in AIAP.md for discoverability
- Does not affect existing program operation (backward compatible)

### B.5 Additional Requirements for `proprietary`

When `license: proprietary`, at least one of the following fields must be provided:

```yaml
license: proprietary
terms_url: https://example.com/terms   # or
contact: author@example.com            # at least one is required
```

### B.6 aiap-store Store Integration

aiap-store registry entries read and display the `license` field directly from AIAP.md:

```json
{
  "program_id": "publisher.domain/program_name",
  "version": "1.0.0",
  "license": "MIT",
  "store_url": "https://aiap.store/programs/publisher.domain/program_name"
}
```

Listing checks:
- Missing `license` field → Store registration API returns error, listing rejected
- `license: proprietary` without `terms_url`/`contact` → Listing rejected

### B.7 Backward Compatibility Guarantees

| Scenario | Behavior |
|------|------|
| Existing programs without a `license` field | Run normally, default treated as `proprietary` (should add field for compliance) |
| Local use without Store listing | Completely unaffected |
| Submitted to Store without `license` filled in | Store registration API returns error, listing rejected |
| Programs without `copyright` field | Run normally, no impact (optional field) |

---

## Appendix C: Category M — Tool Directory Simulation Scenarios (M1-M20)

Applicable: Pattern G programs.

| Scenario | Description | Expected |
|----------|-------------|----------|
| M1 | Normal MCP Server startup and tool invocation | **PASS** |
| M2 | MCP Server startup failure, degraded handling | **PASS** (graceful degradation) |
| M3 | Python dependency installation failure | **FAIL** (DEPENDENCY_ERROR) |
| M4 | MCP Server tool invocation timeout | **PASS** (timeout handling) |
| M5 | governance_hash mismatch (Code Trust Gate interception) | **FAIL** (INTEGRITY_VIOLATION) |
| M6 | ZIP SLIP attack (malicious paths in tool_dirs) | **FAIL** (SECURITY_VIOLATION) |
| M7 | Network permission violation (undeclared import requests) | **FAIL** (PERMISSION_VIOLATION) |
| M8 | Dependency version not pinned (TS ^ prefix detection) | **FAIL** (UNPINNED_DEPENDENCY) |
| M9 | go.sum missing | **FAIL** (INTEGRITY_VIOLATION) |
| M10 | Rust pre-compiled binary hash mismatch | **FAIL** (INTEGRITY_VIOLATION) |
| M11 | shell_tools present but trust_level < T4 | **FAIL** (TRUST_LEVEL_INSUFFICIENT) |
| M12 | Multi-language MCP Server partial startup failure | **PASS** (partial degradation) |
| M13 | aiap_tools sub-program normal load and execution | **PASS** |
| M14 | aiap_tools sub-program AIAP.md missing or invalid | **FAIL** (INVALID_AIAP_MD) |
| M15 | aiap_tools sub-program trust_level > parent (should intercept) | **FAIL** (TRUST_CEILING_VIOLATION) |
| M16 | aiap_tools sub-program governance_hash mismatch | **FAIL** (INTEGRITY_VIOLATION) |
| M17 | aiap_tools recursion depth exceeded (>3 layers) | **FAIL** (RECURSION_DEPTH_EXCEEDED) |
| M18 | aiap_tools sub-program permissions exceed parent scope | **FAIL** (PERMISSION_VIOLATION) |
| M19 | aiap_tools circular dependency detection (A→B→A) | **FAIL** (CIRCULAR_DEPENDENCY) |
| M20 | aiap_tools sub-program version incompatibility with parent protocol | **FAIL** (PROTOCOL_VERSION_INCOMPATIBLE) |

---

## Appendix D: NO_SELF_MODIFY Rule

AIAP programs are prohibited from modifying their own governance files at runtime. This rule applies unconditionally to all AIAP programs.

### D.1 Core Rule

> AIAP programs MUST NOT modify their own governance files at runtime. Any structural change to an AIAP program MUST go through the Creator Pipeline's full process (including human-confirmed EvolveStep). Violation of this rule is equivalent to an Axiom 0 breach.

### D.2 Protected Files (Blacklist)

| File Pattern | Description |
|------|------|
| `*.aisop.json` | All module files |
| `AIAP.md` | Project governance contract |
| `quality_baseline.json` | Quality baseline data |
| `agent_card.json` | Agent card metadata |
| `.version_history/*` | Version history records |
| Any file covered by `governance_hash` | Integrity-protected files |

### D.3 Allowed Writes (Whitelist)

| File | Condition |
|------|------|
| `insights.json` | Only when insights mechanism is enabled (see Appendix E), subject to write constraints |
| Program data files | Files declared in `side_effects` (e.g., user data, state files) |

### D.4 Rationale

1. Self-modification = departure from human sovereignty control (Axiom 0)
2. Self-modification = governance_hash invalidation = governance chain breakage
3. Self-modification = bypassing the 15-stage Pipeline's audit guarantees
4. LLM hallucination + self-modification = erroneous judgment directly becoming code changes

### D.5 Independence

NO_SELF_MODIFY is independent of the INSIGHTS mechanism. Even when INSIGHTS is not enabled, the self-modification prohibition is always in effect.

---

## Appendix E: INSIGHTS Mechanism — Optional Runtime Insight Recording

An optional mechanism for AIAP programs to record structural observations during runtime or pipeline execution. Default: not enabled.

### E.1 Activation

```yaml
# In AIAP.md optional fields:
insights: true
# or
insights:
  sources: [pipeline, runtime]  # select one or both
```

When the `insights` field does not exist in AIAP.md, the mechanism is not enabled (zero overhead).

### E.2 insights.json Schema

```json
{
  "program": "{program_name}",
  "version": "{current_version}",
  "warning": null,
  "insights": [
    {
      "id": "INS-001",
      "fingerprint": "string (deterministic, from title)",
      "category": "BUG | FUNC | ARCH | PERF | DEBT | USER | SEC | COMP",
      "severity": "HIGH | MEDIUM | LOW",
      "source": "runtime | pipeline:{stage_name}",
      "title": "string",
      "observation": "string (≤250 chars)",
      "impact": "string",
      "suggestion": "string (≤250 chars)",
      "status": "OPEN | ADOPTED | WONTFIX",
      "created": "YYYY-MM-DD",
      "occurrences": [
        { "version": "string", "mode": "EVOLVE | RUNTIME", "date": "YYYY-MM-DD" }
      ]
    }
  ]
}
```

### E.3 Category Definitions

| Category | Code | Description |
|------|------|------|
| Program Defect | BUG | Functional errors, logic contradictions, data flow breaks |
| Feature Gap/Redundancy | FUNC | Missing or obsolete features |
| Architecture Conflict | ARCH | Module responsibility overlap, circular dependencies |
| Performance & Resource | PERF | Response latency, token budget pressure, resource waste |
| Technical Debt | DEBT | Accumulated structural compromises, hardened workarounds |
| User Demand Signal | USER | User behavior patterns suggesting unmet needs |
| Security & Privacy | SEC | Data leak risks, permission violations, injection vectors |
| Compliance | COMP | Protocol violations, governance chain breaks |

### E.4 Write Constraints

| Writer | Permission |
|------|------|
| Runtime (insights.aisop.json / executor) | Strict append-only: add new entries or append occurrences only. Cannot modify/delete existing entries or change status. |
| Creator Pipeline (advisor insights sub-graph) | Can manage: add entries, modify status (OPEN→ADOPTED/WONTFIX with human confirmation), archive non-OPEN entries to .version_history/ |

### E.5 Fingerprint Deduplication

```
fingerprint = lowercase(title).replace(/[^a-z0-9_\u4e00-\u9fff]/g, '_').truncate(50)
```

Same fingerprint → do not add new entry, append to existing entry's `occurrences` array.

### E.6 Anti-Bloat Controls

| Layer | Mechanism |
|------|------|
| L1: Per-entry | observation + suggestion combined ≤ 500 characters |
| L2: Total | OPEN entries capped at 20; exceeding sets `warning` field |
| L3: Version archive | EVOLVE archives non-OPEN entries to `.version_history/v{old}/insights_archive.json` |

### E.7 insights.json is NOT included in governance_hash

insights.json is a dynamic runtime/pipeline artifact, not part of the static program definition. governance_hash covers only .aisop.json static files.

### E.8 Packaging

When packaging as .aiap: `insights.aisop.json` is included (module code), `insights.json` is excluded (runtime data).

---

## Appendix F: Node Gate — Node-Level Execution Assertion

### F.1 Purpose

AI agents executing multi-node AISOP programs tend to skip nodes despite global execution rules (e.g., `strict_semantics: zero_skip`). Global rules declared once at the start lose influence as context grows. Node Gate solves this by **inserting an assertion at every node entry**, refreshing AI attention at each step.

This is not a replacement for `strict_semantics` — it is the **per-node concretization** of the global rule. `strict_semantics` declares the intent; Node Gate asserts it at every node boundary.

### F.2 Mechanism

Every non-start node's first step (S1) MUST begin with an assertion:

**Single predecessor** (linear chain):
```
[ASSERT] {prev_node} executed. If false → go back to {prev_node}. | {step work}
```

**Multiple predecessors** (converge point — node has 2+ incoming Mermaid edges):
```
[ASSERT] {nodeA}∨{nodeB}∨{nodeC} executed. If false → go back to {primary_predecessor}. | {step work}
```

**With data dependency (Required):**

Single predecessor with Required:
```
[ASSERT] {prev_node} executed. Required: {field1}, {field2}. If false → go back to {prev_node}. | {step work}
```

Multiple predecessors with independent Required:
```
[ASSERT] {nodeA} executed. Required: {fieldA1}, {fieldA2}.
[ASSERT] {nodeB} executed. Required: {fieldB1}.
If false → go back to {primary_predecessor}. | {step work}
```

Required is OPTIONAL — omitting it preserves existing ASSERT behavior (execution status check only). Required fields are comma-separated names referring to data produced by the predecessor node's execution. When present, the assertion checks both execution status AND data availability.

Required serves three purposes:
1. **Validation** — Agent verifies required data fields exist before proceeding
2. **Selective context** — execution engine reads only referenced nodes' cached results, reducing context size
3. **Documentation** — makes implicit data dependencies explicit (data flow is visible from ASSERT alone)

The assertion and step work are separated by `|` and merged into one step — no `Do not proceed` terminator needed because the backtrack instruction already implies it. The `|` separator clearly delineates the gate from the step's normal work.

The `∨` (logical OR) operator means: at least one of the listed predecessors must have been executed. This covers converge points where a node can be reached from multiple paths (e.g., loop-back edges, conditional branches merging).

**Predecessor derivation rules:**

1. **Source of truth**: Parse the Mermaid `graph TD` definition. Every edge `A --> B` or `A -- label --> B` makes `A` a predecessor of `B`
2. **Single incoming edge**: Use `{prev_node}` directly — both in predicate and backtrack target
3. **Multiple incoming edges**: List ALL predecessors joined by `∨` in the predicate. The **primary predecessor** (backtrack target) is the node on the **main forward path** — typically the first edge in topological order, excluding loop-back and error-recovery edges
4. **Diamond (decision) nodes**: Edges from a diamond (e.g., `QualityGate -- Fail --> ModifyStep`) count as predecessors of the target. The diamond node name is used, not the edge label
5. **Self-loops and sub-graph entry**: If a node receives edges from both the current sub-graph and external entry (e.g., `Start(drill_down)`), list all sources with `∨`
6. **Cross-sub-graph delegation**: When a sub-graph's entry node receives delegation from another sub-graph's node (e.g., `PipelineEntry` in router delegates to `PipelineStart` in pipeline), the assert references the **delegating node**, not the local Start. The local Start is a trivial label — the true runtime predecessor is the delegating node
7. **Terminal node naming**: The terminal node MUST use the format `endNode((End))` — double parentheses for rounded shape, name `endNode`, label `End`. Variants (`End`, `end`, `Finish`) are non-standard and MUST be normalized

**Primary predecessor selection** (for backtrack target after `go back to`):

| Scenario | Primary predecessor |
|----------|-------------------|
| One main-path edge + loop-back edges | Main-path edge source |
| Multiple conditional branches merging | The branch on the default/happy path |
| All edges are equivalent (no clear primary) | First predecessor in Mermaid declaration order |

The assertion and S1's normal work are combined in one step — no additional step is created.

**Why ASSERT**: In programming, `assert` means "this condition MUST be true, otherwise execution stops." AI training data contains millions of assert statements with this exact semantics — the meaning is unambiguous: **condition false = cannot continue**.

### F.3 Backtrack Rules

- Assertion true → continue executing current node
- Assertion false (single predecessor) → return to `{prev_node}` and execute it fully
- Assertion false (multi-predecessor `∨`) → return to `{primary_predecessor}` and execute it fully. The `∨` predicate checks if ANY listed predecessor was executed; backtrack always targets the primary predecessor (main forward path)
- If `{prev_node}`'s own assertion also fails → continue backtracking to its predecessor
- Natural recursive backtracking with depth budget: max_backtrack_depth = min(3, node_count / 4). Exceeding budget → halt with diagnostic instead of infinite regress (inspired by ABC k-bounded recovery, arXiv 2602.22302)
- Worst case within budget: backtrack to the start node and re-execute from beginning
- Pipeline never fails due to backtracking within budget — it self-corrects. Beyond budget → structured failure with backtrack trace for debugging

### F.4 Why It Works

1. **ASSERT is a programming primitive** — AI recognizes `assert` as a hard stop, not a suggestion. Unlike "please be honest" (a request), `assert` is a **command with defined failure semantics**
2. **Per-node repetition** — global rules suffer attention decay; per-node assertions refresh attention at every boundary
3. **Backtrack is correction, not punishment** — assertion failure triggers re-execution, not error. AI has a legitimate path: go back and do the work
4. **Minimal token cost** — one line per node, ~10 tokens
5. **Academic validation** — Node Gate aligns with established research:
   - **AgentSpec (ICSE 2026, ICSE 2026, arXiv 2503.18666)**: Runtime enforcement via three-tuple `trigger → predicate → enforcement`. Node Gate implements this as: trigger=node entry, predicate=predecessor executed, enforcement=backtrack
   - **ProgPrompt**: Assertions in prompts as pre-conditions with recovery actions. Node Gate uses `[ASSERT]` as pre-condition and backtracking as recovery
   - **Attention decay research**: Global instructions lose influence as context grows; per-node assertions counter this by refreshing constraints at every boundary

### F.5 Assert Pattern (AgentSpec Three-Tuple)

Each Node Gate assertion follows the AgentSpec enforcement model:

| Element | Node Gate Mapping |
|---------|-------------------|
| **Trigger** | Node entry (first step S1) |
| **Predicate** | `{prev_node}` (single) or `{nodeA}∨{nodeB}∨...` (multi) was fully executed |
| **Enforcement** | Backtrack to `{prev_node}` or `{primary_predecessor}` and re-execute |

This three-tuple is embedded directly into each node's S1, requiring no external runtime or monitoring infrastructure. The AI itself serves as both evaluator and enforcer — leveraging `assert` semantics from its training data.

### F.6 Implementation in .aisop.json

**Single predecessor** (linear chain):
```json
{
  "EvolveStep": {
    "step1": "[ASSERT] Research1 executed. If false → go back to Research1. | Based on research findings, plan fixes...",
    "step2": "Execute fixes...",
    "step3": "Verify fix results..."
  }
}
```

**Multiple predecessors** (converge point):
```json
{
  "ModifyStep": {
    "step1": "[ASSERT] Research2∨QualityGate∨PostSimulateGate executed. If false → go back to Research2. | Apply quality fixes..."
  }
}
```

**With Required** (data dependency declaration):
```json
{
  "Research2": {
    "step1": "[ASSERT] Generate1 executed. Required: weighted_score, test_report. If false → go back to Generate1. | Analyze quality of generated draft..."
  }
}
```

**Multiple predecessors with independent Required:**
```json
{
  "ValidateStep": {
    "step1": "[ASSERT] NihilDensityStep executed. Required: gate_result, nihil_report. [ASSERT] Research3 executed. Required: compliance_notes. If false → go back to NihilDensityStep. | Run comprehensive validation..."
  }
}
```

### F.7 Applicability

| Node count | Requirement |
|-----------|-------------|
| 6+ nodes | REQUIRED |
| 3-5 nodes | RECOMMENDED |
| 1-2 nodes | OPTIONAL |

Regardless of node count, Node Gate is REQUIRED if the program contains QualityGate nodes, self-evolution pipelines, or Trust Level T3+ operations.

### F.8 Relationship to Existing Execution Mechanisms

| Mechanism | Scope | Function |
|-----------|-------|----------|
| `strict_semantics` | Global | Declares "no skipping" intent |
| `step_completion_attestation` | Per-stage | Records execution proof |
| `pipeline_integrity_chain` | Cross-stage | Hash-chains execution audit trail |
| **Node Gate (ASSERT)** | **Per-node entry** | **Asserts predecessor execution + self-corrects via backtrack** |

Node Gate complements (not replaces) existing mechanisms. It adds the missing layer: **per-node execution assertion with a self-correction path**.

### F.9 Compliance Check

MF28-MF31 are formally defined in `AIAP_Standard.core.aisop.json` → `multi_file_guidelines.rules`.
The JSON definitions are authoritative. Below is a summary for quick reference:

- **MF28** Node Gate Completeness (YELLOW) — non-start node S1 must contain [ASSERT] with correct predecessor references
- **MF28b** Node Gate Required Consistency (YELLOW WARNING, OPTIONAL) — if [ASSERT] declares Required, verify: (a) declared fields exist in predecessor's execution record, (b) step text data references align with Required declaration. Only checked when Required clause is present. A YELLOW-severity finding: the executor reports the misalignment but does not abort execution. Creator pipelines SHOULD surface it in ReviewPresent.
- **MF29** Version Sync (RED) — cross-file version consistency with auto-correction to AIAP.md
- **MF30** Score Consistency (YELLOW) — quality score sync between AIAP.md and quality_baseline
- **MF31** Mermaid-Function Consistency (YELLOW) — graph nodes ↔ function keys alignment

### F.10 Relationship with sys.assert (AISOP V1.0.0)

`[ASSERT]` and `sys.assert` are two different mechanisms:

| | [ASSERT] | sys.assert |
|-|----------|-----------|
| **Location** | Node S1 (entry point) | Any step |
| **Purpose** | Execution order guarantee + data dependency | Data correctness check |
| **Evaluation** | AI understanding | Deterministic expression engine |
| **On failure** | Backtrack to predecessor | Throw `assertion_error` |
| **Scope** | Node entry (fixed position) | Any step (flexible position) |
| **Required** | Supported (data dependency declaration) | Not supported (checks condition values) |
| **Protocol layer** | AIAP (governance rule) | AISOP (language primitive) |

**Recommended usage** — separate into distinct steps:

```json
{
  "step1": "[ASSERT] PreviousStep executed. Required: account_id. If false → go back to PreviousStep. | Proceed with account processing",
  "step2": "sys.assert('account_id != null', 'Account ID required')"
}
```

Separation rationale:
- step1 is processed by AI ([ASSERT] + natural language)
- step2 is processed by runtime (sys.assert, deterministic)
- Clear separation of responsibilities; does not violate the one-step-one-mode rule (MF33)

`[ASSERT]` is not `sys.*` — it is an AIAP governance marker (AI-processed). `sys.assert` is an AISOP system call (runtime-deterministic).

---

## Appendix G: sys.* System Call Governance (AISOP V1.0.0)

### G.1 Overview

This appendix defines AIAP governance rules for the use of AISOP V1.0.0 `sys.*` system calls (§6). `sys.*` calls are protocol-level operations processed deterministically by the runtime, not through LLM reasoning. AIAP governance ensures `sys.*` usage is safe, consistent, and auditable.

**Scope:** All AIAP programs containing `sys.*` steps. Programs without `sys.*` steps are not affected by this appendix.

**Relationship with AISOP:** AISOP §6 defines `sys.*` syntax and semantics (language level). Appendix G defines `sys.*` governance rules (rules level). AISOP specifies "what you can use"; AIAP specifies "how you should use it."

**Contents of this appendix:**

- G.2 `sys.io.confirm` Immutable Governance (Axiom 0 Enforcement)
- G.3 `sys.assert` Governance
- G.4 `sys.run` / `sys.code` Security Governance
- G.4b `sys.llm` Governance
- G.5 `sys.io.input` / `sys.io.select`
- G.5c `sys.io.notify` / `sys.io.print`
- G.6 `sys.state` State Governance
- G.7 `sys.event` Event Governance
- G.8 `sys.security` Audit Governance
- G.9 Step Mode Governance (one-step-one-mode rule)
- G.10 `sys.*` Interaction with RESERVED_KEYS

### G.2 sys.io.confirm Immutable Governance (Axiom 0 Enforcement)

#### G.2.1 Immutability Principles

`sys.io.confirm` inherits the inviolable properties of Axiom 0:

1. **Cannot be bypassed** — no runtime optimization, LLM discretion, or auto-execution may skip it
2. **Cannot be deleted** — evolution must not delete existing `sys.io.confirm` steps
3. **Cannot be weakened** — evolution must not reduce the protection level of `sys.io.confirm`
4. **Immutable propagation** — `sys.io.confirm` in sub-programs is equally protected

#### G.2.2 Evolution Constraints

When an AIAP program evolves from version N to version N+1:

```
confirm_list_N  = set of all sys.io.confirm steps in version N
confirm_list_N1 = set of all sys.io.confirm steps in version N+1

Rule: confirm_list_N ⊆ confirm_list_N1
Meaning: only additions allowed, not deletions
Violation: FATAL — abort evolution
```

**Comparison key:** The first argument (message string) of `sys.io.confirm`. Comparison scans across all files, not bound to node names or step positions.
- Node renaming does not affect the check (as long as the message exists, it passes)
- Semantically equivalent rewording of messages is not treated as deletion (e.g., "Delete all?" → "Delete all data?"). Creator should display message changes in ReviewPresent for user to confirm equivalence
- Complete disappearance of a message = deletion → triggers FATAL

**Exception:** If the entire node containing `sys.io.confirm` is removed (function removal), the removal itself must be confirmed via `sys.io.confirm` or explicit user approval in the evolution pipeline.

#### G.2.3 Formal Rule Reference and Creator Execution

The immutability requirements above are codified in `AIAP_Standard.core.aisop.json` → `multi_file_guidelines.rules.MF32` (RED severity, `axiom_0_enforcement: true`). The JSON definition is authoritative for machine verification; this section is the human-readable statement of the same rule.

**MF32 summary:** evolving program MUST preserve every `sys.io.confirm` message from version N in version N+1. Comparison key = first argument (message string), scanned across all files. Semantic rewording must be confirmed equivalent in ReviewPresent. Complete disappearance = FATAL.

Creator pipeline responsibilities (reference implementation; see §23.5 for stage definitions):

- **EvolveStep:** Check that the confirm list does not decrease
- **Generate:** Preserve all existing `sys.io.confirm` steps
- **ValidateStep:** Verify MF32 (confirm immutability) — failure is FATAL, halts the pipeline
- **ReviewPresent:** Display `sys.io.confirm` list and changes; human confirms any message rewording is semantically equivalent

#### G.2.4 Relationship with Trust Levels and Nested Programs

- **T3 (Supervised):** `sys.io.confirm` is the protocol-level standardization of T3's "requires human approval". T3 programs SHOULD use `sys.io.confirm` for high-risk operations. Programs with `sys.io.confirm` but no audit capability → I14 WARNING.
- **T4 (Autonomous):** `sys.io.confirm` remains forced-blocking during autonomous execution. T4 does NOT mean "skip sys.io.confirm". T4 autonomy is limited to steps without `sys.io.confirm`. This is the direct embodiment of Axiom 0: human sovereignty > autonomous execution.

**Propagation across Pattern D / Pattern F sub-programs.** MF32 applies **per program**: a program's evolution is compared against its own prior version, not its parent's or sibling's. However, the immutable-propagation guarantee of Axiom 0 means a parent program MUST NOT structurally bypass a sub-program's `sys.io.confirm` — e.g. replacing a `RUN aisop.sub_with_confirm` call with a direct inlined path that omits the confirm step. In practice: when a Pattern F ecosystem or Pattern D parent evolves, ValidateStep must additionally verify that every sub-program's `sys.io.confirm` remains reachable along the parent's invocation graph. Unreachable-but-still-declared `sys.io.confirm` is treated as effective deletion → FATAL.

#### G.2.5 Migration Guidance

**New programs:**
- Safety-critical confirmations MUST use `sys.io.confirm`
- General interactive confirmations SHOULD use `sys.io.confirm`
- Only `sys.io.confirm` has Axiom 0 immutable protection

**Existing programs:**
- During evolution, SHOULD migrate natural-language confirmations to `sys.io.confirm`
- Example: `"Ask user to confirm before deployment"` → `"sys.io.confirm('Proceed with deployment?')"`
- Once migrated, the `sys.io.confirm` is immediately protected by MF32

**Limitations of natural-language confirmations:**
- AI may skip them (attention decay)
- Executor cannot deterministically identify them (requires LLM to judge whether confirmation is needed)
- Not protected by Axiom 0 (evolution can delete them)

### G.3 sys.assert Governance

#### G.3.1 Relationship with Existing Assertion Mechanisms

Three-layer assertion system:

| Mechanism | Level | Evaluation | On Failure |
|-----------|-------|-----------|------------|
| `constraints` | Function-level | AI understanding | AI "should" comply |
| `[ASSERT]` | Node entry | AI understanding | Backtrack to predecessor |
| `sys.assert` | Step-level | Deterministic | Runtime abort immediately |

Complementary relationships:
- `constraints` = behavioral guidance ("you should")
- `[ASSERT]` = execution order guarantee ("predecessor must complete") + data dependency (Required)
- `sys.assert` = data correctness check ("condition must be true")

All three can coexist without conflict:
```
constraints: "Account ID must be valid"
[ASSERT]: "PreviousStep executed. Required: account_id"
step3: "sys.assert('account_id != null', 'Account ID required')"
```

#### G.3.2 Usage Guidance

**When to use `sys.assert`:**
- Safety-critical conditions (data integrity, permission checks) → MUST
- Conditions checkable with deterministic expressions → RECOMMENDED
- When failure must immediately abort execution → MUST

**When to use `constraints`:**
- Behavioral guidance (output format, style requirements) → constraints
- Conditions not checkable by expression (semantic judgment) → constraints

**When to use `[ASSERT]`:**
- Node execution order guarantee → `[ASSERT]` (always)
- Data dependency declaration → `[ASSERT] Required` (selective)

#### G.3.3 Expression Syntax Constraints

`sys.assert` expressions must conform to AISOP §6.11:
- Comparison: `==`, `!=`, `>`, `<`, `>=`, `<=`
- Logic: `&&`, `||`, `!`
- Null check: `!= null`, `== null`
- Member access: `.`

Not allowed: function calls, complex arithmetic, string operations, AI reasoning (natural language conditions).

### G.4 sys.run / sys.code Security Governance

#### G.4.1 Permission Mapping

- `sys.run` executes system commands → subject to §17 `permissions.shell` constraints
- `sys.code.exec` / `sys.code.eval` executes code → subject to §17 `permissions` + sandbox constraints
- `sys.io.read/write` operates files → subject to §17 `permissions.file_system` constraints

Mapping rules:
- `permissions.shell.allowed = false` → program must not use `sys.run`
- `permissions.network.allowed = false` → `sys.run` must not contain network operations
- `permissions.file_system.scope = "./data/"` → `sys.io.read/write` limited to `./data/`

Violation → FATAL (§20 Error Handling).

Modules containing `sys.io.write` SHOULD declare `side_effects: [file_write]`. Modules containing `sys.run` SHOULD declare `side_effects: [shell_exec]`. This follows naturally from §3.4 module specification.

#### G.4.2 High-Risk Command Auto-Confirmation

When `sys.run` executes high-risk commands, the executor SHOULD auto-trigger `sys.io.confirm`:
- File deletion (rm, del, rmdir)
- Database operations (DROP, DELETE, TRUNCATE)
- System operations (shutdown, reboot, kill)
- Permission changes (chmod, chown, icacls)
- Irreversible operations (git push --force, git reset --hard)

Program authors may also explicitly add `sys.io.confirm`:
```json
"step1": "sys.io.confirm('About to delete all data. Confirm?')",
"step2": "sys.run('rm -rf ./output/')"
```

Explicit > implicit: if the program already has `sys.io.confirm`, the executor does not auto-add another.

#### G.4.3 Code Execution Sandbox

`sys.code.exec` / `sys.code.eval` security constraints (consistent with AISOP §6.7):
- Sandbox required: isolated file system, network, resources
- Language allowlist: runtime maintains a list of permitted languages
- Resource limits: memory and CPU time limits
- High-risk detection: destructive operations auto-trigger `sys.io.confirm`

`sys.code.eval` shares security constraints with `sys.code.exec`. Its expression syntax shares the AISOP §6.11 engine with `sys.assert`.

### G.4b sys.llm Governance

#### G.4b.1 Permission Constraints

`sys.llm` explicitly invokes external models:
- Subject to §17 `permissions.network` constraints
- `permissions.network.allowed = false` → `sys.llm` is prohibited
- `permissions.network.endpoints` → restricts callable model APIs

#### G.4b.2 Usage Guidance

**When to use `sys.llm` (explicit model invocation):**
- Need to specify a particular model (e.g., `model='gpt-4'`)
- Need to control parameters (temperature, max_tokens)
- Need structured output (`sys.llm.json` with schema)
- Need classification (`sys.llm.classify`)

**When to use natural language steps:**
- Current Agent context execution is sufficient
- No need to specify model or parameters
- Natural language reasoning tasks

#### G.4b.3 Security Recommendations

When using `sys.llm` in safety-critical operations:
- SHOULD use low temperature (higher determinism)
- SHOULD declare allowed model list in `constraints`
- `sys.llm` output SHOULD be verified via `sys.assert` before use

### G.5 sys.io.input / sys.io.select Governance

#### G.5.1 User Interaction Governance

`sys.io.input` / `sys.io.select` belong to the same forced-blocking category as `sys.io.confirm` (AISOP §6.1):
- Pause execution, wait for user response
- Cannot be skipped, cannot be auto-filled with default values

Distinction from `sys.io.confirm`:
- `sys.io.confirm` → inviolable (Axiom 0: cannot be deleted/weakened/bypassed)
- `sys.io.input/select` → forced-blocking but no Axiom 0 immutability constraint (evolution may delete input/select, but cannot delete confirm)

#### G.5.2 Input Validation

User input obtained via `sys.io.input` SHOULD be validated with `sys.assert` in subsequent steps:

```json
"step1": "sys.io.input('Enter file path') -> path",
"step2": "sys.assert('path != null', 'Path is required')",
"step3": "sys.io.read(path) -> content"
```

This is defensive programming, not a mandatory requirement.

### G.5c sys.io.notify / sys.io.print

Non-blocking operations with no special AIAP governance requirements.

- `sys.io.notify('message')` — executor should forward content to user
- `sys.io.print('message')` — executor should log content

No Axiom 0 constraints. No permission restrictions. Evolution may freely add or remove. No MF rules or security checks required.

### G.6 sys.state State Governance

#### G.6.1 Relationship with Execution Cache

The AIAP executor currently uses split-file cache: `.execution_cache/{N}/{aiap_name}.{NodeName}.json`

`sys.state` is protocol-level state management:
- `sys.state.save()` = persist checkpoint
- `sys.state.load()` = restore checkpoint
- `sys.state.get/set` = read/write state within node

The execution cache is one implementation of `sys.state`. When `sys.state.save` fires → executor writes cache. When `sys.state.load` fires → executor restores from cache.

#### G.6.2 Checkpoint Governance

**Governance requirements (AIAP level):**
- Round-trip integrity: `sys.state.save()` → `sys.state.load()` must restore to an equivalent state
- No impact on completed nodes: `load` must not corrupt already-PASS node caches
- Auditable: checkpoint creation and restoration SHOULD be logged

**Implementation details (executor decides):**
- Specific content and storage format of checkpoints
- Storage location (execution cache directory or other)
- Checkpoint cleanup and expiration policy

### G.7 sys.event Event Governance

#### G.7.1 Event System Scope

`sys.event.emit/wait` provides cross-node event communication:
- `emit` = non-blocking, send event
- `wait` = blocking, wait for event (with optional timeout)

Use cases:
- `sys.run.bg` starts background process → `sys.event.wait` waits for completion
- Synchronization between parallel branches
- External webhook triggers

#### G.7.2 Governance Rules

- Event names: must be unique within the same execution instance, recommend `snake_case`
- Timeout: `sys.event.wait` SHOULD declare timeout
- `sys.event.wait` without timeout → WARNING (may wait indefinitely)

### G.8 sys.security Audit Governance

#### G.8.1 Audit Requirements

`sys.security.audit()` writes to audit log:
- Cannot be deleted
- Cannot be modified
- Storage location determined by executor (independent of execution cache)

`sys.io.confirm` audit:
- Every invocation automatically writes to audit log
- Includes: call arguments + user response + timestamp
- Not affected by `sys.security.redact()`

#### G.8.2 Data Redaction

`sys.security.redact(type)`:
- Replaces sensitive data in output
- `type` specifies redaction type (credit_card, ssn, email, etc.)
- Redaction occurs at output stage, does not affect internal processing

### G.9 Step Mode Governance

#### G.9.1 One-Step-One-Mode Rule (consistent with AISOP §5.3)

This rule is codified as **MF33** (YELLOW severity) in `AIAP_Standard.core.aisop.json` → `multi_file_guidelines.rules.MF33`. The JSON definition is authoritative.

Each step must be exactly one of:
1. `sys.*` system call
2. `RUN aisop.*` sub-task invocation
3. Natural language instruction

Mixing is not allowed:
- `"Analyze data, sys.assert('count > 0')"` ← prohibited
- `"sys.io.read('file.txt'), then process"` ← prohibited

Correct:
```json
"step1": "sys.io.read('file.txt') -> data",
"step2": "Analyze data in data variable"
```

Note: the `[ASSERT]` prefix on node entry steps is exempt from MF33 — it is an AIAP governance marker (§F Node Gate), not a `sys.*` call.

#### G.9.2 Return Value Rules

Variable names:
- Must be unique within the same node (no duplicate definitions)
- `snake_case` naming
- Only valid in subsequent steps of the current node

References:
- Only reference variables defined in prior steps (-> return values)
- Do not reference variables from other nodes (use `output_mapping` or `sys.state.set` for cross-node transfer)

#### G.9.3 sys.* Execution Dispatch

The specific execution method for `sys.*` calls is determined by the AISOP specification and the executor. AIAP imposes only one hard rule:

> `sys.io.confirm` / `sys.io.input` / `sys.io.select` MUST be handled directly by the executor, and must NOT be delegated to an AI Agent for autonomous judgment. This is an Axiom 0 enforcement requirement per AISOP §6.2.

Note: `execute_mode` is a language-level field defined in AISOP §5.2.8 and is not within the scope of the AIAP protocol.

### G.10 sys.* Interaction with RESERVED_KEYS

#### G.10.1 context_filter

`context_filter` filters node input context (data passed between nodes). `->` variables are step-level variables (return values from sys.* calls within the node). They operate in different scopes → `context_filter` does not affect `->` variables. When `sys.assert` references `->` variables, it is not affected by `context_filter` exclusions.

#### G.10.2 retry_policy

`retry_policy` is a node-level mechanism. When a node contains non-retryable sys.* steps:
- `sys.io.confirm` failure → does not trigger node-level retry, goes directly to `on_error`
- `sys.assert` failure → does not trigger node-level retry (deterministic failure)
- `sys.run/sys.code` failure → may trigger node-level retry
- Natural language step failure → may trigger node-level retry

Principle: `retry_policy` only applies to RECOVERABLE errors. FATAL types skip retry.

#### G.10.3 output_mapping

`output_mapping` is node-level (cross-node transfer). `->` variables are step-level (valid within node, destroyed after node completes). They are complementary:
- `->` variables for passing between steps within a node
- `output_mapping` for passing node results to the next node
- To transfer a `->` variable to the next node → use `sys.state.set` or include it in the final step output

#### G.10.4 constraints

The complementary relationship between `constraints` and `sys.assert` is explained in G.3.1. `constraints` does not affect `sys.*` execution behavior. `sys.*` does not replace `constraints` (each has its own applicable scenarios).

#### G.10.5 map / join

- `sys.io.confirm` within a `map` iteration → each iteration confirms independently (executor decides presentation)
- `sys.io.confirm` in parallel `join` branches → each branch confirms independently (executor decides order)
- AIAP does not constrain the presentation of concurrent confirmations.

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
