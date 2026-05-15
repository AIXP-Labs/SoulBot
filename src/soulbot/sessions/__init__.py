from .base_session_service import BaseSessionService
from .constants import DEFAULT_USER_ID, resolve_cli_name, resolve_db_path
from .in_memory_session_service import InMemorySessionService
from .session import Session
from .state import State

__all__ = [
    "BaseSessionService",
    "DEFAULT_USER_ID",
    "InMemorySessionService",
    "Session",
    "State",
    "resolve_cli_name",
    "resolve_db_path",
]

# Lazy import for optional dependency
def __getattr__(name):
    if name == "DatabaseSessionService":
        from .database_session_service import DatabaseSessionService
        return DatabaseSessionService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
