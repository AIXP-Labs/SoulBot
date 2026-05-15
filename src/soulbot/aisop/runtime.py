"""AisopPlugin — AISOP/AISIP blueprint runtime as a framework Plugin."""

from __future__ import annotations

from typing import Any

from ..plugins.interface import PluginInterface
from .loader import AisopLoader
from .prompt_builder import AisopPromptBuilder


class AisopPlugin(PluginInterface):
    """AISOP/AISIP blueprint runtime plugin.

    Actions:
    - ``get_system_prompt``: Build and return a system prompt for a blueprint.
    - ``list``: List all loaded blueprints.
    - ``reload``: Reload all blueprints from disk.
    """

    name = "aisop_engine"
    version = "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._loader: AisopLoader | None = None
        self._builder = AisopPromptBuilder()
        self._prompt_cache: dict[str, str] = {}
        self._config: dict[str, Any] = {}

    async def initialize(self, config: dict[str, Any] | None = None) -> None:
        config = config or {}
        self._config = config
        aisop_dir = config.get("aisop_dir", "aisop")
        self._loader = AisopLoader(aisop_dir)
        self._loader.load_all()

        # Pre-cache "main" blueprint if present
        main_bp = self._loader.get("main")
        if main_bp is not None:
            self._prompt_cache["main"] = self._builder.build(
                main_bp,
                base_prompt=config.get("base_prompt", ""),
                workspace_dir=config.get("workspace_dir", aisop_dir),
                enable_schedule=config.get("enable_schedule", False),
            )

        await super().initialize(config)

    async def execute(self, params: dict[str, Any]) -> dict[str, Any]:
        action = params.get("action", "get_system_prompt")

        if action == "get_system_prompt":
            return self._action_get_prompt(params)

        if action == "list":
            return self._action_list()

        if action == "reload":
            return self._action_reload()

        raise ValueError(f"Unknown AISOP action: {action}")

    def get_supported_actions(self) -> list[str]:
        return ["get_system_prompt", "list", "reload"]

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _action_get_prompt(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("aisop", "main")

        if name in self._prompt_cache:
            return {"system_prompt": self._prompt_cache[name], "aisop_name": name}

        if self._loader is None:
            raise RuntimeError("AisopPlugin not initialized")

        bp = self._loader.load(name)
        prompt = self._builder.build(
            bp,
            base_prompt=self._config.get("base_prompt", ""),
            workspace_dir=self._config.get("workspace_dir", ""),
            enable_schedule=self._config.get("enable_schedule", False),
        )
        self._prompt_cache[name] = prompt
        return {"system_prompt": prompt, "aisop_name": name}

    def _action_list(self) -> dict[str, Any]:
        if self._loader is None:
            return {"aisops": [], "count": 0}
        names = self._loader.list_names()
        return {"aisops": names, "count": len(names)}

    def _action_reload(self) -> dict[str, Any]:
        if self._loader is None:
            raise RuntimeError("AisopPlugin not initialized")

        self._prompt_cache.clear()
        count = self._loader.reload_all()

        # Re-cache "main" if present
        main_bp = self._loader.get("main")
        if main_bp is not None:
            self._prompt_cache["main"] = self._builder.build(
                main_bp,
                base_prompt=self._config.get("base_prompt", ""),
                workspace_dir=self._config.get("workspace_dir", ""),
                enable_schedule=self._config.get("enable_schedule", False),
            )

        return {"reloaded": True, "count": count}
