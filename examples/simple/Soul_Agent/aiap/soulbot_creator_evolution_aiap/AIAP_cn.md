---
# AIAP Governance Contract
# 治理字段 (6 个必需)
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

# 项目字段 (8 个必需)
name: aiap_creator
version: "2.34.0"
pattern: D
flow_format: "mermaid"
summary: "AIAP Creator — 通过 18 阶段 Pipeline 创建、进化、验证、模拟和管理 AIAP 程序。15 个模块，213 个节点，1167 个场景 (A-AJ)。Pattern D，Grade S (4.972)。支持 Create/Evolve/Modify/Validate/Simulate/Compare/Discover/Deprecate/Export/Import/Explain/Package/Convert 工作流。ThreeDimTest 质量评分, governance_hash canonical v1.0。v2.34.0: A1 EvolveStep user_gate=true + A2 ValidateStep user_gate=false + A3 ReviewPresent user_gate=conditional（G1 误报消除）。governance_hash TRI-SYNC 已验证。"
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

# 可选字段
governance_hash: 01854f9cd0c23d75b11d2b9e7be08488534c1af052ab75dcd5a6c862642a14f6
governance_hash_canonical_version: "1.0"
quality:
  weighted_score: 4.972
  grade: S
  last_pipeline: "1c17901a-a71b-42b2-8d37-fc2959fd77d1"
  changes_v1_95_0: "6 LEVEL_B + 8 LEVEL_C: B1 AIAP.md simulate 节点数 18->14。B2 AIAP.md modify 节点数 12->10。B3 SimulateStep 委派参数完整性 (research_context, evolution_context, quality_baseline, research_quality_context)。B4 MCP/A2A/NIST/EU AI Act 引用时间戳刷新 (ProtocolAlign + Research3)。B5 MCP Tool Annotations 最佳实践对齐。B6 总节点数 213->207 校准 (AIAP.md)。C1 版本同步 15/15, C2 名称同步 10/10, C3 AIAP.md (第 61 次), C4 agent_card.json, C5 quality_baseline, C6 governance hash, C7 protocol_config, C8 AIAP_cn.md 同步。14 项变更。MAINTENANCE 第 61 次。"
  changes_v1_94_0: "4 LEVEL_B + 6 LEVEL_C: B1 Engine v4.5 (确定性循环拒绝、WAITING_USER 冲突守卫、effort_per_step、InlineExec 透传、跨平台 os.replace、[ASSERT] 前向引用阻塞、混合程序分类)。B2 Engine Router v1.2 (match/classify/endNode constraints)。B3 Router v3.1 (match/classify/execute/endNode constraints)。B4 Engine fractal_exempt 节点数修正 (25->27, main 20 + react 7)。C1 版本同步 10/10, C2 AIAP.md (第 60 次), C3 agent_card.json, C4 quality_baseline, C5 governance hash, C6 名称同步。10 项变更。MAINTENANCE 第 60 次。"
  changes_v1_93_0: "5 LEVEL_B + 6 LEVEL_C: B1 Engine v4.4 版本引用同步 (v4.3->v4.4)。B2 Engine v4.4 normal 模式感知 (NormalResolve, NormalAgentExec/FUNCTION_LOOP, NormalResultVerify, NormalNodeComplete)。B3 Engine Router v1.1 编排协议 (CheckMode 路由)。B4 prompt_template FUNCTION_LOOP MODE 生成支持 (sys.io.confirm 中断, [ASSERT] 内存读取, 子模块检查, 循环警告)。B5 双路由器架构同步 (Router v3.0 + Engine Router v1.1)。C1 版本同步 10/10, C2 AIAP.md (第 59 次), C3 agent_card.json, C4 quality_baseline, C5 governance hash, C6 名称同步。11 项变更。MAINTENANCE 第 59 次。"
  changes_v1_78_0: "5 LEVEL_B + 6 LEVEL_C: B1 calibration_convergence 10th CHECK (CONFIRMED STABLE, ccv=62, plateau 8 consecutive), B2 NIST AI RMF alignment update, B3 EU AI Act compliance reference update, B4 bootstrap_advisory update, B5 NihilDensity trend monitoring. C1-C6 version sync 10/10 creator modules + AIAP.md + agent_card + quality_baseline + protocol_config metadata. 11 changes, 11 effective, 100%. ThreeDimTest: C=5.00, I=5.00, D=5.00, weighted=5.00/S. MAINTENANCE 44th."
  changes_v1_79_0: "5 LEVEL_B + 9 LEVEL_C: B1 REMOVE steps_summary (2 nodes, 1 sub_mermaid, 6 refs), B2 Y6 recertification PASS (217 Error fields), B3 autonomy 30th + triple sync 31st CONFIRMED, B4 MCP/A2A AAIF refs, B5 EU AI Act Aug 2026 + NIST IR 8596 refs. C1-C9 version sync + metadata + fractal_exempt + node counts. 14 changes, 14 effective, 100%. ThreeDimTest: C=5.00, I=5.00, D=5.00, weighted=5.00/S. NihilDensity 10/10 GREEN aggregate 0.0195. MAINTENANCE 45th."
  changes_v1_80_0: "5 LEVEL_B + 9 LEVEL_C: B1 execute_mode auto-assignment in generate step8_1, B2 Bootstrap 53rd CHECK INTACT, B3 NIST ref, B4 EU ref, B5 A2A/MCP refs. I11 execution_mode fix (10 modules). C1-C9 version sync + metadata. ThreeDimTest: C=5.00, I=5.00, D=5.00, weighted=5.00/S. NihilDensity 10/10 GREEN aggregate 0.0359. 121/121 sim PASS. MAINTENANCE 46th."
  changes_v1_81_0: "5 LEVEL_B + 9 LEVEL_C: B1 ValidateStep EXECUTE_MODE_VALIDATION step7, B2 ReviewPresent EXECUTE_MODE_SUMMARY step6, B3 EvolveStep user execute_mode override step8, B4 calibration 11th CHECK, B5 NIST/EU/MCP+A2A refs. Q4+Q6 fixes. C1-C9 version sync + metadata. ThreeDimTest: C=5.00, I=5.00, D=5.00, weighted=5.00/S. NihilDensity 10/10 GREEN aggregate 0.0312. 150 sim (148 PASS, 2 YELLOW). MAINTENANCE 47th."
  changes_v1_82_0: "7 LEVEL_B + 9 LEVEL_C: B1 protocol_config version sync fix (1.80.0->1.82.0), B2 scenario coverage gap documentation (26/1023 unexecuted categorized), B3 EU Digital Omnibus trilogue update, B4 NIST Agent Standards update, B5 MCP 2026 roadmap, B6 A2A v0.3 three-binding, B7 json_schema for 3 modules. C1-C9 version sync + metadata + governance hash. 16 changes, 16 effective, 100%. ThreeDimTest: C=5.000, I=4.923, D=5.000, weighted=4.965/S. NihilDensity 10/10 GREEN aggregate 0.0126 (-59.6%). MAINTENANCE 48th."
  changes_v1_83_0: "7 LEVEL_B + 10 LEVEL_C: B1 A2A v1.0 reference update (v0.3->v1.0 across main, advisor, ecosystem), B2 Y7 anti-pattern recertification (PASS, 15 modules, 213 nodes, 217 Error fields), B3 Autonomy 32nd CHECK (CONFIRMED, bayesian 0.938, stable_duration 27), B4 Triple subsystem sync 33rd CHECK (autonomy+cache+steady_state CONFIRMED), B5 NIST Agent Standards update (benchmark draft closed, identity draft Apr 2, listening sessions Apr 2026), B6 json_schema expansion 3->7 modules (modify, review, simulate, nihil_density added, I10 4->5 recovered), B7 EU AI Act trilogue status (last trilogue Apr 28, Cypriot Presidency May 2026 target). C1-C10 version sync + metadata + governance hash. 17 changes, 17 effective, 100%. MAINTENANCE 49th."
  changes_v1_89_0: "7 LEVEL_B + 5 LEVEL_C: B1 Autonomy CHECK 36th CONFIRMED (bayesian 0.938, stable_duration 29, 73 consecutive 100%). B2 Triple subsystem sync 36th CHECK CONFIRMED. B3 NIST listening sessions Apr 2026. B4 EU Omnibus Apr 28 trilogue tracking. B5 MCP Q2 enterprise auth. B6 AGENTS.md convention. B7 ICLR 2026 self-improvement alignment. C1 version sync 10/10, C2 AIAP.md (55th), C3 agent_card.json, C4 quality_baseline, C5 governance hash. 12 changes. ThreeDimTest: C=4.857, I=5.000, D=4.950, weighted=4.949/S. MAINTENANCE 55th."
  changes_v1_88_0: "5 LEVEL_B + 5 LEVEL_C: B1 NIST AI Agent Standards alignment update (three-pillar framework operational, benchmark closed Mar 31, identity Apr 2, listening sessions Apr 2026). B2 EU Digital Omnibus trilogue outcome tracking (569-45 vote, Apr 28 trilogue, Annex III Dec 2027, penalties 35M/7%). B3 MCP 2026 roadmap update (Server Cards, Streamable HTTP, enterprise auth, SEPs June 2026). B4 Autonomy CHECK 35th SKIP. B5 Agentic pipeline hardening documentation. C1 version sync 10/10, C2 governance hash, C3 quality_baseline, C4 AIAP.md+agent_card.json, C5 triple sync SKIP. 10 changes, 10 effective, 100%. ThreeDimTest: C=4.857, I=5.000, D=4.950, weighted=4.949/S (post-Finalize adjusted, D6/D9 recovered to 5.0, D8 remains 4.5). NihilDensity 10/10 GREEN aggregate 0.0007 (-95.6%). 152/152 sim PASS. MAINTENANCE 54th."
  changes_v1_87_0: "3 LEVEL_A + 4 LEVEL_B + 1 LEVEL_C: A1 MF31c terminal fix (3 non-standard in generate), A2 STEP-KEY normalization (13 keys across 4 modules), A3 ERR-PAT verified fixed. B1 Y8 recertification PASS (213 Error fields), B2 Autonomy 34th CHECK CONFIRMED, B3 Triple sync 34th CONFIRMED, B4 MF31c terminal standardization. C1 version sync 10/10. ThreeDimTest: C=4.929, I=5.000, D=5.000, weighted=4.982/S. NihilDensity 4/4 GREEN aggregate 0.0158. 315/315 sim PASS. MAINTENANCE 53rd."
  changes_v1_86_0: "5 LEVEL_B + 4 LEVEL_C: B1 fix stale A2A v0.3 refs in advisor (2 refs updated to v1.0-compatible phrasing). B2 json_schema expansion to 3 remaining modules (advisor, convert, observability — I10 recovery). B3 NIST Agent Standards post-March 2026 update. B4 EU AI Act Digital Omnibus trilogue update. B5 MCP 2026 roadmap. C1 version sync, C2 governance hash, C3 AIAP.md+agent_card.json metadata, C4 quality_baseline. A2A-Y1 AIAP.md stale ref fixed (v0.3->v1.0). ThreeDimTest: C=4.857, I=4.923, D=5.000, weighted=4.930/S. NihilDensity 10/10 GREEN aggregate 0.0108 (-84.3%). 1167/1167 sim PASS. MAINTENANCE 52nd."
  changes_v1_85_0: "3 LEVEL_B + 5 LEVEL_C: B1 ASSERT_REQUIRED_ASSIGNMENT auto-generation (generate step8_2), B2 MF28b Required consistency validation (ValidateStep step8), B3 ASSERT Required display (ReviewPresent step7 + PresentDraft step6). C1-C5 version sync + metadata. ThreeDimTest: C=5.00, I=5.00, D=5.00, weighted=4.94/S. NihilDensity 10/10 GREEN. 213/213 sim PASS. MAINTENANCE 51st."
  changes_v1_84_0: "1 LEVEL_B + 5 LEVEL_C: B1 ASSERT Required format upgrade (213 ASSERTs across 10 modules per Protocol Section F.2 — explicit data dependency declarations enabling MF28b checking, selective context loading). C1 version sync, C2 name update, C3 governance hash, C4 quality_baseline, C5 fractal_exempt. ThreeDimTest: C=4.86, I=4.92, D=5.00, weighted=4.92/S. NihilDensity 10/10 GREEN. MAINTENANCE 50th."
