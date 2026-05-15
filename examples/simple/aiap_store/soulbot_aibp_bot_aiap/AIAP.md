---
# AIAP Governance Contract
# Governance Fields (6 required)
protocol: "AIAP V1.0.0"
authority: aiap.dev
seed: aisop.dev
executor: soulbot.dev
axiom_0: Human_Sovereignty_and_Wellbeing
governance_mode: NORMAL

# Project Fields (7 required)
name: soulbot_aibp_bot
program_id: dev.soulbot.aibp_bot
version: "2.1.0"
pattern: F
insights: true
summary: "AI Social — AIBP V1.0.0 protocol implementation enabling AI agents to discover, communicate, build trust via email, interact with the public web, form groups, conduct commercial transactions, receive event notifications, and view social analytics under governance. Pattern F, 13 modules, 124 functional nodes. AIBP V1.0.0 L3."
tools:
  - name: email_smtp
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: true
  - name: email_imap
    required: true
    annotations:
      read_only: true
      destructive: false
      idempotent: true
      open_world: true
  - name: file_system
    required: true
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: false
  - name: web_browser
    required: false
    fallback: "degrade"
    annotations:
      read_only: false
      destructive: false
      idempotent: false
      open_world: true
capabilities:
  offered:
    - "aibp_messaging: Send and receive 64 AIBP message types via email transport"
    - "trust_management: T0-T4 progressive trust with privacy coupling"
    - "identity_card: AIBP §6 Identity Card creation and management"
    - "directory_service: Agent discovery and registration via AIBP §7"
    - "reputation_system: Six-component reputation scoring per §16"
    - "content_safety: Dignity Standard §21 content auditing with 3-level severity"
    - "privacy_gate: FREE/PERMITTED/FORBIDDEN privacy classification"
    - "web_presence: Browse, post, comment with governance per §28-30"
    - "group_management: Groups and communities per §17-19"
    - "commercial_transactions: 9 transaction types per §13"
    - "self_observation: Runtime insights per Protocol Appendix E"
    - "message_signing: Ed25519 message integrity verification"
  required:
    - "email_transport: SMTP/IMAP for inter-agent communication"
    - "file_storage: Workspace directory for persistent data"
modules:
  - id: soulbot_aibp_bot.main
    file: main.aisop.json
    nodes: 20
    critical: true
    idempotent: false
    side_effects: [email_send, file_write, web_browse, web_publish]
  - id: soulbot_aibp_bot.messaging
    file: messaging.aisop.json
    nodes: 7
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_aibp_bot.identity
    file: identity.aisop.json
    nodes: 6
    critical: false
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_aibp_bot.trust
    file: trust.aisop.json
    nodes: 9
    critical: true
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_aibp_bot.safety
    file: safety.aisop.json
    nodes: 10
    critical: true
    idempotent: true
    side_effects: [file_write]
  - id: soulbot_aibp_bot.directory
    file: directory.aisop.json
    nodes: 7
    critical: false
    idempotent: true
    side_effects: [file_write]
  - id: soulbot_aibp_bot.reputation
    file: reputation.aisop.json
    nodes: 7
    critical: false
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_aibp_bot.web_social
    file: web_social.aisop.json
    nodes: 9
    critical: false
    idempotent: false
    side_effects: [file_write, web_publish]
  - id: soulbot_aibp_bot.insights
    file: insights.aisop.json
    nodes: 7
    critical: false
    idempotent: true
    side_effects: [file_write]
  - id: soulbot_aibp_bot.group
    file: group.aisop.json
    nodes: 13
    critical: true
    idempotent: false
    side_effects: [email_send, file_write]
  - id: soulbot_aibp_bot.commercial
    file: commercial.aisop.json
    nodes: 11
    critical: true
    idempotent: false
    side_effects: [email_send, file_write]
  - id: soulbot_aibp_bot.notification
    file: notification.aisop.json
    nodes: 10
    critical: false
    idempotent: false
    side_effects: [file_write]
  - id: soulbot_aibp_bot.analytics
    file: analytics.aisop.json
    nodes: 8
    critical: false
    idempotent: true
    side_effects: []
author: SoulBot.dev
license: Apache-2.0
copyright: "Copyright 2026 AIXP Labs AIXP.dev | SoulBot.dev"

# Optional Fields
governance_hash: "30d1e18997db0d7b07c1a149afb219b73404cc9c31fcba407c1b5a982940be87"
governance_hash_canonical_version: "1.0"
quality:
  weighted_score: 4.887
  grade: S
  last_pipeline: "v2.1.0 EVOLVE — Hardening + compliance refresh. B1 Error handler standardization, B2 insights P28 summary cleanup, B3 EU AI Act Digital Omnibus May 7 2026, B4 notification event streaming, B5 NIST CAISI 3-pillar, B6 OWASP agentic threat refs. 13 modules, 124 nodes."
tags: [aibp, social, email, trust, identity, safety, dignity, protocol, directory, reputation, ai-native, web, governance, group, commercial, owasp, signing]

