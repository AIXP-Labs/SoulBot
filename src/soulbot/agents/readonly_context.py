"""ReadonlyContext — read-only view of the invocation context."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..sessions.session import Session
    from .invocation_context import InvocationContext


class ReadonlyContext:
    """Read-only base context available to all callbacks.

    Provides safe, read-only access to session data and agent metadata.
    """

    def __init__(
        self,
        invocation_context: "InvocationContext",
        agent_name: str = "",
    ) -> None:
        self._invocation_context = invocation_context
        self._agent_name = agent_name

    @property
    def agent_name(self) -> str:
        return self._agent_name

    @property
    def invocation_context(self) -> "InvocationContext":
        return self._invocation_context

    @property
    def session(self) -> "Session":
        return self._invocation_context.session

    @property
    def invocation_id(self) -> str:
        return self._invocation_context.invocation_id