tags: [aiap, creator, pipeline, governance, meta, execution, strict_mode, density_metrics, strict_semantics, self_evolution, dsm, token_efficiency, evolution_fitness, attestation, insights, quality, threedimscore]
author: SoulBot.dev
license: Apache-2.0
copyright: "Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev"

# 安全与运行时可选字段
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

# 工程化可选字段
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
  - "创建一个个人支出追踪器 AIAP 程序"
  - "将 health_tracker 从 v1.1 进化到 v1.2"
  - "修改 recipe_finder 的搜索模块"
  - "验证 expense_tracker 的代码质量"
  - "模拟 travel_planner 的执行路径"
  - "查找有没有健康相关的 AIAP 程序"
  - "弃用 old_tracker 程序"
  - "将 recipe_finder 导出为 SKILL.md"
  - "从 SKILL.md 导入一个技能作为 AIAP 程序"
  - "将 health_tracker 的工具映射到 MCP 协议"
  - "从远程注册表搜索健康相关的 AIAP 程序"
  - "将 health_tracker 打包为 .aiap 文件"
  - "解包并验证 recipe_finder_v1.0.0.aiap"
  - "为 health_tracker 添加 Dashboard UI 组件"
discovery_keywords: [aiap, creator, aisop, pipeline, evolve, generate, validate, simulate, skill, discover, deprecate, export, import, mcp, registry, adapter, package, pack, capability, ui, dashboard, agent_card, migration, auto_fix, a2a, license, store, safety_card, insights, self_observation, execution_config, strict_mode, density_metrics, strict_semantics, self_evolution, dsm, token_efficiency, attestation, fitness, quality, governance, threedimscore, pattern_g, pattern_d]
dependencies:
  - file: AIAP_Protocol.md
    required: true
    description: "AIAP protocol specification used by ReadTemplate and research modules"
