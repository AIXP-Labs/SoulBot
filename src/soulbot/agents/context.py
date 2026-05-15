"""Context — unified writable context for callbacks and tools.

In Google ADK, ``CallbackContext`` and ``ToolContext`` are actually the same
class.  We follow that pattern: a single :class:`Context` with type aliases.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from ..events.event_actions import EventActions
from ..sessions.state import State
from .readonly_context import ReadonlyContext

if TYPE_CHECKING:
    from .invocation_context import InvocationContext


class Context(ReadonlyContext):
    """Unified writable context used by both callbacks and tools.

    Attributes:
        state: Delta-aware state object; writes are automatically tracked.
        actions: Accumulated side-effects for the current event.
    """

    def __init__(
        self,
        invocation_context: "InvocationContext",
        agent_name: str = "",
        function_call_id: Optional[str] = None,
    ) -> None:
        super().__init__(invocation_context, agent_name)
        self._event_actions = EventActions()
        self._function_call_id = function_call_id

    # -- state ---------------------------------------------------------------

    @property
    def state(self) -> State:
        """Delta-aware state.  Writes are auto-tracked."""
        return self._invocation_context.session.state

    # -- actions -------------------------------------------------------------

    @property
    def actions(self) -> EventActions:
        """Accumulated side-effects for the current step."""
        return self._event_actions

    # -- function call id (set when invoked from a tool) ---------------------

    @property
    def function_call_id(self) -> Optional[str]:
        return self._function_call_id

    # -- convenience helpers -------------------------------------------------

    def commit_state_delta(self) -> dict[str, object]:
        """Flush pending state changes into ``actions.state_delta`` and return them.

        The delta is cleared only **after** it has been successfully written
        into ``actions.state_delta``, preventing data loss if an exception
        occurs between the two steps.
        """
        if not self.state.has_delta:
            return {}
        # Snapshot first, write into actions, then clear — atomic semantics.
        delta = dict(self.state._delta)
        self._event_actions.state_delta.update(delta)
        self.state._delta.clear()
        return delta


# Type aliases — API-compatible with Google ADK naming
CallbackContext = Context
ToolContext = Context
