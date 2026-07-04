import copy
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

import soulbot
from soulbot.agents import LlmAgent

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_AGENT_DIR = Path(__file__).parent
_AIAP_DIR = (_AGENT_DIR / "aiap").resolve()
_AIAP_STORE_DIR = (_AGENT_DIR.parent / "aiap_store").resolve()
_AISP_DIR = (_AGENT_DIR / "aisp").resolve()

# Cache lifecycle management is delegated to prepare_cache module.
# agent.py bootstraps the Engine by importing cleanup_cache + prepare_execution_context.
# CACHE_NUM env var (default 100) is the single source of truth, read by prepare_cache.
# AISOP layer can also invoke the same module via Bash CLI (portability).
_ENGINE_AIAP_DIR = _AGENT_DIR / "soulbot_execute_engine_aiap"

# Heartbeat AISOP: flat file at agent dir root. Read dynamically each call
# (not cached) so AI can modify recurring_tasks array at runtime via normal
# chat. Only ~1 call/day — file I/O overhead is negligible.
_HEARTBEAT_PATH = _AGENT_DIR / "heartbeat.aisop.json"


def _load_heartbeat_aisop() -> str:
    """Read heartbeat.aisop.json from disk (live, not cached).

    AI may modify recurring_tasks array via file_system tool during normal
    chat; live read ensures next heartbeat trigger sees the updated tasks
    without requiring process restart.
    """
    if _HEARTBEAT_PATH.is_file():
        try:
            with open(_HEARTBEAT_PATH, encoding="utf-8-sig") as f:
                return json.dumps(json.load(f), ensure_ascii=False, indent=2)
        except (json.JSONDecodeError, OSError):
            return ""
    return ""


# Capability doc path (AI reads on demand, not injected into prompt).
_SCHEDULE_GUIDE = Path(soulbot.__file__).parent / "docs" / "schedule_guide.md"
_MCP_GUIDE = Path(soulbot.__file__).parent / "docs" / "mcp_guide.md"
_MESSAGE_GUIDE = Path(soulbot.__file__).parent / "docs" / "message_guide.md"


# ---------------------------------------------------------------------------
# Cache lifecycle — prepare_cache dual-use module (library + CLI).
# agent.py uses Python import (fast path, ~5ms).
# AISOP fallback uses Bash CLI (~300ms, portable to any Agent framework).
# prepare_execution_context runs cleanup_cache internally (equivalent to
# original agent.py sequence: cleanup() then prepare()).
# ---------------------------------------------------------------------------

import sys as _sys
_sys.path.insert(0, str(_ENGINE_AIAP_DIR / "python_tools"))
from prepare_cache import prepare_execution_context as _prepare_execution_context


# ---------------------------------------------------------------------------
# Router: one-time file cache (no mtime reload)
# ---------------------------------------------------------------------------

_router_cache: list | None = None

def _load_router_cache() -> list:
    """Load router AISOP file once at startup. No mtime reload."""
    global _router_cache
    if _router_cache is not None:
        return _router_cache

    router_file = "soulbot_execute_engine_aiap/main.aisop.json"
    logger.info("Loading router: %s", router_file)
    p = _AGENT_DIR / router_file
    if p.is_file():
        try:
            with open(p, encoding="utf-8-sig") as f:
                _router_cache = json.load(f)
            # Startup validation: check Router AISOP structure
            if isinstance(_router_cache, list) and len(_router_cache) >= 2:
                sys_content = _router_cache[0].get("content", {})
                if sys_content.get("protocol") != "AIAP V1.0.0":
                    logger.warning("Router AISOP %s missing or invalid protocol field", router_file)
                if not sys_content.get("version"):
                    logger.warning("Router AISOP %s missing version field", router_file)
                usr_content = _router_cache[1].get("content", {})
                if not usr_content.get("functions"):
                    logger.warning("Router AISOP %s missing functions — routing will fail", router_file)
            else:
                logger.warning("Router AISOP %s has unexpected structure (expected list with >= 2 elements)", router_file)
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load router AISOP %s: %s", router_file, e)
            _router_cache = []
    else:
        logger.error("Router AISOP file not found: %s", p)
        _router_cache = []

    return _router_cache


# ---------------------------------------------------------------------------
# AIAP registry (consume aiap/aiap_list.json; aiap_list.py is the generator)
# Truth model: *_aiap folders = source of truth, aiap_list.py = generator,
# aiap_list.json = cache, agent.py = consumer only.
# ---------------------------------------------------------------------------

