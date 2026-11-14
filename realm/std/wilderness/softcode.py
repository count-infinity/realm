"""
Softcode functions of the ``wilderness`` feature.

The feature declares each (``feature.py``, with its group and flags); the
first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def enter_wilderness(frame, player: GameObject | str | None,
                     region: str, x, y) -> bool:
    """
    Send a player to the wilderness cell at ``(region, x, y)``,
    materializing it on demand — the scripted seam into a
    coordinate-keyed region. (Walking between cells needs no softcode:
    the cells' exits are real exits with deferred destinations.)

    Callable when the executor controls the player, or the player is
    the consenting enactor. Entry is gated by the region master's
    ENTER lock, checked against the player being sent. Returns whether
    the entry was *authorized and queued*; the materialize-and-move
    happens after the script ends.

    Example: enter_wilderness(enactor, 'wilds', 10, 10)
    """
    from realm.permissions.locks import LockType, check_lock
    from realm.std.wilderness.cells import get_region

    target = frame.resolve(player)
    if target is None:
        return False
    if not (frame.may_relocate(target)
            or (target is frame.enactor and frame.enactor_consent)):
        return False
    try:
        x_i, y_i = int(x), int(y)
    except (TypeError, ValueError):
        return False
    region_obj = get_region(str(region))
    if region_obj is None:
        return False
    if not check_lock(region_obj, LockType.ENTER, target):
        return False
    frame.command_queue.append(
        ('wilderness', target, (str(region), x_i, y_i)))
    return True
