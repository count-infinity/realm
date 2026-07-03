"""
Command system for REALM.

Provides command registration, parsing, and execution.
"""

from realm.server.dispatcher import (
    Command,
    CommandContext,
    CommandDispatcher,
    command,
    register_commands,
)

__all__ = [
    "CommandDispatcher",
    "CommandContext",
    "Command",
    "command",
    "register_commands",
]
