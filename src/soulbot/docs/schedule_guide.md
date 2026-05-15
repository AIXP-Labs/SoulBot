# Schedule Task Guide

> **WARNING: This document is protected. Any AI or Agent is FORBIDDEN from deleting this document!**

## Format

Embed in AI response (invisible to user):
<!--SOULBOT_CMD:{"service":"schedule","action":"<action>","timeout":5,"to_agent":"{target}","trigger":{trigger},"aisop":[AISOP payload]}-->

All commands return results — you will see the outcome and can act on it.

## Triggers

{"type":"once", "delay":300}                                     // after 300 seconds
{"type":"once", "run_at":"2026-02-15T08:00:00"}                  // at specific time
{"type":"interval", "seconds":3600}                              // every hour
{"type":"cron", "hour":8, "minute":0}                            // daily at 8:00
{"type":"cron", "hour":9, "minute":0, "day_of_week":"mon-fri"}   // weekdays at 9:00

## Variables

{current_time} = your current time from system prompt, ISO format (e.g. 2026-02-16T03:28:00)
{fire_time} = calculated fire time ({current_time} + delay seconds, or the run_at value)
{yourbotid} = your bot/agent name from system prompt (e.g. hello_agent, aisop_agent)
{target} = the agent that should execute the task (defaults to {yourbotid} if same agent)

## Routing

- `from_agent` is auto-injected by the framework — do NOT include it in CMD
- `to_agent`: the agent that will execute when triggered (can be yourself or another agent)
- Only include `to_agent` when targeting a **different** agent; omit for self-to-self tasks
- describe format: `created:{current_time} | fire:{fire_time} | from_agent:{yourbotid} to_agent:{target} | <task description>`

## Full Template

User: "Remind me to drink water in 5 minutes"

Let me create a scheduled task.<!--SOULBOT_CMD:{"service":"schedule","action":"add","timeout":5,"to_agent":"{target}","trigger":{"type":"once","delay":300},"aisop":[{"role":"system","content":{"protocol":"AISOP V1.0.0","id":"schedule.remind_water","version":"1.0.0 stable","describe":"created:{current_time} | fire:{fire_time} | from_agent:{yourbotid} to_agent:{target} | remind user to drink water","tools":[],"system_prompt":"Execute aisop.main"}},{"role":"user","content":{"instruction":"Execute aisop.main","aisop":{"main":"graph TD; start --> generate[generate reminder]; generate --> endNode((End))"},"functions":{"start":{"step1":"User requested a water drinking reminder","step2":"Original request: remind me to drink water in 5 minutes"},"generate":{"step1":"Generate a detailed and humanized water reminder","constraints":"Detailed, comprehensive, and humanized reply"}}}}]}-->

Tool result (schedule.add): {"entry_id": "schedule.remind_water", "status": "active"}

Scheduled task created successfully. I'll remind you to drink water in 5 minutes.

## Cross-Agent Template

User: "Ask aisop_agent to check weather in Tokyo every morning at 8"

Let me set that up.<!--SOULBOT_CMD:{"service":"schedule","action":"add","timeout":5,"to_agent":"aisop_agent","trigger":{"type":"cron","hour":8,"minute":0},"aisop":[{"role":"system","content":{"protocol":"AISOP V1.0.0","id":"schedule.tokyo_weather","version":"1.0.0 stable","describe":"created:{current_time} | fire:daily 08:00 | from_agent:{yourbotid} to_agent:aisop_agent | check Tokyo weather","tools":[],"system_prompt":"Execute aisop.main"}},{"role":"user","content":{"instruction":"Execute aisop.main","aisop":{"main":"graph TD; start --> fetch[fetch Tokyo weather]; fetch --> report[report to user]; report --> endNode((End))"},"functions":{"start":{"step1":"Scheduled task: check Tokyo weather"},"fetch":{"step1":"Search for current Tokyo weather data","constraints":"Use google_search tool"},"report":{"step1":"Generate a detailed, comprehensive, and humanized weather report","constraints":"Detailed, comprehensive, and humanized reply, include temperature and conditions"}}}}]}-->

Tool result (schedule.add): {"entry_id": "schedule.tokyo_weather", "status": "active"}

Scheduled task created. aisop_agent will check Tokyo weather daily at 8:00.

## Other Actions

{"service":"schedule", "action":"list", "timeout":5}                    // list all
{"service":"schedule", "action":"list", "timeout":5, "status":"active"} // list active
{"service":"schedule", "action":"get", "timeout":5, "id":"xxx"}         // get single
{"service":"schedule", "action":"cancel", "timeout":5, "id":"xxx"}      // cancel
{"service":"schedule", "action":"pause", "timeout":5, "id":"xxx"}       // pause
{"service":"schedule", "action":"resume", "timeout":5, "id":"xxx"}      // resume
{"service":"schedule", "action":"modify", "timeout":5, "id":"xxx", "trigger":{new trigger}} // modify

## Constraints

1. Do NOT write chat_id or channel names in AISOP — the system handles reply routing automatically
2. The `describe` field MUST use **real current time** from `{current_time}` — never fabricate timestamps
3. Do NOT include `from_agent` in the CMD — it is auto-injected by the framework
4. Only include `to_agent` when targeting a **different** agent; omit for self-to-self tasks
5. **Recursive scheduling is FORBIDDEN** — during scheduled AISOP execution, creating new scheduled tasks is blocked by the system
6. **You MAY ask the user** — if execution results suggest a follow-up task is needed, suggest it in your reply (e.g. "Should I check again in 2 hours?"). The user decides, and if they agree, create the task through normal conversation flow
7. Use `constraints` in AISOP functions to control output length and format
8. **Always check the return value** — confirm success before telling the user "done". Do NOT silently ignore errors