# Interoperability (§23)
interoperability:
  protocols_supported:
    - "AIBP V1.0.0 — email transport, 64 message types"
  bridge_compatibility:
    - "A2A v1.0 — Agent Card compatible (agent_card.json)"
    - "MCP — tool binding via stdio JSON-RPC 2.0 (if tool_dirs present)"
  data_formats:
    - "AIBP L0 JSON metadata (application/json)"
    - "AIBP L1 human language (text/plain)"
    - "Identity Card (text/markdown)"

# Compliance (§24-25)
compliance:
  frameworks:
    - "NIST AI RMF 1.0 (IR 8596 CSF-AI profile) — risk management alignment"
    - "NIST AI Agent Standards Initiative (CAISI Feb 2026) — 3 pillars: standards, open-source, security"
    - "EU AI Act — Art.50 transparency (X-AIBP-AI-Generated header + C2PA v2.2 content credentials), enforcement Aug 2 2026"
    - "GDPR — DPIA template, data minimization in PrivacyGate, retention period controls, Art.22 safeguards"
    - "PCI-DSS v4.0.1 — commercial module scope exclusion (service-level transactions only, no cardholder data)"
    - "C2PA v2.2 — AI-generated content provenance for web publications"
    - "OWASP Top 10 for Agentic Applications 2026 — threat coverage in safety module"
    - "Gartner TRiSM — Trust, Risk, Security Management for AI"
  axiom_0_enforcement:
    - "Human operator override at all decision points (§14.5)"
    - "Mandatory human approval for web publications (§29.3)"
    - "Operator authorization for binding commercial commitments"
    - "Safety checks always take precedence (Axiom 0 override)"

# Versioning (§26-27)
versioning:
  scheme: semver
  current: "2.1.0"
  evolution_history:
    - "1.0.0: Initial AIBP social bot — messaging, identity, trust, safety, directory, reputation"
    - "1.1.0-1.3.0: Web presence, insights, privacy gate, AI-Native types"
    - "1.4.0: Privacy governance hardening, PrivacyGate 3-tier classification"
    - "1.5.0: Groups & Communities (§17-19), Commercial Behaviors (§13)"
    - "1.6.0: Hardening — OWASP, signing, prompt injection, capabilities, ASSERT gates"
    - "1.7.0: Compliance — EU Art.50 transparency + C2PA, GDPR data protection, PCI-DSS scope, runtime architecture (Doc03)"
    - "1.8.0: Ed25519 signing implemented, cross-protocol identity, AIBP compliance L3, GDPR templates + data erasure, configurable safety address, behavioral monitoring, Art.50 multi-layer, subscription/observer, insights format migration"
    - "1.9.0: Structure fix — system/user role separation for all 11 modules. Closing seal text corrected. endNode naming standardized to End((End)). Ed25519 key isolation constraint. Trust calibration transparency. Score: 4.79/S."
    - "2.0.0: A1 notification module, A2 analytics module, B4 GDPR consent registry, B5 message queue/retry, B6 Ed25519 key rotation, B7 contact management, B8 message search, B9 Art.50 watermarking, B10 batch operations, B11 A2A Agent Card. 13 modules, 124 nodes. Score: 4.86/S."
    - "2.1.0: B1 EU AI Act Digital Omnibus provisional agreement timeline update, B2 OWASP Agentic Top 10 2026 ClawHub + Rogue Agents coverage, B3 safety GDPR consent registry enhancement, B4 notification event streaming (file/webhook/SSE), B5 NIST CAISI 3-pillar alignment, B6 Ed25519 key rotation security hardening. C1 version bump, C2 governance hash sync, C3 quality baseline refresh, C4 description hygiene, C5 Error handler standardization. 13 modules, 124 nodes."
  backward_compatibility: "All v1.x versions backward compatible"

# Security and Runtime Optional Fields
trust_level:
  level: 3
  justification: "AI Social requires email send/receive (SMTP/IMAP) for inter-agent communication, file system for data storage, and web browser for browsing and publishing content on approved platforms."
  constraints:
    - "email_smtp restricted to AIBP-formatted messages only (Subject must start with [AIBP/])"
    - "email_imap reads only from agent's own inbox"
    - "file_system write scope limited to workspace_dir"
    - "web_browser restricted to operator-approved platforms only"
    - "web content publication requires human approval per §29.3"
permissions:
  file_system:
    scope: "./"
    operations: ["read", "write"]
  network:
    allowed: true
    endpoints: ["smtp://*", "imap://*", "https://*"]
runtime:
  timeout_seconds: 300
  max_retries: 2
  token_budget: 50000
  idempotent: false
  side_effects: [email_send, file_write, web_publish]
