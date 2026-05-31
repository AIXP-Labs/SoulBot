import copy
import json
import logging
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import yaml as _yaml  # noqa: F401
except ImportError:
    logger.warning("PyYAML not installed — AIAP.md frontmatter summaries will be unavailable. Install with: pip install pyyaml")

import soulbot
from soulbot.agents import LlmAgent

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_AGENT_DIR = Path(__file__).parent
_AIAP_DIR = (_AGENT_DIR / "aiap").resolve()
_AIAP_STORE_DIR = (_AGENT_DIR.parent / "aiap_store").resolve()

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
# AIAP registry (scan aiap_store + aiap, with loading_mode)
# ---------------------------------------------------------------------------

_aiap_json_path = _AGENT_DIR / "aiap.json"
_aiap_registry_cache: list[dict] | None = None
_aiap_dirs_hash: str = ""


def _compute_dirs_hash(aiap_dirs: list[Path]) -> str:
    """Compute a content-based hash of AIAP directory listings.

    Uses directory entry names + sizes instead of mtime, which is unreliable
    on Windows (mtime granularity issues, copy/move not updating mtime).
    """
    import hashlib
    h = hashlib.md5(usedforsecurity=False)
    for d in sorted(aiap_dirs):
        try:
            for entry in sorted(d.iterdir()):
                if entry.is_dir() and entry.name.endswith("_aiap"):
                    main_file = entry / "main.aisop.json"
                    size = main_file.stat().st_size if main_file.is_file() else 0
                    h.update(f"{entry.name}:{size}".encode())
        except OSError:
            pass
    return h.hexdigest()


def _get_aiap_registry() -> list[dict]:
    """Scan aiap/ for *_aiap packages (private agent-local AIAPs only)."""
    global _aiap_registry_cache, _aiap_dirs_hash

    aiap_dirs = [d for d in (_AIAP_DIR,) if d.is_dir()]
    if not aiap_dirs:
        return []

    try:
        current_hash = _compute_dirs_hash(aiap_dirs)
    except OSError:
        return _aiap_registry_cache or []

    if _aiap_registry_cache is not None and current_hash == _aiap_dirs_hash:
        return _aiap_registry_cache

    _aiap_dirs_hash = current_hash

    packages = []
    seen_names = set()

    for aiap_dir in aiap_dirs:
        for d in sorted(aiap_dir.iterdir()):
            if not d.is_dir() or not d.name.endswith("_aiap"):
                continue

            # Dedup: aiap_store scanned first, skip duplicates in aiap/
            if d.name in seen_names:
                continue
            seen_names.add(d.name)

            entry = d / "main.aisop.json"
            if not entry.is_file():
                continue

            pkg = {
                "name": d.name.replace("_aiap", ""),
                "summary": "",
                "entry": str(entry),
                "loading_mode": "normal",
                "workspace_dir": str(aiap_dir),
            }

            # Read loading_mode from main.aisop.json
            try:
                with open(entry, encoding="utf-8-sig") as f:
                    prog = json.load(f)
                lm = prog[0]["content"].get("loading_mode", "normal")
                if lm not in ("normal", "node", "lite"):
                    logger.warning("AIAP %s has invalid loading_mode '%s', defaulting to 'normal'", d.name, lm)
                pkg["loading_mode"] = lm if lm in ("normal", "node", "lite") else "normal"
            except Exception:
                pass

            # Extract summary from AIAP.md YAML frontmatter
            aiap_md = d / "AIAP.md"
            if aiap_md.is_file():
                try:
                    import yaml  # noqa: F811
                    content = aiap_md.read_text(encoding="utf-8-sig")
                    if content.startswith("---"):
                        fm_parts = content.split("---", 2)
                        if len(fm_parts) >= 3:
                            fm = yaml.safe_load(fm_parts[1])
                            if isinstance(fm, dict):
                                raw = str(fm.get("summary", ""))
                                dot = raw.find(".")
                                pkg["summary"] = raw[:dot + 1] if dot > 0 else raw
                except Exception:
                    pass

            packages.append(pkg)

    # Persist registry
    try:
        with open(_aiap_json_path, "w", encoding="utf-8") as f:
            json.dump(packages, f, ensure_ascii=False, indent=2)
    except OSError:
        pass

    _aiap_registry_cache = packages
    return packages


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
        f"[AIAP Store Directory]\n{_AIAP_STORE_DIR}"
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

        # AIAP package registry with loading_mode (only needed for Router matching)
        registry = _get_aiap_registry()
        if registry:
            lines = ["[Available AIAP packages]"]
            for pkg in registry:
                mode_tag = f" [loading_mode={pkg['loading_mode']}]"
                lines.append(f"- {pkg['name']}: {pkg['summary'] or 'No description'}{mode_tag}")
                lines.append(f"  entry: {pkg['entry']}")
                lines.append(f"  workspace_dir: {pkg['workspace_dir']}")
            lines.append("Route user intent to the matching package above.")
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
