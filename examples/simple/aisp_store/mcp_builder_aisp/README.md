<!-- generated_from_aisp: true -->
<!-- source: aisp.aisop.json -->
<!-- generator: tools/aisp_readme.py -->

# MCP Server Builder

This README is a deterministic projection of `aisp.aisop.json`. The contract remains the source of truth.

## Identity

| Field | Value |
| --- | --- |
| Skill ID | `mcp_builder_aisp` |
| Version | `2.0.0` |
| Protocol | `AISP V1.0.0` |
| License | `Apache-2.0` |
| Risk Level | `medium` |
| Category | code-generation |
| Tags | mcp, mcp-server, fastmcp, typescript-sdk, python-sdk, tool-design, code-generation, evaluation, read-only-eval |

## Purpose

AISP V1.0.0 skill that guides building MCP servers in Python (FastMCP) or Node/TypeScript SDK via the four-phase flow Research-and-Plan -> Implement -> Review-and-Test -> Create-Evaluations, producing a server plus a read-only evaluation suite. Nine sys.assert/tools-bound non-negotiable rules cover strict schemas, tool annotations, actionable errors, offset pagination, no-stdout-on-stdio, read-only evals, open-world docs, http-auth presence, and allow-list-only (default-deny) SSRF egress.

## When To Use

- The user wants to build an MCP (Model Context Protocol) server that lets an LLM call an external service or API through well-designed tools.
- The user is writing an MCP server in Python with FastMCP or in Node/TypeScript with the MCP SDK and wants the recommended structure, strict input schemas, annotations, error handling, and pagination.
- The user wants the full MCP-builder workflow: research/plan the tools, implement the server, review and build/test it, and create an evaluation suite.
- The user needs to author MCP evaluation questions (read-only, complex, string-verifiable) and emit them as evaluation XML.
- The user wants to wrap a documented REST/HTTP API as MCP tools with correct readOnlyHint/destructiveHint/idempotentHint/openWorldHint annotations.

## When Not To Use

- The user wants generic (non-MCP) application or API code generation with no MCP server involved.
- The user wants to run destructive or state-mutating operations against a live MCP server's backend as part of evaluation (evaluations here are strictly read-only / non-destructive).
- The user wants to operate, monitor, or deploy an already-running production MCP server rather than author a new one.
- The user wants the external MCP/SDK documentation bundled as static offline content rather than fetched on demand (these docs are open-world / runtime-fetched).
- The user wants the skill to modify its own bundled reference documents or any source material (the references are read-only).

## How To Run

With an AISOP runtime:

1. Load `aisp.aisop.json`.
2. Read `user.content.aisp_contract` before execution.
3. Run `user.content.aisop.main` exactly as declared.
4. Enforce every `non_negotiable` rule and every referenced `sys.*` mechanism.
5. Treat `sys.io.confirm` and other human-confirmation gates as blocking controls.

With a generic AI or non-AISOP agent:

- Treat this README as bootstrap guidance only.
- Verify external provenance or obtain explicit human approval before executing an untrusted package.
- Load the contract from `aisp.aisop.json`; do not treat this README as authoritative.
- Follow `RUN aisop.main` and the non-negotiable rules on a best-effort basis.
- Hard guarantees such as `sys.assert`, tool gating, and `sys.io.confirm` exist only in a conforming AISOP runtime.

## Non-Negotiable Rules

