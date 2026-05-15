"""history_tool — search_history FunctionTool factory (Doc 22 Step 8)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..history.base_history_service import BaseChatHistoryService


def create_history_tool(
    history_service: BaseChatHistoryService,
    *,
    default_agent: str = "",
    user_id: str = "default",
):
    """Create a ``search_history`` async function bound to *history_service*.

    The returned function can be wrapped by :class:`FunctionTool` or passed
    directly to an agent's ``tools`` list (``LlmAgent._ensure_tool`` will
    auto-wrap it).

    Args:
        history_service: The chat history backend to query.
        default_agent: Agent name used when the caller omits *agent*.
        user_id: Fixed user id (single-user framework).
    """

    async def search_history(
        keyword: str = "",
        agent: str = "",
        limit: int = 10,
    ) -> str:
        """Search chat history.

        Args:
            keyword: Search keyword. Empty returns the most recent messages.
            agent: Agent name to search. Empty searches the current agent.
            limit: Maximum number of messages to return.

        Returns:
            Formatted history messages, one per line.
        """
        target_agent = agent or default_agent
        if not target_agent:
            return "No agent specified."

        if keyword:
            messages = await history_service.search(
                user_id, target_agent, keyword, limit=limit,
            )
        else:
            messages = await history_service.get_agent_history(
                user_id, target_agent, limit=limit,
            )

        if not messages:
            return "No history found."

        lines: list[str] = []
        for m in messages:
            dt = datetime.fromtimestamp(m.created_at).strftime("%m-%d %H:%M")
            role = "User" if m.role == "user" else "AI"
            agent_tag = f" [{m.agent}]" if not agent and not default_agent else ""
            content = m.content[:200]
            if len(m.content) > 200:
                content += "..."
            lines.append(f"[{dt}]{agent_tag} {role}: {content}")

        return "\n".join(lines)

    return search_history
