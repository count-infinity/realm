"""
Exit pairing — the two faces of one door as a first-class relationship.

``@dig`` creates a passage as TWO independent exit objects (A->B and
B->A); anything that treats them as one door (the mirror pattern's
``ON_OPEN``/``ON_LOCK`` hooks copying state to the far side) needs each
side to know its sibling. That link lives in a ``partner`` attribute
holding the far exit's ``#id`` — and because a stored reference is
stale-able, the engine owns every write path that could invalidate it:

- ``@dig`` (two-way) pairs the newborn exits automatically.
- ``@link`` / ``@unlink`` on a paired exit DISSOLVES the pairing on both
  sides, loudly — retargeting an exit never silently drags a mirror
  along to an unrelated door.
- ``@destroy`` of one side clears the survivor's ``partner``.
- ``@pair a = b`` (re)marries by hand — hand-built ``@open`` exits,
  double doors between the same two rooms, re-pairing after a relink.

``partner`` stays an ordinary attribute (scripts read it with
``V('partner')``; exotic mirrors like a lever-and-bridge may still set
their own on non-exits) — these helpers just keep the EXIT pairing
consistent. The ``#id`` form remaps on fresh-id import (worldio), so a
cloned area's doors re-wire to their own copies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

PARTNER_ATTR = "partner"


def partner_of(exit_obj: GameObject) -> GameObject | None:
    """The live object this exit's ``partner`` points at, or None."""
    from realm.persistence.manager import get_active_manager

    ref = exit_obj.db.get(PARTNER_ATTR)
    if not isinstance(ref, str) or not ref.startswith('#'):
        return None
    manager = get_active_manager()
    return manager.get_cached(ref[1:]) if manager else None


def pair_exits(a: GameObject, b: GameObject) -> None:
    """Marry two exits: each side's ``partner`` names the other."""
    a.db.set(PARTNER_ATTR, '#' + b.id)
    b.db.set(PARTNER_ATTR, '#' + a.id)


def dissolve_pairing(exit_obj: GameObject) -> GameObject | None:
    """Clear this exit's pairing on BOTH sides (if the far side still
    points back here). Returns the former partner, or None if the exit
    was unpaired."""
    former = partner_of(exit_obj)
    if former is not None and former.db.get(PARTNER_ATTR) == '#' + exit_obj.id:
        former.db.delete(PARTNER_ATTR)
    if exit_obj.db.get(PARTNER_ATTR) is not None:
        exit_obj.db.delete(PARTNER_ATTR)
        return former
    return None


__all__ = ["PARTNER_ATTR", "partner_of", "pair_exits", "dissolve_pairing"]
