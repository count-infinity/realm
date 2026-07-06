"""
Forcing and possession: run a command AS another object, through the
REAL dispatcher — normal parsing, permissions, and propagation apply.

Authority is the one predicate (permissions.locks.controls): you force
what you control. Possession of a PLAYER is therefore admin-only by
default — unless the player opts in with a control lock
(``@lock/control me = caller.has_tag('ghost')``), which is exactly how
a haunted-house ghost gets its victim.

The puppet "session" forwards anything the puppet would see to the
watcher (the forcer), prefixed — you experience what your puppet does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

# A forced command can itself force (a chain of puppets); cap it.
MAX_FORCE_DEPTH = 3
_force_depth = 0


class PuppetSession:
    """The minimal session surface the dispatcher needs (.player, .send)."""

    def __init__(self, player: GameObject, watcher: Any = None):
        self.player = player
        self.watcher = watcher  # a real Session to forward output to

    async def send(self, message: str) -> None:
        if self.watcher is not None:
            await self.watcher.send(f"[{self.player.name}] {message}")

    async def flush_output(self) -> None:  # session-manager compatibility
        pass


async def force_command(
    dispatcher: Any,
    target: GameObject,
    command: str,
    *,
    watcher: Any = None,
) -> bool:
    """
    Execute ``command`` as ``target`` through the dispatcher. The CALLER
    is responsible for the authority check (controls). Returns False if
    the puppet-chain depth cap is hit.
    """
    global _force_depth
    if _force_depth >= MAX_FORCE_DEPTH:
        return False
    _force_depth += 1
    try:
        await dispatcher.dispatch(PuppetSession(target, watcher), command)
    finally:
        _force_depth -= 1
    return True


__all__ = ["PuppetSession", "force_command", "MAX_FORCE_DEPTH"]
