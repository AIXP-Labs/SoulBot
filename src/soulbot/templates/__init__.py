"""Agent template scaffolding utilities.

Shared by both ``soulbot create`` CLI command and ``POST /agents/create`` API.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent

#: Agent name must start with a letter (a-z or A-Z), contain [a-zA-Z0-9_], max 56 chars.
#: Case is preserved as typed by the user.
AGENT_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,55}$")

_DEFAULT_ENV = """\
# Telegram Bot Token (get from @BotFather)
TELEGRAM_BOT_TOKEN=
# AI Provider Configuration (CLI Mode)
# Priority order: CODEX > OPENCODE > GEMINI > CLAUDE (default).
# Set exactly ONE to true.
CLAUDE_CLI=true
CODEX_CLI=false
OPENCODE_CLI=false
GEMINI_CLI=false

# Model Override Switch
# true:  SoulBot forces the model above (default)
# false: use OpenCode's own default model (set via /models in TUI or /connect provider)
OPENCODE_MODEL_OVERRIDE=true
# Agent Mode Configuration
# plan: chat and planning only, no tool execution (recommended for simple chat)
# build: default mode, executes system tools as needed
OPENCODE_AGENT_MODE=build
# OPENCODE_MODEL=opencode-acp/opencode/gemini-3.1-pro-preview
# OPENCODE_MODEL=opencode-acp/opencode/gemini-3-flash-preview
OPENCODE_MODEL=opencode-acp/opencode/claude-opus-4.6

# CLAUDE_MODEL=claude-acp/claude-fable-5
CLAUDE_MODEL=claude-acp/claude-opus-4-8

# Codex (OpenAI) — requires `codex login` (ChatGPT account, no API key needed).
# gpt-5.5 is ChatGPT-auth friendly; for API-key auth use gpt-5.5-codex / o3 / o4-mini.
CODEX_MODEL=codex-acp/gpt-5.5

# Codex reasoning effort (5 levels): minimal / low / medium / high / xhigh
# Read by soulacp 0.1.5+; injected as `-c model_reasoning_effort="..."` to codex-acp.
# If unset, soulacp defaults to "medium" (OpenAI's recommended balance).
# Source: https://developers.openai.com/codex/config-reference
CODEX_REASONING_EFFORT=xhigh

# Codex permission model (two independent controls — opt-in).
# Set BOTH to make Codex behave like Claude with --permission-mode dontAsk
# (no approval prompts, can write within workspace).
# Source: https://developers.openai.com/codex/agent-approvals-security
#
# CODEX_SANDBOX_MODE: read-only / workspace-write / danger-full-access
#   - read-only           (Codex default, can't write)
#   - workspace-write     (write within workspace, no network) ← recommended
#   - danger-full-access  (full system, DANGEROUS)
CODEX_SANDBOX_MODE=workspace-write
#
# CODEX_APPROVAL_POLICY: untrusted / on-failure / on-request / never
#   - untrusted   (Codex default, asks for risky ops)
#   - on-failure  (only when sandbox blocks)
#   - on-request  (model decides)
#   - never       (NEVER ask — like Claude dontAsk) ← recommended for autonomy
CODEX_APPROVAL_POLICY=never
#
# CODEX_NETWORK_ACCESS: true / false (default false)
# workspace-write defaults to NO network. Set true to allow network for:
#   - AISOP tools that need it (google_search, web_browser)
#   - pip install / npm install during AIAP runs
# No-op when sandbox_mode is read-only (can't write) or danger-full-access
# (network already on). Accepts: true / 1 / yes.
CODEX_NETWORK_ACCESS=true

# GEMINI_MODEL=gemini-acp/gemini-3.1-pro-preview
GEMINI_MODEL=gemini-acp/gemini-3-flash-preview

# Model Fallback Configuration
# true:  auto-switch to fallback model on failure (may cause confusion)
# false: fail immediately and show error to user (recommended)
ENABLE_FALLBACK=false

