# Changelog

All notable changes to soulbot_execute_engine are documented in this file.

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
