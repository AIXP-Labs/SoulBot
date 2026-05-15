"""LlmRequest / LlmResponse / GenerateContentConfig — LLM communication models."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..events.event import Content

if TYPE_CHECKING:
    from ..tools.base_tool import BaseTool


class GenerateContentConfig(BaseModel):
    """Configuration for a model generation call."""

    temperature: float = 0.7
    max_output_tokens: int = 4096
    top_p: float = 1.0
    stop_sequences: list[str] = Field(default_factory=list)


class LlmRequest(BaseModel):
    """A request to an LLM, built progressively by processors or the agent."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: Optional[str] = None
    """Model identifier (e.g. 'gpt-4o-mini')."""

    contents: list[Content] = Field(default_factory=list)
    """Conversation history (user + model messages)."""

    system_instruction: Optional[str] = None
    """System-level instruction text."""

    config: GenerateContentConfig = Field(default_factory=GenerateContentConfig)
    """Generation parameters."""

    tools_dict: dict[str, Any] = Field(default_factory=dict, exclude=True)
    """name → BaseTool mapping (used to look up tools for execution)."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    """Arbitrary metadata carried through the pipeline (e.g. user_id)."""

    def append_instructions(self, instructions: list[str]) -> None:
        """Append instruction text(s) to the system instruction."""
        if not instructions:
            return
        new_text = "\n\n".join(instructions)
        if self.system_instruction:
            self.system_instruction += "\n\n" + new_text
        else:
            self.system_instruction = new_text

    def append_tools(self, tools: list["BaseTool"]) -> None:
        """Register tools into the request."""
        for tool in tools:
            self.tools_dict[tool.name] = tool

    def get_tools_schema(self) -> list[dict]:
        """Return OpenAI-compatible function schemas for all registered tools."""
        schemas = []
        for tool in self.tools_dict.values():
            decl = tool.get_declaration()
            if decl:
                schemas.append({"type": "function", "function": decl})
        return schemas


class LlmResponse(BaseModel):
    """A response from an LLM."""

    content: Optional[Content] = None
    """The generated content."""

    partial: bool = False
    """True if this is a streaming chunk."""

    error_code: Optional[str] = None
    error_message: Optional[str] = None

    usage: Optional[dict[str, Any]] = None
    """Token usage info (model-dependent structure)."""