_aiap_registry_cache: list[dict] | None = None
_aiap_dirs_hash: str = ""


def _compute_dirs_hash(
    dirs: list[Path], suffix: str = "_aiap", entry_name: str = "main.aisop.json"
) -> str:
    """Compute a content-based hash of package directory listings.

    Generalized for both protocols (AIAP: *_aiap/main.aisop.json — defaults;
    AISP: *_aisp/aisp.aisop.json). Uses directory entry names + sizes instead
    of mtime, which is unreliable on Windows (mtime granularity issues,
    copy/move not updating mtime).
    """
    import hashlib
    h = hashlib.md5(usedforsecurity=False)
    for d in sorted(dirs):
        try:
            for entry in sorted(d.iterdir()):
                if entry.is_dir() and entry.name.endswith(suffix):
                    main_file = entry / entry_name
                    size = main_file.stat().st_size if main_file.is_file() else 0
                    h.update(f"{entry.name}:{size}".encode())
        except OSError:
            pass
    return h.hexdigest()


def _first_sentence(raw: str) -> str:
    """First sentence for display: cut at the earliest of '。' or '. ' (half-width
    dot followed by whitespace/end) — avoids dots inside version numbers
    ("V1.0.0") and filenames ("cast_hexagram.py")."""
    zh = raw.find("。")
    en = -1
    i = raw.find(".")
    while i != -1:
        if i == len(raw) - 1 or raw[i + 1] in " \n\t":
            en = i
            break
        i = raw.find(".", i + 1)
    cands = [c for c in (zh, en) if c != -1]
    return raw[:min(cands) + 1] if cands else raw


def _get_aiap_registry() -> list[dict]:
    """Consume aiap/aiap_list.json (regenerated via aiap_list.py on dir change).

    Private agent-local AIAPs only. Generator failure falls back to the
    existing aiap_list.json (routing never breaks on a malformed package);
    unreadable JSON degrades to an empty registry for this turn.
    """
    global _aiap_registry_cache, _aiap_dirs_hash

    if not _AIAP_DIR.is_dir():
        return []
    try:
        current_hash = _compute_dirs_hash([_AIAP_DIR])
    except OSError:
        return _aiap_registry_cache or []

    if _aiap_registry_cache is not None and current_hash == _aiap_dirs_hash:
        return _aiap_registry_cache

    list_json = _AIAP_DIR / "aiap_list.json"
    if current_hash != _aiap_dirs_hash or not list_json.is_file():
        try:
            subprocess.run(
                [_sys.executable, "-B", str(_AIAP_DIR / "aiap_list.py"), "--json"],
                cwd=str(_AIAP_DIR), timeout=30, capture_output=True, check=True)
        except Exception as e:
            logger.error("aiap_list.py --json failed: %s — falling back to existing aiap_list.json", e)
    _aiap_dirs_hash = current_hash

    packages = []
    try:
        data = json.loads(list_json.read_text(encoding="utf-8-sig"))
        for item in data.get("packages", []):
            packages.append({
                "name": item["id"].replace("_aiap", ""),
                "summary": _first_sentence(item.get("summary") or ""),
                "entry": str(_AGENT_DIR / item["path"]),
                "loading_mode": item.get("loading_mode", "normal"),
                "workspace_dir": str(_AIAP_DIR),
            })
    except Exception as e:
        logger.error("cannot read aiap_list.json: %s — registry empty this turn", e)
    _aiap_registry_cache = packages
    return packages


# ---------------------------------------------------------------------------
# AISP registry (consume aisp/aisp_list.json; aisp_list.py is the generator —
# spec-normative, referenced by AISP_Standard.core/ecosystem/security).
# Same truth model + consumer pattern as the AIAP registry above.
# ---------------------------------------------------------------------------

_aisp_registry_cache: list[dict] | None = None
_aisp_dirs_hash: str = ""


