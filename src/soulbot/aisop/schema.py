"""AISOP/AISIP blueprint schema — Pydantic models for .aisop.json and .aisip.json files."""

from typing import Any

from pydantic import BaseModel, Field


class AisopToolAnnotations(BaseModel):
    """Tool behavior annotations (AIAP v14 P2-1)."""

    read_only: bool = False
    destructive: bool = False
    idempotent: bool = False
    open_world: bool = False


class AisopTool(BaseModel):
    """A tool declaration within an AISOP blueprint."""

    name: str
    description: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    required: bool = True
    fallback: str | None = None
    annotations: AisopToolAnnotations | None = None
    mcp_server: dict[str, Any] | None = None


class AisopCapabilities(BaseModel):
    """Runtime capability declaration (AIAP v14 P2-3)."""

    offered: list[str] = Field(default_factory=list)
    required: list[str] = Field(default_factory=list)


class AisopBlueprint(BaseModel):
    """A blueprint defining agent behavior via JSON (AISOP or AISIP).

    Attributes:
        name: Unique blueprint identifier.
        version: Semantic version string.
        description: Human-readable description.
        protocol: Detected protocol type ("aisop" or "aisip").
        workflow: Mermaid flowchart string (AISOP) or empty string (AISIP).
        flow: JSON flow graph dict (AISIP) or empty dict (AISOP).
        functions: Mapping of node name to action description.
        tools: List of tool declarations available to the agent.
        system_directive: Additional system-level instructions.
        metadata: Arbitrary key-value metadata.
        registry_uri: Optional federated registry endpoint.
        capabilities: Runtime capability declaration.
        ui: UI component declarations.
        identity: Program identity verification.
    """

    name: str
    version: str = "1.0"
    description: str = ""
    protocol: str = "aisop"
    workflow: str = ""
    flow: dict[str, Any] = Field(default_factory=dict)
    functions: dict[str, Any] = Field(default_factory=dict)
    tools: list[AisopTool] = Field(default_factory=list)
    system_directive: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    registry_uri: str | None = None
    capabilities: AisopCapabilities | None = None
    ui: dict[str, Any] | None = None
    identity: dict[str, Any] | None = None
