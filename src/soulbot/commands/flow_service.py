"""FlowService — SOULBOT_CMD service for on-demand function loading (AISOP + AISIP)."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FlowService:
    """Provide on-demand function loading for AISOP/AISIP flows.

    AI requests functions via::

        <!--SOULBOT_CMD:{"service":"flow","action":"load_functions",
            "path":"main.aisop.json","refs":["N3","N5"]}-->

    Relative paths are resolved against agent_dir.
    """

    def __init__(self, agent_dir: str | None = None) -> None:
        self._agent_dir: Path | None = Path(agent_dir) if agent_dir else None

    def set_agent_dir(self, agent_dir: str) -> None:
        """Set the agent directory for resolving relative paths."""
        self._agent_dir = Path(agent_dir)

    def load_functions(self, path: str, refs: list[str]) -> dict:
        """Load function bodies from an AISOP/AISIP file by node refs."""
        file_path = Path(path)
        if not file_path.is_absolute() and self._agent_dir:
            file_path = self._agent_dir / file_path

        try:
            with open(file_path, encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load flow file %s: %s", file_path, exc)
            return {"error": f"Failed to load file: {exc}"}

        functions = data[1]["content"].get("functions", {})
        result = {}
        for ref in refs:
            key = ref.split(".")[-1] if "." in ref else ref
            if key in functions:
                result[key] = functions[key]

        if not result:
            return {"error": f"Functions not found: {refs}"}
        return result
