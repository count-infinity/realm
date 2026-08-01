"""Back-compat shim: the command dispatcher lives in ``realm.commands``.

``Command``, ``CommandContext`` and ``CommandDispatcher`` are the command
system's core types, so they moved home to ``realm/commands/dispatcher.py``
(2026-07-31). That flipped the old layering cycle — ``realm.commands``
re-exporting *from* the server package while the server imported the
command modules — into the one correct arrow: server → commands.

This module survives only so existing imports of
``realm.server.dispatcher`` (tests, external game code) keep working.
New code should import from ``realm.commands`` (or
``realm.commands.dispatcher`` for the aux symbols).
"""

from __future__ import annotations

from realm.commands.dispatcher import (
    DIRECTION_ALIASES,
    TOKEN_MAP,
    Command,
    CommandContext,
    CommandDispatcher,
    CommandHandler,
)

__all__ = [
    "Command",
    "CommandContext",
    "CommandDispatcher",
    "CommandHandler",
    "DIRECTION_ALIASES",
    "TOKEN_MAP",
]