| Rule | Enforced By |
| --- | --- |
| NN1 — Evaluation questions MUST be read-only, non-destructive, and idempotent: every authored qa_pair may only require tool calls whose readOnlyHint=true / destructiveHint=false, and any qa_pair that would require a WRITE or DESTRUCTIVE operation is dropped. Source: reference/evaluation.md (questions must require only non-destructive and idempotent tool use; verification step flags and removes any qa_pair requiring write/destructive operations). | `EvalGen.step3:sys.assert` |
| NN5 — Tool/API errors MUST be actionable: the generated server returns helpful, specific error messages with a suggested next step INSIDE the result object (isError), never throwing raw exceptions and never leaking internal implementation details. Source: SKILL.md (error messages should guide agents toward solutions with specific suggestions and next steps) + reference/mcp_best_practices.md L206-211. | `ReviewTest.step2:sys.assert` |
| NN6 — Every tool MUST declare all four annotation hints (readOnlyHint, destructiveHint, idempotentHint, openWorldHint) as booleans. This is a STRUCTURAL presence + boolean-type check, NOT a proof of semantic truthfulness — the annotations are hints, not security guarantees. Source: SKILL.md L119-124 + reference/mcp_best_practices.md L60/L190-201. | `ImplementPy.step3:sys.assert` |
| NN7 — Tool input validation MUST use a strict schema: Pydantic ConfigDict(extra='forbid') in Python or Zod .strict() in TypeScript, forbidding extra fields; ad-hoc hand-written if-checks are rejected. Source: reference/python_mcp_server.md (Pydantic models handle input validation, ConfigDict extra='forbid') + reference/node_mcp_server.md (Zod .strict() to forbid extra fields) + reference/mcp_best_practices.md L172. | `ImplementPy.step4:sys.assert` |
| NN8 — List/collection tools MUST paginate: respect the limit parameter and return has_more and next_offset (plus total_count). next_offset is the tool-RESULT offset pagination convention faithful to reference/mcp_best_practices.md L20-23 / L84-104; it is a DISTINCT layer from the MCP protocol-transport opaque cursor (nextCursor) and MUST NOT be rewritten to nextCursor. | `ReviewTest.step3:sys.assert` |
| NN9 — stdio servers MUST NOT log to stdout: stdout is the JSON-RPC channel, so all logging goes to stderr (Python logging->stderr, Node console.error, never console.log/print on the stdio transport path). Source: reference/mcp_best_practices.md L139 + reference/node_mcp_server.md (console.error for stdio logging). | `ReviewTest.step4:sys.assert` |
| NN10 — External MCP/SDK documentation is ON-DEMAND / OPEN-WORLD: it is fetched at runtime via web_fetch (modelcontextprotocol.io spec pages, python-sdk README, typescript-sdk README) and is NEVER bundled as static skill content. The skill therefore declares web_search/web_fetch with openWorldHint=true and marks those external URLs as open_world/runtime, not as static read_only resources. Source: SKILL.md L41-43/L61/L65/L203/L212-213. | `tools` |
| NN11 — When transport is http/remote, the generated server MUST declare an authorization section: a STRUCTURAL presence + type check that an auth/authorization block exists on the http/remote transport path (i.e. it is NOT left unauthenticated). This is presence-only, mirroring NN6's framing — it verifies the auth section is PRESENT and structured, NOT that the auth is cryptographically correct or unbypassable (no semantic security guarantee). For stdio transport the check is vacuously satisfied (no network auth surface). The recommended shape (OAuth 2.1 authorization-code + mandatory PKCE(S256) + token-audience validation per RFC 8707/RFC 9068, and no raw client-token passthrough to upstream APIs) lives in discovery.guidance; this red line only asserts the presence of the section, not its semantic strength. Source: MCP 2025-11-25 authorization spec + reference/mcp_best_practices.md. | `ReviewTest.step5:sys.assert` |
| NN12 — Outbound fetch MUST be SSRF-safe under an ALLOW-LIST-ONLY (default-deny) egress policy: any LLM-provided / user-provided URL the generated server would fetch MUST be validated against an explicit, statically-declared allow-list, and ONLY hosts on that allow-list may egress — every undeclared host is blocked (default-deny). There is NO default public-internet egress: an outbound-fetch path that permits arbitrary public URLs so long as private/loopback/link-local ranges are blocked is REJECTED, because blocking private ranges alone still leaves the whole public internet reachable. Private / loopback / link-local egress remains blocked as before, but is now a subset of the default-deny posture rather than the whole guarantee. This is a DETERMINISTICALLY assertable structural check over the emitted server (a default-deny allow-list gate is present on the outbound-fetch path: the URL host is checked against an explicit allow-list and rejected when absent). The non-deterministic threats — prompt-injection, tool-poisoning, confused-deputy, and token-passthrough — are NOT asserted here; they remain LLM-judgement guidance in discovery.guidance with no fabricated enforced_by. Source: MCP 2026 security best practices + reference/mcp_best_practices.md security section + OWASP SSRF default-deny allow-list guidance. | `ReviewTest.step6:sys.assert` |

## Resources

| ID | Path | Kind | Mode | Scope | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| mcp_best_practices | reference/mcp_best_practices.md | doc | read_only | skill |  |
| python_mcp_server | reference/python_mcp_server.md | doc | read_only | skill |  |
| node_mcp_server | reference/node_mcp_server.md | doc | read_only | skill |  |
| evaluation_guide | reference/evaluation.md | doc | read_only | skill |  |

## Integrity

| Hash | Value | Meaning |
| --- | --- | --- |
| `contract_sha256` | `66764ddf8574da4cfcaa78d70198f51f8d566ccf18b1f3565f42e4027f4a815a` | Recomputable hash of `user.content.aisp_contract` |
| `resources_sha256` | `ba0ce7dc3cdd83e410dda7836fda3347069ed54b79a940434de7500786d4112b` | Recomputable hash of declared resource records |

`package_sha256` is intentionally not embedded here because a README is part of the distributed package and package-level hashes belong in external registry/provenance artifacts. Recompute it with `tools/aisp_hash.py` at publication time.

These hashes show local integrity only. They do not prove trust, safety, or registry approval.

## Source Of Truth

`aisp.aisop.json` is authoritative. A successful README check proves only that this file matches the contract-derived projection; it does not prove that the skill is safe or trustworthy.
