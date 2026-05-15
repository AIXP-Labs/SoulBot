"""Session constants for the SoulBot framework."""

import os

# Single-user mode: all channels share the same user identity.
DEFAULT_USER_ID = "default"

# Default data directory and DB file name.
DEFAULT_DB_DIR = "data"
DEFAULT_DB_NAME = "soulbot_sessions.db"


def resolve_cli_name() -> str:
    """Resolve CLI_NAME from environment.

    Priority:
    1. Explicit ``CLI_NAME`` env var.
    2. Inferred from ``*_CLI=true`` flags.
    3. Fallback to ``"default_cli"``.
    """
    name = os.getenv("CLI_NAME", "").strip()
    if name:
        return name
    if os.getenv("CLAUDE_CLI", "").lower() in ("true", "1"):
        return "claude_cli"
    if os.getenv("CODEX_CLI", "").lower() in ("true", "1"):
        return "codex_cli"
    if os.getenv("OPENCODE_CLI", "").lower() in ("true", "1"):
        return "opencode_cli"
    if os.getenv("GEMINI_CLI", "").lower() in ("true", "1"):
        return "gemini_cli"
    if os.getenv("OPENCLAW_CLI", "").lower() in ("true", "1"):
        return "openclaw_cli"
    return "default_cli"


def resolve_db_path(agents_dir: str | None = None) -> str:
    """Resolve the session DB path: ``agents_dir/data/soulbot_sessions.db``.

    Creates the ``data/`` directory if it does not exist.
    Falls back to CWD when *agents_dir* is ``None`` (useful for tests).
    """
    from pathlib import Path

    base = Path(agents_dir) if agents_dir else Path.cwd()
    data_dir = base / DEFAULT_DB_DIR
    data_dir.mkdir(exist_ok=True)
    return str(data_dir / DEFAULT_DB_NAME)
