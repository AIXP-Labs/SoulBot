"""AgentLoader — discover and load agents from a directory.

Convention: each agent lives in a subdirectory (or single file) under
the agents directory.  The loader looks for a module-level variable named
``root_agent`` (a :class:`BaseAgent` instance).

Directory layout::

    agents_dir/
    ├── .env              # Root shared config (inherited by all agents)
    ├── hello_agent/
    │   ├── .env          # Agent-specific overrides (optional)
    │   ├── __init__.py   # from .agent import root_agent
    │   └── agent.py      # root_agent = LlmAgent(...)
    ├── weather_agent/
    │   └── agent.py      # root_agent = LlmAgent(...)
    └── simple_agent.py   # root_agent = LlmAgent(...)

Environment variable inheritance::

    Agent .env  >  Root .env  >  System environment
    (highest)      (fallback)    (lowest)
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

from ..agents.base_agent import BaseAgent


class AgentLoader:
    """Discovers and loads agent definitions from a directory."""

    ROOT_AGENT_VAR = "root_agent"

    def __init__(self, agents_dir: str | Path) -> None:
        self.agents_dir = Path(agents_dir).resolve()
        if not self.agents_dir.is_dir():
            raise FileNotFoundError(f"Agents directory not found: {self.agents_dir}")

        # Parse and cache root .env once at init
        self._root_env: dict[str, str] = self._parse_env(self.agents_dir / ".env")
        # Pre-merged complete env per agent (lazily populated)
        self._agent_envs: dict[str, dict[str, str]] = {}

    def list_agents(self) -> list[str]:
        """Return the names of all discoverable agents."""
        names: list[str] = []
        for child in sorted(self.agents_dir.iterdir()):
            if child.name.startswith(("_", ".")):
                continue
            # Package (directory with __init__.py or agent.py)
            if child.is_dir():
                if (child / "__init__.py").exists() or (child / "agent.py").exists():
                    names.append(child.name)
            # Single-file agent
            elif child.is_file() and child.suffix == ".py":
                names.append(child.stem)
        return names

    def get_agent_dir(self, name: str) -> Path | None:
        """Return the directory path of a named agent, or None for single-file agents."""
        pkg_dir = self.agents_dir / name
        if pkg_dir.is_dir():
            return pkg_dir
        return None

    def load_agent(self, name: str) -> BaseAgent:
        """Load and return the ``root_agent`` from the named agent module.

        If the agent directory contains a ``.env`` file, it is loaded into
        ``os.environ`` before the module is imported, so that ``os.getenv()``
        calls inside the agent module pick up per-agent configuration.

        Raises:
            FileNotFoundError: if the agent cannot be located.
            AttributeError: if the module has no ``root_agent``.
        """
        self._load_agent_env(name)
        module = self._import_agent_module(name)
        if not hasattr(module, self.ROOT_AGENT_VAR):
            raise AttributeError(
                f"Agent module '{name}' has no '{self.ROOT_AGENT_VAR}' variable"
            )
        agent = getattr(module, self.ROOT_AGENT_VAR)
        if not isinstance(agent, BaseAgent):
            raise TypeError(
                f"'{self.ROOT_AGENT_VAR}' in '{name}' is not a BaseAgent instance "
                f"(got {type(agent).__name__})"
            )
        return agent

    def _import_agent_module(self, name: str):
        """Dynamically import the agent module."""
        # Try directory-based package first
        pkg_dir = self.agents_dir / name
        if pkg_dir.is_dir():
            # Prefer __init__.py, fall back to agent.py
            if (pkg_dir / "__init__.py").exists():
                return self._import_from_path(name, pkg_dir / "__init__.py")
            if (pkg_dir / "agent.py").exists():
                return self._import_from_path(f"{name}.agent", pkg_dir / "agent.py")

        # Try single-file module
        single_file = self.agents_dir / f"{name}.py"
        if single_file.is_file():
            return self._import_from_path(name, single_file)

        raise FileNotFoundError(
            f"Agent '{name}' not found in {self.agents_dir}"
        )

    @staticmethod
    def _parse_env(path: Path) -> dict[str, str]:
        """Parse a ``.env`` file into a dict without modifying ``os.environ``."""
        if not path.is_file():
            return {}
        try:
            from dotenv import dotenv_values
            return {k: v for k, v in dotenv_values(path).items() if v is not None}
        except ImportError:
            return {}

    def get_agent_env(self, name: str) -> dict[str, str]:
        """Return the complete, pre-merged env dict for an agent.

        On first call for a given agent name:
        1. Parse agent's ``.env`` (if any)
        2. Merge with root ``.env`` (root as base, agent overrides)
        3. Cache the result

        Subsequent calls return the cached dict directly.
        """
        if name not in self._agent_envs:
            agent_dir = self.get_agent_dir(name)
            agent_env = self._parse_env(agent_dir / ".env") if agent_dir else {}
            self._agent_envs[name] = {**self._root_env, **agent_env}
        return self._agent_envs[name]

    def _load_agent_env(self, name: str) -> None:
        """Apply the agent's complete env to ``os.environ``.

        Uses the pre-merged env from :meth:`get_agent_env` so that
        each agent sees: ``agent .env > root .env > system env``.
        """
        merged = self.get_agent_env(name)
        for key, value in merged.items():
            os.environ[key] = value

    @staticmethod
    def _import_from_path(module_name: str, file_path: Path):
        """Import a module from an absolute file path."""
        # Use hash of file path to avoid collisions between different
        # directories that contain agents with the same name.
        path_hash = hash(str(file_path))
        qualified = f"_adk_agents_{path_hash}.{module_name}"

        # Re-import every time to avoid stale cache
        sys.modules.pop(qualified, None)

        spec = importlib.util.spec_from_file_location(qualified, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        return module
