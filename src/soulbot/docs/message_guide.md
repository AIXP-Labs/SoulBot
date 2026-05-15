# Agent Message Guide

> **WARNING: This document is protected. Any AI or Agent is FORBIDDEN from deleting this document!**

## When to use

Use `message` to send an asynchronous task to **another agent in the same SoulBot instance**.

| Need | Use |
|------|-----|
| Hand a task to another agent and continue working | **message** (this guide) |
| Run a task at a specific time / interval / cron | schedule (schedule_guide.md) |
| Get a synchronous reply from a sub-agent in this same call | AgentTool |
| Hand the entire conversation control to another agent | transfer_to_agent |

## Format

Embed in AI response (invisible to user):

<!--SOULBOT_CMD:{"service":"message","action":"send","timeout":30,"to_agent":"{target}","reply_mode":"none","aisop":[AISOP payload]}-->

All commands return results — you will see the outcome and can act on it.

## Reply Modes

{"reply_mode":"none"}      // fire-and-forget; you will NOT receive a reply
{"reply_mode":"callback"}  // receiver's result will be delivered back to you as a new message

## Variables

{current_time} = your current time from system prompt, ISO format (e.g. 2026-04-13T03:28:00)
{yourbotid}    = your bot/agent name from system prompt
{target}       = the agent that will receive and execute the task (must be a different agent)

## Routing

- `from_agent` is auto-injected by the framework — do NOT include it in CMD
- `to_agent`: the receiver agent. **MUST be different from `{yourbotid}`** (self-message is rejected)
- `parent_id` / `depth`: auto-managed by the framework — do NOT include
- `describe` format: `created:{current_time} | from_agent:{yourbotid} to_agent:{target} | <task description>`

## Full Template (fire-and-forget)

User: "Tell research_agent to summarize today's AI news in the background"

I'll dispatch that to research_agent.<!--SOULBOT_CMD:{"service":"message","action":"send","timeout":30,"to_agent":"research_agent","reply_mode":"none","aisop":[{"role":"system","content":{"protocol":"AISOP V1.0.0","id":"msg.ai_news_summary","version":"1.0.0 stable","describe":"created:{current_time} | from_agent:{yourbotid} to_agent:research_agent | summarize today AI news","tools":[],"system_prompt":"Execute aisop.main"}},{"role":"user","content":{"instruction":"Execute aisop.main","aisop":{"main":"graph TD; start --> search[search AI news]; search --> summarize[summarize findings]; summarize --> endNode((End))"},"functions":{"start":{"step1":"Background task delegated by {yourbotid}"},"search":{"step1":"Search for today's significant AI news","constraints":"Use google_search tool"},"summarize":{"step1":"Produce a 5-bullet summary","constraints":"Concise, factual, dated"}}}}]}-->

Tool result (message.send): {"message_id": "msg_a1b2c3d4", "status": "pending", "depth": 0}

Message dispatched to research_agent. Working on other things now.

## Callback Template (need the result back)

User: "Ask translator_agent to translate this paragraph into Japanese, then continue our conversation"

I'll send it to translator_agent and process the reply when it comes back.<!--SOULBOT_CMD:{"service":"message","action":"send","timeout":60,"to_agent":"translator_agent","reply_mode":"callback","aisop":[{"role":"system","content":{"protocol":"AISOP V1.0.0","id":"msg.translate_jp","version":"1.0.0 stable","describe":"created:{current_time} | from_agent:{yourbotid} to_agent:translator_agent | translate to Japanese","tools":[],"system_prompt":"Execute aisop.main"}},{"role":"user","content":{"instruction":"Execute aisop.main","aisop":{"main":"graph TD; start --> translate[translate text]; translate --> endNode((End))"},"functions":{"start":{"step1":"Translation request from {yourbotid}"},"translate":{"step1":"Translate the source text into natural Japanese","constraints":"Source: <original paragraph here>; Output Japanese only"}}}}]}-->

