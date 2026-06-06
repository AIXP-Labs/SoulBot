# Changelog

All notable changes to soulbot_execute_engine are documented in this file.

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