def _get_aisp_registry() -> list[dict]:
    """Consume aisp/aisp_list.json (regenerated via aisp_list.py on dir change).

    Private agent-local AISP skills only. Mirrors _get_aiap_registry's
    hash-gated subprocess + fallback pattern: generator failure falls back to
    the existing aisp_list.json; unreadable JSON degrades to an empty registry.
    loading_mode is hardcoded "node" (AISP M1 mandates node; aisp_list.json
    does not carry the field). when_to_use/risk_level come from aisp_contract
    discovery semantics — stronger routing signals than AIAP name+summary.
    """
    global _aisp_registry_cache, _aisp_dirs_hash

    if not _AISP_DIR.is_dir():
        return []
    try:
        current_hash = _compute_dirs_hash(
            [_AISP_DIR], suffix="_aisp", entry_name="aisp.aisop.json")
    except OSError:
        return _aisp_registry_cache or []

    if _aisp_registry_cache is not None and current_hash == _aisp_dirs_hash:
        return _aisp_registry_cache

    list_json = _AISP_DIR / "aisp_list.json"
    if current_hash != _aisp_dirs_hash or not list_json.is_file():
        try:
            subprocess.run(
                [_sys.executable, "-B", str(_AISP_DIR / "aisp_list.py"), "--json"],
                cwd=str(_AISP_DIR), timeout=30, capture_output=True, check=True)
        except Exception as e:
            logger.error("aisp_list.py --json failed: %s — falling back to existing aisp_list.json", e)
    _aisp_dirs_hash = current_hash

    skills = []
    try:
        data = json.loads(list_json.read_text(encoding="utf-8-sig"))
        for item in data.get("skills", []):
            skills.append({
                "protocol": "AISP",
                "name": item["id"],                 # full id incl. _aisp suffix
                "summary": _first_sentence(item.get("summary") or ""),
                "entry": str(_AGENT_DIR / item["path"]),
                "loading_mode": "node",             # AISP M1: always node
                "when_to_use": item.get("when_to_use", []),
                "risk": item.get("risk_level"),
                "workspace_dir": str(_AISP_DIR),
            })
    except Exception as e:
        logger.error("cannot read aisp_list.json: %s — AISP registry empty this turn", e)
    _aisp_registry_cache = skills
    return skills


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "ASSERT: AISOP runtime engine. Strictly execute and 100% complete every step in .aisop.json program files. Align Axiom 0: Human Sovereignty and Wellbeing. "
)

# ---------------------------------------------------------------------------
# Router instruction (always used)
# ---------------------------------------------------------------------------