# Tool & Workspace Configuration
AUTO_APPROVE_PERMISSIONS=true

# Cache Management
CACHE_NUM=200


# Show AI thinking process in response (> [Thought])
SHOW_THOUGHTS=true


# OpenCode ACP Settings
# Disable auto title and summary to prevent request blocking caused by small models (gpt-5-nano)
OPENCODE_CONFIG_CONTENT={"agent":{"title":{"disable":true},"summary":{"disable":true}}}
# Force CLI mode to avoid Windows Git repo hanging issue
OPENCODE_USE_ACP=true

# soulacp ACP timeouts — 30 days (1 month)
# Matches soulacp source default (config.py); listed here for explicit clarity.
ACP_TIMEOUT_PROMPT=2592000
ACP_TIMEOUT_STREAM=2592000
ACP_POOL_IDLE_TIMEOUT=2592000

# Claude Code reasoning effort: low / medium / high / xhigh / max / auto
# Unset = auto (adaptive thinking, Anthropic's recommended default).
# Docs: https://code.claude.com/docs/en/model-config
# CLAUDE_CODE_EFFORT_LEVEL=auto
"""


def list_templates() -> list[dict[str, str]]:
    """Return available templates as ``[{name, description}]``."""
    result: list[dict[str, str]] = []
    if not TEMPLATES_DIR.is_dir():
        return result
    for child in sorted(TEMPLATES_DIR.iterdir()):
        if child.is_dir() and not child.name.startswith("_"):
            if (child / "agent.py").exists() or (child / "__init__.py").exists():
                result.append({
                    "name": child.name,
                    "description": _read_template_description(child),
                })
    return result


def scaffold_agent(name: str, template: str, output_dir: Path) -> Path:
    """Create a new agent directory from *template*.

    Returns the created directory path.
    Raises ``ValueError`` for invalid name/template, ``FileExistsError`` if target exists.
    """
    if not AGENT_NAME_RE.match(name):
        raise ValueError(
            f"Invalid agent name '{name}': must match [a-z][a-z0-9_]{{0,49}}"
        )

    template_dir = TEMPLATES_DIR / template
    if not template_dir.is_dir():
        raise ValueError(f"Template '{template}' not found")

    target = Path(output_dir) / name
    if target.exists():
        raise FileExistsError(f"'{target}' already exists")

    # Copy template (ignore __pycache__)
    shutil.copytree(
        template_dir, target, ignore=shutil.ignore_patterns("__pycache__")
    )

    # Replace placeholders in text files
    name_title = name.replace("_", " ").title()
    for f in target.rglob("*"):
        if f.is_file() and f.suffix in (".py", ".json", ".md"):
            content = f.read_text(encoding="utf-8")
            content = content.replace("template_agent", name)
            content = content.replace("Template Agent", name_title)
            f.write_text(content, encoding="utf-8")

    # Generate .env
    generate_agent_env(target)

    return target


def generate_agent_env(target: Path) -> None:
    """Write ``.env`` and ``.env.example`` into *target* directory.

    Both files start identical to ``_DEFAULT_ENV``. ``.env`` is the live
    config (user edits freely); ``.env.example`` is the canonical template
    snapshot for reference / git tracking.
    """
    env_file = target / ".env"
    env_file.write_text(_DEFAULT_ENV, encoding="utf-8")
    example_file = target / ".env.example"
    example_file.write_text(_DEFAULT_ENV, encoding="utf-8")


def _read_template_description(template_dir: Path) -> str:
    """Extract a one-line description from the template's agent.py docstring."""
    agent_py = template_dir / "agent.py"
    if not agent_py.exists():
        return ""
    try:
        text = agent_py.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Single-line docstring
                doc = stripped.strip("\"'").strip()
                if doc:
                    return doc
                # Multi-line: read next line
                continue
            if stripped and not line.startswith("#") and not line.startswith("from") and not line.startswith("import"):
                # First non-empty, non-import line after opening quote
                return stripped.strip("\"'").strip()
    except Exception:
        pass
    return ""
