"""BaseTool — abstract base class for all tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from ..agents.context import ToolContext


class BaseTool(ABC):
    """Base class for all tools.

    Subclasses must implement :meth:`get_declaration` and :meth:`run_async`.
    """

    def __init__(
        self, *, name: str, description: str = "", timeout: float | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.timeout = timeout  # per-tool timeout (seconds), overrides RunConfig

    # ------------------------------------------------------------------
    # Schema — returns OpenAI-compatible function schema
    # ------------------------------------------------------------------

    @abstractmethod
    def get_declaration(self) -> Optional[dict]:
        """Return an OpenAI-compatible function schema dict.

        Example return value::

            {
                "name": "get_weather",
                "description": "Get the weather for a city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"}
                    },
                    "required": ["city"]
                }
            }

        Return ``None`` if this tool does not need a schema (e.g. built-in
        tools that only modify the request).
        """
        ...

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    @abstractmethod
    async def run_async(
        self, *, args: dict[str, Any], tool_context: "ToolContext"
    ) -> Any:
        """Execute the tool with the given arguments.

        Args:
            args: Arguments filled in by the LLM.
            tool_context: The current invocation context.

        Returns:
            The tool result (will be serialized to JSON for the LLM).
        """
        ...
