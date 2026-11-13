"""
Softcode functions: Disposition and reactions.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    pass

@softfn(owner='social', group='NPCs & behaviors', readonly=True)
def disposition(frame, npc, other=None) -> int:
    """How npc feels about other (default: the enactor).

    Example: disposition(me, enactor) >= 2
    """
    from realm.core.disposition import get_disposition
    npc_obj = frame.resolve(npc)
    other_obj = frame.resolve(other) if other is not None else frame.enactor
    if npc_obj is None or other_obj is None:
        return 0
    return get_disposition(npc_obj, other_obj)

@softfn(owner='social', group='NPCs & behaviors')
def adjust_disposition(frame, npc, other, delta: int) -> bool:
    """
    Shift an NPC's attitude. Authority: the executor must control
    the NPC (its own opinions) — you can't script others' minds
    about yourself.

    Example: adjust_disposition(me, enactor, 1)
    """
    from realm.core.disposition import adjust_disposition as _adjust
    npc_obj = frame.resolve(npc)
    other_obj = frame.resolve(other)
    if npc_obj is None or other_obj is None:
        return False
    if not frame.may_mutate(npc_obj):
        return False
    _adjust(npc_obj, other_obj, int(delta))
    frame.command_queue.append(('save', npc_obj, ''))
    return True

@softfn(owner='social', group='NPCs & behaviors')
def reaction_roll(frame, npc, other=None, modifier: int = 0) -> int:
    """Memoized first-impression roll (npc must be in executor's reach).

    Example: reaction_roll(me)
    """
    from realm.core.disposition import reaction_roll as _roll
    npc_obj = frame.resolve(npc)
    other_obj = frame.resolve(other) if other is not None else frame.enactor
    if npc_obj is None or other_obj is None or not frame.in_reach(npc_obj):
        return 0
    value = _roll(npc_obj, other_obj, int(modifier))
    frame.command_queue.append(('save', npc_obj, ''))
    return value
