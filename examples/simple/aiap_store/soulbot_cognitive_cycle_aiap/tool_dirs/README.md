# tool_dirs/ — soulbot_cognitive_cycle MCP tool surface (v2.36.0)

This directory materializes the `tool_dirs: ["tool_dirs/"]` declaration in `agent_card.json`,
closing the prior claim-vs-artifact gap (Y1) where the declaration had no backing directory.

## Contents

- `mcp_server.json` — declarative MCP server manifest (static). Mirrors the discovery card.
- The matching static discovery card lives at `../.well-known/mcp/server-card.json`
  (per **SEP-2127**, served at the canonical `/.well-known/mcp/server-card.json` path —
  NOT the stale SEP-1649 `/.well-known/mcp.json`).

## Honest scope (do not over-state)

This is **static discovery metadata only**. No live MCP JSON-RPC / SSE runtime is bundled with
this package. The `endpoints` fields in the card are declared placeholders for a future runtime.
SEP-2127 itself is **draft/RC** as of 2026-06-14 (RC target mid-2026), so the card carries a
`_freshness` annotation and MUST be read as discovery metadata, not as proof of a reachable server.

## Tool surface (4 tools, from agent_card.json skills)

| tool | module | entry |
|------|--------|-------|
| start_cognitive_cycle | main | ../main.aisop.json |
| inspect_state | metacognition | ../metacognition.aisop.json |
| trigger_sleep | consolidation | ../consolidation.aisop.json |
| inject_stimulus | perception | ../perception.aisop.json |