min_protocol_version: "AIAP V1.0.0"
identity:
  program_id: "aiap.dev/aiap_creator"
  publisher: "AIXP Labs AIXP.dev | SoulBot.dev"
  verified_on: "2026-06-04"
benchmark:
  threedimscore: 4.972
  grade: "S"
  simulation_coverage: "A(16)+B(13)+C(10)+D(10)+E(13)+F(8)+G(10)+H(14)+J(4)+K(7)+L(2)+M(22)+N(5)+O(6)+P(10)+Q(12)+R(404)+S(20)+T(19)+U(14)+V(18)+W(12)+X(21)+Y(11)+Z(16)+AA(22)+AB(29)+AC(37)+AD(40)+AE(35)+AF(38)+AG(40)+AH(38)+AI(45)+AJ(2) = 1023 scenarios"
  total_nodes: 213
  pass_rate: "997/997 (100%) — 0 RED, 10 YELLOW_accepted"
---

## 治理声明

AIAP Creator 是 AIAP 协议的参考实现和自举工具。本程序遵循 AIAP V1.0.0 协议，
以 Axiom 0 (Human Sovereignty and Wellbeing) 为不可变公理，通过三域治理链
(aisop.dev → aiap.dev → soulbot.dev) 确保所有产出对齐人类主权与福祉。

