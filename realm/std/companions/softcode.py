"""
Softcode functions: companions.

The ``companions`` feature declares each (``feature.py``, with its group
and flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.std.companions.companions import bond_refusal, companions_of, master_of

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def master(frame, obj: GameObject | str | None) -> GameObject | None:
    """The character ``obj`` is a companion of (a pet's owner, a charmed
    creature's charmer), or None.

    Example: pemit(master(me), 'Woof.') if master(me) else None
    """
    target = frame.resolve(obj)
    return master_of(target) if target is not None else None


def companions(frame, obj: GameObject | str | None) -> list[GameObject]:
    """``obj``'s companions, wherever they are.

    Example: len(companions(enactor))
    """
    target = frame.resolve(obj)
    return companions_of(target) if target is not None else []


def set_master(frame, obj: GameObject | str | None,
               master: GameObject | str | None) -> bool:
    """Make ``obj`` (an NPC the executor controls) ``master``'s companion:
    it follows and obeys ``order``. False, with nothing changed, past
    ``master``'s companion limit or ``COMPANION_LEVEL_DIFF``, or for a
    player. The bond happens after the script (``ON_BOND`` fires then).

    Example: set_master(me, enactor)
    """
    npc = frame.controlled(obj)
    owner = frame.resolve(master)
    if npc is None or owner is None or bond_refusal(npc, owner) is not None:
        return False
    frame.command_queue.append(('companion_bond', npc, owner))
    return True


def release(frame, obj: GameObject | str | None) -> bool:
    """Free ``obj`` (an NPC the executor controls) from its master; it
    stays where it is. Happens after the script (``ON_RELEASE`` fires).

    Example: release(me)
    """
    npc = frame.controlled(obj)
    if npc is None or master_of(npc) is None:
        return False
    frame.command_queue.append(('companion_release', npc, None))
    return True


async def queued_bond(engine, frame, npc, owner) -> None:
    """Queued by softcode ``set_master()``."""
    from realm.std.companions.companions import set_master as bond
    await bond(npc, owner, how="set")


async def queued_release(engine, frame, npc, _payload) -> None:
    """Queued by softcode ``release()``."""
    from realm.std.companions.companions import set_master as bond
    await bond(npc, None, reason="released")


__all__ = ["companions", "master", "queued_bond", "queued_release", "release", "set_master"]