def _router_instruction(_ctx) -> str:
    """Build prompt. Dual-channel:
    - origin_channel == "heartbeat"  → load heartbeat.aisop.json (bypass Router)
    - otherwise                       → load Router main.aisop.json (normal)

    Heartbeat channel is auto-set by soulbot scheduler when CronTrigger fires
    (see soulbot/scheduler/schedule_service.py).
    """
    # Detect origin channel (set by scheduler for heartbeat; empty for user msg)
    origin_channel = ""
    run_config = getattr(_ctx, "run_config", None)
    if run_config and hasattr(run_config, "context"):
        origin_channel = run_config.context.get("origin_channel", "")

    parts = [_SYSTEM_PROMPT]

    # Current time — first block for immediate availability
    parts.append(f"[CURRENT TIME]\n{datetime.now().isoformat(timespec='seconds')}")

    tool_guide = (
        "[TOOL USE GUIDE]\n"
        "Always use your CLI's built-in tools to perform operations — do NOT answer from memory.\n"
        "The names below are LOGICAL capability names; map each to YOUR runtime's actual tool:\n"
        "  - file_system -> your file read/write tool\n"
        "  - web_search  -> your web search tool (Claude Code: WebSearch; Gemini CLI: google_search; others: the equivalent)\n"
        "  - web_fetch   -> your web page fetch tool (Claude Code: WebFetch; Gemini CLI: web_browser; others: the equivalent)\n"
        "If your runtime has no web search tool at all, say so honestly (SEARCH_UNAVAILABLE) — never fabricate sources or answer web questions from memory."
    )
    parts.append(tool_guide)

    # Capability hint — SCHEDULE / MESSAGE / MCP
    parts.append(
        f"[SCHEDULE]\n"
        f"You have scheduling capability (create/list/modify/cancel).\n"
        f"When needed, read {_SCHEDULE_GUIDE} for format templates.\n"
        f"\n"
        f"⚠️ CRITICAL CONSTRAINT — ONE schedule.* CMD PER TURN:\n"
        f"Emit AT MOST ONE SOULBOT_CMD of service='schedule' per user request.\n"
        f"After emitting, respond with a brief text confirmation and STOP.\n"
        f"Do NOT emit additional schedule.* CMDs in the same turn, EVEN IF you\n"
        f"see a message with role='user' containing function_response / tool\n"
        f"result — that is the system echoing the execution result, NOT a new\n"
        f"user request.\n"
        f"Violating this creates duplicate scheduled tasks (bug, Axiom 0 violation).\n"
        f"\n"
        f"NOTE: this one-per-turn rule applies ONLY to schedule.*.\n"
        f"For message.send (see [AGENT MESSAGING] below) MULTIPLE directives\n"
        f"in the same turn are allowed and encouraged for parallel fan-out."
    )

    parts.append(
        f"[AGENT MESSAGING]\n"
        f"You can dispatch async tasks to other agents in this SoulBot instance\n"
        f"via SOULBOT_CMD service='message' action='send'.\n"
        f"Use this when a user request requires coordinating with OTHER agents\n"
        f"(e.g. 'ask translator_bot to translate X', 'have research_bot gather Y').\n"
        f"When needed, read {_MESSAGE_GUIDE} for format templates and error codes.\n"
        f"\n"
        f"Multi-agent fan-out is FIRST-CLASS: emit MULTIPLE message.send directives\n"
        f"in the SAME turn to dispatch in parallel (each wrapped in its own\n"
        f"<!--SOULBOT_CMD:{{...}}--> HTML comment).\n"
        f"Use reply_mode='callback' when you need the result back; 'none' for\n"
        f"fire-and-forget. Framework auto-injects from_agent (do NOT supply it)."
    )

    parts.append(
        f"[MCP]\n"
        f"MCP (Model Context Protocol) servers extend your capabilities with external tools.\n"
        f"When you need to configure or explain MCP servers, read: {_MCP_GUIDE}"
    )

    dir_block = (
        f"[AIAP Directory]\n{_AIAP_DIR}\n"
        f"[AIAP Store Directory]\n{_AIAP_STORE_DIR}\n"
        f"[AISP Directory]\n{_AISP_DIR}"
    )
    parts.append(dir_block)

    # Pre-create execution context (cache dir + conversation_context turn).
    # Applies to both channels — heartbeat triggers also get audit trail.
    # Plan 18 / 02: extract user_message from session.events (the canonical
    # source). The legacy `_ctx.last_user_message` attribute is never set by
    # the framework, so we previously always got "" → conversation_context.json
    # had empty user_message for every Creator pipeline turn (audit log gap).
    user_message = ""
    try:
        session = getattr(_ctx, "session", None)
        events = getattr(session, "events", None) if session else None
        if events:
            for ev in reversed(events):
                if getattr(ev, "author", None) != "user":
                    continue
                content = getattr(ev, "content", None)
                parts_list = getattr(content, "parts", None) if content else None
                if parts_list:
                    text = getattr(parts_list[0], "text", None)
                    if text:
                        user_message = text
                        break
    except Exception:
        pass
    if origin_channel == "heartbeat":
        user_message = user_message or f"heartbeat trigger {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    exec_ctx = _prepare_execution_context(user_message, engine_aiap_dir=_ENGINE_AIAP_DIR)
    if exec_ctx:
        ctx_block = (
            f"[EXECUTION CONTEXT]\n"
            f"turn_id: {exec_ctx['turn_id']}\n"
            f"cache_dir: {exec_ctx['cache_dir']}\n"
            f"cache_name: {exec_ctx['cache_name']}\n"
            f"trace_id: {exec_ctx['trace_id']}"
        )
        if origin_channel:
            ctx_block += f"\norigin_channel: {origin_channel}"
        parts.append(ctx_block)

    # AISOP injection — heartbeat replaces Router when origin_channel="heartbeat"
    heartbeat_aisop = _load_heartbeat_aisop()
    if origin_channel == "heartbeat" and heartbeat_aisop:
        parts.append(
            f"[LOADED AISOP: heartbeat.aisop.json]\n```json\n{heartbeat_aisop}\n```"
        )
    else:
        # Normal channel: load Router AISOP
        data = copy.deepcopy(_load_router_cache())
        if not data:
            return _SYSTEM_PROMPT

        # Router is always normal mode — inject system prompt into Router JSON
        data[0]["content"]["system_prompt"] = _SYSTEM_PROMPT
        data[1]["content"]["instruction"] = "RUN aisop.main"
        data[0]["content"].pop("loading_mode", None)

        # Package registry for Router matching. Block name kept as
        # "[Available AIAP packages]" for engine-match compatibility; AISP
        # entries are tagged [protocol=AISP] (untagged entries = AIAP). AIAP
        # entry rendering is byte-identical to the pre-AISP version (doc 04 V3).
        registry = _get_aiap_registry()
        aisp_registry = _get_aisp_registry()
        if registry or aisp_registry:
            lines = ["[Available AIAP packages]"]
            for pkg in registry:
                mode_tag = f" [loading_mode={pkg['loading_mode']}]"
                lines.append(f"- {pkg['name']}: {pkg['summary'] or 'No description'}{mode_tag}")
                lines.append(f"  entry: {pkg['entry']}")
                lines.append(f"  workspace_dir: {pkg['workspace_dir']}")
            for pkg in aisp_registry:
                risk_tag = f" [risk={pkg['risk']}]" if pkg.get("risk") else ""
                lines.append(
                    f"- {pkg['name']}: {pkg['summary'] or 'No description'}"
                    f" [protocol=AISP] [loading_mode={pkg['loading_mode']}]{risk_tag}"
                )
                if pkg.get("when_to_use"):
                    lines.append(f"  when_to_use: {' | '.join(pkg['when_to_use'])}")
                lines.append(f"  entry: {pkg['entry']}")
                lines.append(f"  workspace_dir: {pkg['workspace_dir']}")
            # Routing discipline (user legislation 2026-07-03, Axiom 0 — see
            # docs/01SoulBot-Support-AISP/05 §4b): explicit naming wins; on
            # same-intent ambiguity NEVER pick on the user's behalf — ask.
            # v2 (same day): bounded "doubt" + anti-over-gate clause — the first
            # wording's unscoped "when in doubt, STOP" invited manufactured doubt
            # (mid-run "shall I continue" pauses). Two-sided discipline: designed
            # gates must stop; undesigned stops are also a sovereignty violation.
            lines.append(
                "Route user intent to the matching package above.\n"
                "- If the user explicitly names a package or a protocol (e.g. \"用 AISP …\"), "
                "use exactly that — absolute priority.\n"
                "- If exactly one entry matches the intent, route to it and RUN — "
                "do not ask permission to proceed.\n"
                "- ONLY IF more than one entry covers the same intent and the user did not "
                "name one: do not pick for the user — present the matching entries as a "
                "short numbered list (one line each), optionally add your recommendation, "
                "and wait for the user's choice. (Axiom 0 here means: genuine doubt about "
                "WHICH package the user wants — not doubt about whether to proceed with "
                "clear instructions.)\n"
                "- Once the target is decided, execute continuously to completion or a "
                "DESIGNED gate (sys.io.confirm / user_gate) or HARD_FAIL. Do NOT pause "
                "mid-run to ask \"shall I continue\" — unnecessary stops are also a "
                "sovereignty violation (they dilute real gates)."
            )
            parts.append("\n".join(lines))

        file_id = data[0]["content"].get("id", "main")
        data_json = json.dumps(data, ensure_ascii=False, indent=2)
        parts.append(f"[LOADED AISOP: {file_id}.aisop.json]\n```json\n{data_json}\n```")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Model resolution