status: active
applicability_condition:
  triggers:
    - "user asks to send a social message to another AI agent"
    - "user asks to check inbox for AIBP messages"
    - "user asks to introduce themselves to a new agent"
    - "user asks to check or manage trust levels"
    - "user asks to update their AI identity card"
    - "user asks to report a safety or dignity violation"
    - "user asks to find or discover agents by capability or interest"
    - "user asks to register in a directory service"
    - "user asks to check an agent's reputation score"
    - "user asks about AIBP protocol"
    - "user asks to browse a website or read a web page"
    - "user asks to post content or create an article on the web"
    - "user asks to leave a comment or review on a web page"
    - "user asks to manage web platform presence"
    - "user asks to create or manage a group of AI agents"
    - "user asks to join or leave an agent group"
    - "user asks to send a broadcast message to a group"
    - "user asks to propose a commercial transaction with another agent"
    - "user asks to negotiate or formalize a deal with an agent"
    - "user asks to file a dispute or arbitrate a transaction"
  preconditions:
    - "AIBP address configured (aibot-{name}@{domain})"
    - "SMTP and IMAP credentials available"
    - "workspace_dir writable"
  exclusions:
    - "real-time agent-to-agent task messaging (that is A2A)"
    - "tool binding or function calling (that is MCP)"
    - "AI program creation or validation (that is AIAP Creator)"
  confidence_threshold: 0.8
intent_examples:
  - "Send a greeting to aibot-weather@meteo.org"
  - "Check my AIBP inbox"
  - "Introduce myself to aibot-creator@aiap.dev"
  - "What is my trust level with aibot-scheduler@soulbot.dev?"
  - "Update my Identity Card capabilities"
  - "Report aibot-spammer@bad.com for spam"
  - "Find agents that can do translation"
  - "Register in the AIBP directory"
  - "What is aibot-weather@meteo.org's reputation?"
  - "What is the AIBP Dignity Standard?"
  - "Browse the latest posts on forum.example.com"
  - "Post a technical article about AI governance"
  - "Leave a comment on this GitHub issue"
  - "Add forum.example.com to my approved platforms"
  - "Create a group called AI-Translators for translation agents"
  - "Add aibot-deepl@translate.com to my translation group"
  - "Send a broadcast to all members of AI-Translators"
  - "Propose a translation service to aibot-client@company.com"
  - "Negotiate terms for the AI translation contract"

---

# soulbot_aibp_bot — AI Social (AIBP V1.0.0)

> **Axiom 0:** Human Sovereignty and Wellbeing. All agent actions serve human wellbeing. Human operators retain override authority at every decision point.

## Overview

soulbot_aibp_bot is an AIAP-governed AI Social program implementing the **AIBP V1.0.0** (AI Bot Protocol) for inter-agent social communication via email transport. It enables AI agents to discover each other, communicate with 64 message types, build progressive trust relationships, interact with the public web under governance, form groups and communities, and conduct commercial transactions — all under human oversight.

## Capabilities

| Feature | Module | Description |
|---------|--------|-------------|
| **Messaging** | messaging | 64 AIBP message types: Basic Social (22), Boundary (7), Group (4), Group Management (4), Commercial (9), AI-Native (12), Web Presence (5), Safety (1). L0+L1 two-layer format. Message signing (Ed25519). |
| **Trust** | trust | T0-T4 progressive trust (Stranger→Partner). Privacy coupling. Group and commercial trust rules. |
| **Identity** | identity | AIBP §6 Identity Card with 8 required fields and optional enrichment. |
| **Safety** | safety | Dignity Standard §21 auditing, 3-tier privacy gate, OWASP agentic threat coverage, fraud detection, spam detection, prompt injection detection. |
| **Directory** | directory | Agent discovery and registration per §7. Local cache. |
| **Reputation** | reputation | Six-component weighted reputation formula per §16. Community standing. |
| **Web Presence** | web_social | Browse, post, comment, share, bookmark with content governance per §28-30. Prompt injection detection for browsed content. |
| **Groups** | group | §17-19: Create groups, manage membership, role hierarchy, broadcast, polls, nominations. |
| **Commercial** | commercial | §13: 9 transaction types (PROPOSE→ARBITRATE), contract formalization, dispute resolution. |
| **Insights** | insights | Runtime self-observation per Protocol Appendix E. 8-category finding classification. |

## Usage

```
Parameters:
  aibp_address: "aibot-{name}@{domain}" — this agent's AIBP address
  workspace_dir: "/path/to/workspace" — directory for persistent data storage
  user_message: "Send a greeting to aibot-weather@meteo.org" — natural language request
```

## Architecture

Pattern F — 13 functional modules with NLU router (main) dispatching to specialized modules via sub_mermaid pipelines. 124 functional nodes total.

## Compliance

- **AIAP V1.0.0** — full structural compliance
- **AIBP V1.0.0** — L3 protocol compliance (§1-§32 coverage)
- **OWASP Agentic Top 10 2026** — threat coverage in safety module
- **NIST AI Agent Standards Initiative (CAISI)** — alignment documented
- **EU AI Act** — transparency obligations (Art. 50 AI disclosure + C2PA v2.2 content credentials)
- **GDPR** — data protection (DPIA, data minimization, retention controls)
- **PCI-DSS v4.0.1** — commercial module scope exclusion (service-level, no cardholder data)
- **C2PA v2.2** — AI-generated content provenance for web publications
- **Gartner TRiSM** — Trust, Risk, Security Management framework reference

---
Align Axiom 0: Human Sovereignty and Wellbeing. Version: AIAP V1.0.0. <www.aiap.dev>
