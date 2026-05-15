"""TransferToAgentTool — built-in tool for transferring control between agents."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from .base_tool import BaseTool

if TYPE_CHECKING:
    from ..agents.context import ToolContext


class TransferToAgentTool(BaseTool):
    """A special tool that the LLM calls to transfer control to another agent.

    This is automatically injected into LlmAgent when it has sub_agents
    or when transfer to parent/peers is allowed.
    """

    TOOL_NAME = "transfer_to_agent"

    def __init__(self, agent_names: list[dict[str, str]]) -> None:
        """
        Args:
            agent_names: List of dicts with 'name' and 'description' keys
                for each transferable agent.
        """
        super().__init__(
            name=self.TOOL_NAME,
            description="Transfer the conversation to another agent.",
        )
        self.agent_names = agent_names

    def get_declaration(self) -> Optional[dict]:
        names = [a["name"] for a in self.agent_names]
        descriptions = "\n".join(
            f"- {a['name']}: {a.get('description', 'No description')}"
            for a in self.agent_names
        )
        return {
            "name": self.TOOL_NAME,
            "description": (
                "Transfer the conversation to another specialized agent. "
                "Available agents:\n" + descriptions
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": names,
                        "description": "The name of the agent to transfer to.",
                    }
                },
                "required": ["agent_name"],
            },
        }

    async def run_async(
        self, *, args: dict[str, Any], tool_context: "ToolContext"
    ) -> Any:
        agent_name = args.get("agent_name", "")
        if not agent_name:
            return {"error": "agent_name is required"}

        valid_names = {a["name"] for a in self.agent_names}
        if agent_name not in valid_names:
            return {
                "error": f"Unknown agent '{agent_name}'. Available: {sorted(valid_names)}"
            }

        # Signal the transfer via EventActions
        tool_context.actions.transfer_to_agent = agent_name
        return {"status": "transferring", "agent": agent_name}