Tool result (message.send): {"message_id": "msg_e5f6a7b8", "status": "pending", "depth": 0}

Translation request sent. The result will arrive as a callback message; I'll continue once it returns.

## Other Actions

{"service":"message", "action":"list", "timeout":5}                                  // recent 100, all statuses
{"service":"message", "action":"list", "timeout":5, "status":"pending"}              // filter by status
{"service":"message", "action":"list", "timeout":5, "from_agent":"{yourbotid}"}      // sent by you
{"service":"message", "action":"list", "timeout":5, "to_agent":"{yourbotid}"}        // sent to you
{"service":"message", "action":"list", "timeout":5, "parent_id":"msg_xxx"}           // children of a message
{"service":"message", "action":"get", "timeout":5, "id":"msg_xxx"}                   // single entry
{"service":"message", "action":"cancel", "timeout":5, "id":"msg_xxx"}                // cancel pending

## Error Codes

If `send` returns `{"success":false,"error":"<code>: ..."}`, react as follows:

| code | meaning | what to do |
|------|---------|-----------|
| `self_loop` | You tried to send to yourself | Use AISOP graph internally instead; messages are for OTHER agents |
| `depth_exceeded` | Message chain is too deep (>5) | The current chain is over-extended; summarize and reply directly |
| `loop_detected` | Target agent already initiated a message in this chain | Pick a different agent or restructure the task |
| `rate_limited` | You sent too many messages too fast (>10/sec) | Wait briefly, batch related work into one message |
| `receiver_unknown` | The `to_agent` name is wrong or not registered | Re-check the agent name; do NOT retry blindly |
| `payload_too_large` | AISOP payload exceeds 100KB | Split the task or trim the payload |
| `service_closed` | SoulBot is shutting down | Do not send more messages |

## Operator notes

These do not affect what you (the AI agent) emit, but they describe how
the framework around you behaves:

- **Cap on payload size**: 100 KB per message by default; configurable via
  env var `SOULBOT_MESSAGE_MAX_AISOP_BYTES`.
- **Retention**: terminal-status messages older than 30 days are deleted
  by a daily cron at 03:00 server time; configurable via
  `SOULBOT_MESSAGE_RETENTION_DAYS`.
- **Disable entirely**: `SOULBOT_ENABLE_MESSAGING=false` removes the
  `message` service from the executor.
- **Multi-process safety**: in multi-worker deployments, only one worker
  performs the startup `restore()` (advisory SQLite lock).
- **Health endpoint**: `GET /message/health` returns counts by status
  for ops monitoring.
- **Demo / examples**: see `examples/simple/AGENT_MESSAGE_DEMO.md`.

## Constraints

1. Do NOT write chat_id, user_id, or channel names in AISOP — receiver routes via its own session automatically
2. The `describe` field MUST use **real current time** from `{current_time}` — never fabricate timestamps
3. Do NOT include `from_agent`, `parent_id`, or `depth` in the CMD — all auto-injected by the framework
4. `to_agent` MUST be a different agent — sending to yourself is rejected (`self_loop`)
5. **Recursive callback chains are bounded** — the system blocks chains deeper than 5 messages. This is the **only** automatic safeguard against a runaway callback storm; there is no per-parent child-count limit. If you need many parallel callbacks, consider whether a single fan-out (depth=1) plus a synthesized reply is cleaner than chains
6. **Callback messages cannot themselves request a callback** — `reply_mode` of a callback is forced to `"none"`
7. **You MAY ask the user before sending** — if a task is ambiguous or the receiver agent is uncertain, confirm with the user first
8. **Always check the return value** — confirm `"status":"pending"` before telling the user "dispatched"; on error, surface the failure and stop
9. Keep AISOP `payload` lean — use `constraints` to bound output length
10. Prefer `reply_mode:"none"` unless you genuinely need the result — callbacks add latency and chain depth