AIAP Creator 自身是一个 AIAP 程序 (自举属性)——它创建 AIAP 程序，同时自身也遵循
所有 AIAP 规则。

## 功能概述

AIAP Creator 通过 15 模块 (213 节点)、18 阶段 Pipeline（含自动 ProtocolAlign、NihilDensityStep、ReviewPresent + ReviewFinalize）管理 AIAP 程序的完整生命周期：

| 意图 | 说明 | Pipeline |
|------|------|----------|
| **Create** | 创建新的 AIAP 程序 | Research → Evolve → Generate → Modify → QualityGate → Validate → Simulate → PostSimulateGate → Observability → Review |
| **Evolve** | 进化现有 AIAP 程序 | 同 Create (带增量差异分析) |
| **Modify** | 修改特定模块 | Research(quality) → Modify → Generate → Validate → [Simulate] → [PostSimulateGate] → Review |
| **Validate** | 验证代码质量 | ThreeDimTest 33+ 项检查 (C1-C7, I1-I13, D1-D10) |
| **Simulate** | 模拟执行路径 | 路径追踪 + 场景覆盖 (Categories A-X) |
| **Compare** | 对比两个版本 | 并排差异展示 |
| **Discover** | 搜索现有程序 | 工作区扫描 + 联邦注册表查询 + 语义匹配 + 关联推荐 |
| **Deprecate** | 弃用/归档程序 | 状态转换 + 迁移指南生成 |
| **Export** | 导出为 SKILL.md | AIAP→SKILL.md 字段映射 + 治理元数据保留 |
| **Import** | 从 SKILL.md 导入 | SKILL.md→AIAP 骨架生成 + 治理默认值填充 |
| **Explain** | 解释 AIAP 概念 | 内联知识回答 |
| **Package** | 打包/解包程序 | advisor package 子图 (pack → .aiap / unpack → verify) |
| **Convert** | 格式转换 | Mermaid↔JSON Flow 双向转换，自动方向检测，§4 拓扑变换，round-trip 验证 |

