"""Configuration helpers — .env loading and settings."""

from __future__ import annotations

from pathlib import Path


def load_dotenv(agents_dir: str | Path | None = None) -> None:
    """Load .env files using python-dotenv.

    Loads only from the given directory.  Call multiple times with
    different directories for hierarchical loading (e.g. agent_dir
    first, then agents_dir).  ``override=False`` ensures earlier
    values are not overwritten.
    """
    try:
        from dotenv import load_dotenv as _load
    except ImportError:
        return

    if agents_dir is not None:
        env_file = Path(agents_dir) / ".env"
        if env_file.is_file():
            _load(env_file, override=False)
