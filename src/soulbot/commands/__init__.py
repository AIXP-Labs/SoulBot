"""Commands — AI command protocol for text-embedded service invocation."""

from .parser import ParsedCommand, parse_commands, CMD_PREFIX, CMD_SUFFIX
from .executor import CommandExecutor

__all__ = [
    "ParsedCommand",
    "parse_commands",
    "CMD_PREFIX",
    "CMD_SUFFIX",
    "CommandExecutor",
]
