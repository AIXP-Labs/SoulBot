"""AisopLoader — discover and load .aisop.json / .aisip.json blueprint files."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .schema import AisopBlueprint

logger = logging.getLogger(__name__)


class AisopLoader:
    """Load and manage AISOP blueprint files.

    Usage::

        loader = AisopLoader("./aisop")
        blueprints = loader.load_all()
        bp = loader.load("customer_support")
    """

    def __init__(self, aisop_dir: str | Path) -> None:
        self._dir = Path(aisop_dir)
        self._blueprints: dict[str, AisopBlueprint] = {}

    @property
    def blueprints(self) -> dict[str, AisopBlueprint]:
        """Return loaded blueprints."""
        return dict(self._blueprints)

    def has(self, name: str) -> bool:
        """Check if a blueprint with *name* is loaded."""
        return name in self._blueprints

    def list_names(self) -> list[str]:
        """Return names of all loaded blueprints."""
        return list(self._blueprints.keys())

    def get(self, name: str) -> AisopBlueprint | None:
        """Return a loaded blueprint by name, or ``None``."""
        return self._blueprints.get(name)

    def load_all(self) -> dict[str, AisopBlueprint]:
        """Scan directory and load all ``*.aisop.json`` and ``*.aisip.json`` files.

        Returns:
            Mapping of blueprint name to loaded blueprint.
        """
        if not self._dir.is_dir():
            logger.warning("AISOP/AISIP directory not found: %s", self._dir)
            return {}

        for pattern in ("*.aisop.json", "*.aisip.json"):
            for path in sorted(self._dir.glob(pattern)):
                try:
                    bp = self._load_file(path)
                    if bp.name not in self._blueprints:
                        self._blueprints[bp.name] = bp
                except Exception as exc:
                    logger.warning("Skipping %s: %s", path, exc)

        return dict(self._blueprints)

    def load(self, name: str) -> AisopBlueprint:
        """Load a single blueprint by name.

        Returns cached version if already loaded.

        Raises:
            FileNotFoundError: Blueprint file not found.
        """
        if name in self._blueprints:
            return self._blueprints[name]

        path = self._dir / f"{name}.aisop.json"
        if not path.exists():
            path = self._dir / f"{name}.aisip.json"
        if not path.exists():
            raise FileNotFoundError(f"Blueprint not found: {name}.aisop.json or {name}.aisip.json")

        bp = self._load_file(path)
        self._blueprints[bp.name] = bp
        return bp

    def reload_all(self) -> int:
        """Clear cache and reload all blueprints.

        Returns:
            Number of blueprints loaded.
        """
        self._blueprints.clear()
        self.load_all()
        return len(self._blueprints)

    @staticmethod
    def _load_file(path: Path) -> AisopBlueprint:
        """Load and parse a single .aisop.json or .aisip.json file.

        Supports formats:
        - Flat dict: ``{name, workflow, functions, ...}`` (legacy)
        - AISOP V1.0.0: ``[{role: "system", ...}, {role: "user", content: {aisop: ...}}]``
        - AISIP V1.0.0: ``[{role: "system", ...}, {role: "user", content: {aisip: ...}}]``
        """
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)

        # Standard V1.0.0 format: list of role/content messages
        if isinstance(data, list):
            data = _v1_to_flat(data, path)

        return AisopBlueprint(**data)


def _v1_to_flat(messages: list, path: Path) -> dict:
    """Convert AISOP/AISIP V1.0.0 ``[{role, content}, ...]`` to flat dict."""
    system_content = {}
    user_content = {}
    for msg in messages:
        role = msg.get("role", "")
        if role == "system":
            system_content = msg.get("content", {})
        elif role == "user":
            user_content = msg.get("content", {})

    sc = system_content if isinstance(system_content, dict) else {}
    uc = user_content if isinstance(user_content, dict) else {}

    # Detect protocol from user content
    if "aisip" in uc:
        protocol = "aisip"
        name = path.stem.removesuffix(".aisip")
    else:
        protocol = "aisop"
        name = path.stem.removesuffix(".aisop")

    # functions: V1.0.0 has step dicts + extension keys — preserve structure
    raw_funcs = uc.get("functions", {})
    functions = {}
    for key, val in raw_funcs.items():
        if isinstance(val, dict):
            functions[key] = val  # preserve dict for extension parsing
        else:
            functions[key] = str(val)

    # tools: V1.0.0 stores as string list; convert to AisopTool-compatible dicts
    raw_tools = sc.get("tools", [])
    tools = []
    for t in raw_tools:
        if isinstance(t, str):
            tools.append({"name": t})
        elif isinstance(t, dict):
            tools.append(t)

    # v14 optional fields
    capabilities = sc.get("capabilities", None)
    if capabilities and isinstance(capabilities, dict):
        capabilities = {
            "offered": capabilities.get("offered", []),
            "required": capabilities.get("required", []),
        }

    # Protocol-specific flow field
    if protocol == "aisip":
        workflow = ""
        flow = uc.get("aisip", {})
    else:
        workflow = uc.get("aisop", {}).get("main", "")
        flow = {}

    return {
        "name": name,
        "version": sc.get("version", "1.0"),
        "description": sc.get("description", sc.get("summary", "")),
        "protocol": protocol,
        "workflow": workflow,
        "flow": flow,
        "functions": functions,
        "tools": tools,
        "system_directive": sc.get("system_prompt", ""),
        "metadata": {
            "protocol": sc.get("protocol", ""),
            "id": sc.get("id", ""),
            "verified_on": sc.get("verified_on", []),
        },
        "registry_uri": sc.get("registry_uri", None),
        "capabilities": capabilities,
        "ui": sc.get("ui", None),
        "identity": sc.get("identity", None),
    }
