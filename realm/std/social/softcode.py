"""
Softcode functions: Disposition and reactions.

The ``social`` feature declares each (``feature.py``, with its group and
flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

def disposition(frame, npc, other=None) -> int:
    """How npc feels about other (default: the enactor).

    Example: disposition(me, enactor) >= 2
    """
    from realm.std.social.disposition import get_disposition
    npc_obj = frame.resolve(npc)
    other_obj = frame.resolve(other) if other is not None else frame.enactor
    if npc_obj is None or other_obj is None:
        return 0
    return get_disposition(npc_obj, other_obj)

def adjust_disposition(frame, npc, other, delta: int) -> bool:
    """
    Shift an NPC's attitude. Authority: the executor must control
    the NPC (its own opinions) — you can't script others' minds
    about yourself.

    Example: adjust_disposition(me, enactor, 1)
    """
    from realm.std.social.disposition import adjust_disposition as _adjust
    npc_obj = frame.resolve(npc)
    other_obj = frame.resolve(other)
    if npc_obj is None or other_obj is None:
        return False
    if not frame.may_mutate(npc_obj):
        return False
    _adjust(npc_obj, other_obj, int(delta))
    frame.command_queue.append(('save', npc_obj, ''))
    return True

def reaction_roll(frame, npc, other=None, modifier: int = 0) -> int:
    """Memoized first-impression roll (npc must be in executor's reach).

    Example: reaction_roll(me)
    """
    from realm.std.social.disposition import reaction_roll as _roll
    npc_obj = frame.resolve(npc)
    other_obj = frame.resolve(other) if other is not None else frame.enactor
    if npc_obj is None or other_obj is None or not frame.in_reach(npc_obj):
        return 0
    value = _roll(npc_obj, other_obj, int(modifier))
    frame.command_queue.append(('save', npc_obj, ''))
    return value