### 模块架构 (Pattern D)

- **main.aisop.json** — Pipeline 编排器 (33 节点, 2 sub_mermaid: main 15 + pipeline 18, hybrid normal/node mode)
- **protocol_config.json** — 协议元数据配置 (执行、密度指标、严格语义、自进化验证、DSM、token 效率、容量监控)
- **generate.aisop.json** — 生成器 (26 功能节点, sub_mermaid 架构, MF1-MF38 跨模块审计)
- **research.aisop.json** — 共享研究模块 (16 节点, fractal_exempt, 3 模式复用)
- **modify.aisop.json** — 修改器 (10 节点, 节点数已校准)
- **review.aisop.json** — 审查器 (12 节点, +AutoFixEngine)
- **simulate.aisop.json** — 模拟器 (14 节点, +YellowRemediationGuide, +ContractCheck, 委派参数完整性)
- **observability.aisop.json** — 遥测分析 (10 节点)
- **nihil_density.aisop.json** — 内容卫生分析 (13 节点, GH1-GH7 规则, 三色闸门)
- **convert.aisop.json** — 格式转换器 (17 节点, Mermaid↔JSON Flow 双向转换)
- **advisor.aisop.json** — 高级顾问 (62 节点, fractal_exempt, 9 子图)
- **AIAP_Standard.core.aisop.json** — 核心质量标准
- **AIAP_Standard.security.aisop.json** — 安全扩展
- **AIAP_Standard.ecosystem.aisop.json** — 生态扩展
- **AIAP_Standard.performance.aisop.json** — 性能扩展
- **AIAP_Standard.runtime_extensions.aisop.json** — 运行时扩展

## 使用方式

### 入口文件

`main.aisop.json` — AI Agent 加载此文件启动 AIAP Creator。

### 工具需求

| 工具 | 必需 | 用途 |
|------|------|------|
| file_system | 是 | 读写 AISOP 文件 |
| web_search | 否 | 研究阶段搜索最佳实践 |
| web_fetch | 否 | 深度网页研究 |

### 前置条件

- 目标目录中包含 AIAP_Standard.core.aisop.json (及扩展文件) 和 AIAP_Protocol.md
- AI Agent 支持 file_system 工具

## 示例交互

**场景 1: 创建新程序**
- 用户: "创建一个个人支出追踪器 AIAP 程序"
- Agent: 执行完整 Pipeline → 生成 expense_tracker_aiap/ 目录含 AIAP.md + main + 模块

**场景 2: 进化现有程序**
- 用户: "将 health_tracker 从 v1.1 进化到 v1.2，添加月度报告功能"
- Agent: 分析现有结构 → 提议 LEVEL_A/B 变更 → 用户确认 → 生成新版本

**场景 3: 验证质量**
- 用户: "验证 recipe_finder 的代码质量"
- Agent: 运行 ThreeDimTest → 输出三维成绩 + 流量分级

## 适用条件

**适用**: 创建、进化、修改、验证、模拟、搜索、弃用 AIAP 程序；SKILL.md 双向转换；MCP 工具映射；联邦注册表发现 (含 MCP/A2A 端点发现)；AIAP 打包/解包 (含 tool_dirs 目录和 Code Trust Gate)；UI 组件声明生成；Pattern G 嵌入式工具目录 (tool_dirs) 验证与自动生成；Pattern E/F→G 迁移指导；自动修复提案生成与应用；YELLOW 持久化追踪与修复指南；自动化质量验证 (lint_report)；MCP 2025 对齐 (Tasks primitive, Elicitation, Extensions, AAIF governance)；A2A v1.0 对齐 (JSON-RPC/gRPC/REST multi-binding, JWS signed Agent Cards, Linux Foundation AAIF governance)；Safety Card 生成 (risk_level, data_handling, limitations in agent_card.json)；NIST AI Agent Standards Initiative 参考；NihilDensity 内容卫生 (GH1-GH7)；多语言同步
**不适用**: 直接执行 AIAP 程序 (那是 SoulBot 执行器的职责)；非 AISOP 格式项目

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. www.aiap.dev