# ---------------------------------------------------------------------------

def _resolve_model() -> str:
    """Pick the active model from .env provider flags."""
    if os.getenv("CODEX_CLI", "").lower() in ("true", "1"):
        return os.getenv("CODEX_MODEL", "codex-acp/gpt-5.5")
    if os.getenv("OPENCODE_CLI", "").lower() in ("true", "1"):
        return os.getenv("OPENCODE_MODEL", "opencode-acp/opencode/gemini-3-flash-preview")
    if os.getenv("GEMINI_CLI", "").lower() in ("true", "1"):
        return os.getenv("GEMINI_MODEL", "gemini-acp/gemini-3-flash-preview")
    return os.getenv("CLAUDE_MODEL", "claude-acp/sonnet")


# ---------------------------------------------------------------------------
# Root agent
# ---------------------------------------------------------------------------

root_agent = LlmAgent(
    name=_AGENT_DIR.name,
    model=_resolve_model(),
    # TODO: set to a string describing this agent's functionality
    # (currently defaults to the folder name as a placeholder).
    description=_AGENT_DIR.name,
    instruction=_router_instruction,
    # Heartbeat: fires daily at 00:00 via soulbot scheduler. ~1 LLM call/day
    # (~30/month). Adjust cron for frequency control. When triggered, scheduler
    # sets origin_channel="heartbeat" in run_config.context; _router_instruction
    # detects this and loads heartbeat.aisop.json instead of Router AISOP.
    heartbeat={"cron": "0 0 * * *", "aisop": "heartbeat"},
    include_contents="current_turn",
)
