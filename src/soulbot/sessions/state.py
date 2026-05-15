"""State — delta-aware dictionary for session state management.

Writes are automatically tracked in an internal ``_delta`` dict so they can
be flushed into ``EventActions.state_delta`` at commit time.
"""

from __future__ import annotations

from collections.abc import Iterator


class State:
    """Session state with automatic change tracking.

    Prefixes control the *scope* of a key:

    * ``app:``  — shared across all users/sessions for the application
    * ``user:`` — shared across all sessions for a given user
    * ``temp:`` — ephemeral, never persisted (discarded after invocation)
    * *(none)*  — scoped to the current session
    """

    APP_PREFIX = "app:"
    USER_PREFIX = "user:"
    TEMP_PREFIX = "temp:"

    def __init__(self, initial: dict[str, object] | None = None):
        self._value: dict[str, object] = dict(initial) if initial else {}
        self._delta: dict[str, object] = {}

    # -- dict-like interface ------------------------------------------------

    def __getitem__(self, key: str) -> object:
        return self._value[key]

    def __setitem__(self, key: str, value: object) -> None:
        self._value[key] = value
        self._delta[key] = value

    def __delitem__(self, key: str) -> None:
        del self._value[key]
        self._delta[key] = None  # signal deletion

    def __contains__(self, key: str) -> bool:
        return key in self._value

    def __iter__(self) -> Iterator[str]:
        return iter(self._value)

    def __len__(self) -> int:
        return len(self._value)

    def get(self, key: str, default: object = None) -> object:
        return self._value.get(key, default)

    def keys(self):
        return self._value.keys()

    def values(self):
        return self._value.values()

    def items(self):
        return self._value.items()

    def to_dict(self) -> dict[str, object]:
        """Return a plain dict snapshot (for serialization)."""
        return dict(self._value)

    # -- delta management ---------------------------------------------------

    @property
    def has_delta(self) -> bool:
        return len(self._delta) > 0

    def commit_delta(self) -> dict[str, object]:
        """Return and clear the pending delta."""
        delta = dict(self._delta)
        self._delta.clear()
        return delta

    def apply_delta(self, delta: dict[str, object]) -> None:
        """Apply an external delta (e.g. from an Event) to the state.

        Keys with value ``None`` are deleted.  Keys prefixed with
        ``temp:`` are stored but will **not** be persisted by the session
        service.
        """
        for key, value in delta.items():
            if value is None:
                self._value.pop(key, None)
            else:
                self._value[key] = value

    def __repr__(self) -> str:
        return f"State({self._value!r})"
