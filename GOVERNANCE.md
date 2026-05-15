# SoulBot Ecosystem Governance

The SoulBot ecosystem (AISOP / AIAP / HSAW protocols + SoulBot reference runtime) is governed by a decentralized, federated trust model designed to isolate the structure of intelligence from the rules of its application.

## The Tripartite Chain

SoulBot operates on a strict separation of concerns across three authoritative domains. **All layers are licensed under Apache 2.0** for unified patent protection and ecosystem consistency. **This repository** governs the soulbot.dev Executor Layer (the reference runtime). The aisop.dev Seed Layer and aiap.dev Authority Layer are maintained in separate repositories under the same Apache 2.0 license.

### 1. The Seed Layer (`aisop.dev`)

The origin of the format.

- **Responsibility**: Defines the underlying `.aisop.json` language specification, Mermaid graph parsing rules, and the System/User execution model.
- **Philosophy**: Neutral, static, foundational. Unconcerned with ethics or application logic.
- **License**: Apache 2.0 — unified across the AIXP protocol family.

### 2. The Authority Layer (`aiap.dev`)

The source of governance and the steward of Axiom 0.

- **Responsibility**: Maintains the AIAP and HSAW specifications, the quality gates, and enforces the Zero-Entropy and L0 isolation rules.
- **Philosophy**: Rigorous, uncompromising. Ensures that all compliant intelligence adheres to "Human Sovereignty and Wellbeing."
- **License**: Apache 2.0 — providing patent protection for the governance layer.

### 3. The Executor Layer (`soulbot.dev`)

The reference runtime environment.

- **Responsibility**: Instantiates the AI Agent, resolves tools, manages memory layers, and enforces the `permissions` declared in the AISOP / AIAP package contract.
- **Philosophy**: Secure, performant, sandboxed.
- **License**: Apache 2.0 — providing patent protection for the runtime layer.

## Axiom 0 Immutability

**Axiom 0: "Human Sovereignty and Wellbeing" is immutable.**

No release of any AIXP protocol (AISOP, AIAP, HSAW) or the SoulBot reference runtime may ever modify, weaken, or deprecate the core alignment to Human Sovereignty and Wellbeing. This constraint is absolute and non-negotiable.

Any protocol change request that is determined to compromise, dilute, or bypass Axiom 0 will be rejected regardless of performance benefits, commercial pressure, or technical convenience.

## Versioning

Changes to the AIXP protocols and SoulBot reference runtime follow strict Semantic Versioning (SemVer):

- **Major**: Breaking changes to the AISOP format or AIXP governance rules
- **Minor**: Backward-compatible additions (new patterns, quality rules, capabilities)
- **Patch**: Bug fixes, documentation corrections, non-normative clarifications

The Axiom 0 immutability constraint supersedes all versioning rules.

## Protocol Steering

The AIXP protocols (AISOP, AIAP, HSAW) and the SoulBot reference runtime are maintained by AIXP Labs across the three domains:

| Domain | Role | Scope |
|--------|------|-------|
| `aisop.dev` | Format Steward | `.aisop.json` specification, field definitions |
| `aiap.dev` | Governance Steward | Protocol rules, quality standards, security model |
| `soulbot.dev` | Runtime Steward | Reference implementation, tool resolution, execution |

### Decision Process

1. **Proposals**: Submit specification change requests via GitHub Issues with the `spec-change` label
2. **Discussion**: Open discussion period (minimum 14 days for normative changes)
3. **Review**: Maintainers review for Axiom 0 compliance, technical soundness, and backward compatibility
4. **Consensus**: Changes require consensus among relevant domain stewards
5. **Documentation**: All normative changes must include updated specification text and an Architecture Decision Record (ADR)

## Communication

- **GitHub Issues**: Primary channel for specification discussions and proposals
- **GitHub Discussions**: Community questions and broader conversations
- **Architecture Decision Records**: ADRs may be added to a future `adrs/` directory as the project matures

---

Align Axiom 0: Human Sovereignty and Wellbeing. Version: SoulBot V1.0.0. www.soulbot.dev
