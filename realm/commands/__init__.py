"""
Command system for REALM.

Provides command registration, parsing, and execution.
"""

from realm.server.dispatcher import (
    Command,
    CommandContext,
    CommandDispatcher,
)

__all__ = [
    "CommandDispatcher",
    "CommandContext",
    "Command",
]
