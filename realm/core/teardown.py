"""
Shared teardown for ephemeral rooms — the R9 contract (see
docs/design/wilderness-requirements.md): destroying a room never orphans
an object. Both reapers (``instances.destroy_instance``,
``wilderness``'s cell teardown) funnel their occupants through
``release_contents`` so the policy can't drift between them.

Disposition of a torn-down room's occupants:

- a **player** is evacuated down the ladder: ``return_room`` → their
  ``home`` → the start room (their inventory rides along);
- an object **doomed** with the room (it carries the copy's own tags —
  cloned template contents, the cell's exits) has its *contents* released
  first, then the shell is left for the caller to delete with the room;
- a **player-owned** object is delivered to its owner's ``home`` (else
  the start-room floor) — a dropped sword follows its owner, loudly;
- anything else — unowned, or owned by a non-player — has its contents
  released first, then is **deliberately destroyed** (logged). Ephemeral
  rooms are not storage; loud deletion beats silent limbo.

The disposition recurses through containment, so a player sitting inside
a vehicle inside the room — or a sword inside a doomed chest — is never
deleted out from under or left dangling inside a destroyed shell.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.query import find_objects

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

EPHEMERAL_TAG = "ephemeral"          # transient — never persisted (see manager)


def start_room_floor() -> GameObject | None:
    """The world's guaranteed landing spot (tag ``start_room``)."""
    return next(iter(find_objects(tag="start_room")), None)


def subtree_has_player(root: GameObject) -> bool:
    """Is a player anywhere in ``root``'s containment subtree? The
    occupancy check for reapers — a player inside a vehicle inside a cell
    still holds the cell open."""
    seen = {root.id}
    stack = list(root.contents)
    while stack:
        obj = stack.pop()
        if obj.id in seen:
            continue
        seen.add(obj.id)
        if obj.has_tag("player"):
            return True
        stack.extend(obj.contents)
    return False


def evacuation_room(persistence, occupant: GameObject,
                    return_room: GameObject | None = None) -> GameObject | None:
    """Where to send a player displaced by a room's destruction: the
    copy's ``return_room``, else their ``home``, else the world's start
    room. The start-room floor means an evacuee is never stranded at
    ``None`` while a world exists (see vision invariant #10 — fail loud,
    not into the void)."""
    home = (persistence.get_cached(occupant.db.get("home"))
            if persistence else None)
    return return_room or home or start_room_floor()


def owner_refuge(persistence, owner: GameObject) -> GameObject | None:
    """Where a player's property lands when the room under it is torn
    down: the owner's ``home``, else the start-room floor."""
    home = (persistence.get_cached(owner.db.get("home"))
            if persistence else None)
    return home or start_room_floor()


async def release_contents(
    room: GameObject, persistence, *,
    return_room: GameObject | None = None,
    doomed_ids: frozenset[str] | set[str] = frozenset(),
) -> None:
    """Apply the R9 disposition to every occupant of ``room``, recursing
    through containment (see module docstring). ``doomed_ids`` are the ids
    being deleted *with* the room — their contents are released here, but
    the shells are destroyed by the caller."""
    await _release(room, persistence, return_room=return_room,
                   doomed_ids=doomed_ids, seen={room.id})


async def _release(container: GameObject, persistence, *,
                   return_room, doomed_ids, seen: set[str]) -> None:
    for occupant in list(container.contents):
        if occupant.id in seen:     # containment cycle guard
            continue
        seen.add(occupant.id)
        if occupant.has_tag("player"):
            occupant.location = evacuation_room(
                persistence, occupant, return_room)
            continue
        if occupant.id in doomed_ids:
            # The shell dies with the room — but whatever sits INSIDE it
            # (a player's sword in a doomed chest) still gets disposed.
            await _release(occupant, persistence, return_room=return_room,
                           doomed_ids=doomed_ids, seen=seen)
            continue
        owner = occupant.owner
        if owner is not None and owner.has_tag("player"):
            refuge = owner_refuge(persistence, owner)
            if refuge is not None:
                occupant.location = refuge
                if persistence is not None:
                    await persistence.save(occupant)
                logger.info(
                    f"Teardown of {container.name}: sent {occupant.name} "
                    f"({occupant.id}) to {owner.name}'s refuge {refuge.name}")
                continue
            # No home, no start room — a bare test world; fall through to
            # deletion rather than leave a dangling location.
        # To be destroyed: empty it first, then delete the shell.
        await _release(occupant, persistence, return_room=return_room,
                       doomed_ids=doomed_ids, seen=seen)
        occupant.location = None
        if persistence is not None:
            await persistence.delete(occupant)
        logger.info(
            f"Teardown of {container.name}: destroyed "
            f"{'unowned' if owner is None else 'non-player-owned'} "
            f"occupant {occupant.name} ({occupant.id})")


__all__ = [
    "EPHEMERAL_TAG",
    "start_room_floor",
    "subtree_has_player",
    "evacuation_room",
    "owner_refuge",
    "release_contents",
]
