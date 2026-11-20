"""
Zone reset — presence-gated scheduled repopulation of a zone's canonical
contents (SMAUG ``area_update``/``reset_area``; tbaMUD zone reset).

A **behavior on the zone master**, not a kernel sweep: the master is the
area's owner object, so repop composes onto it the way every other REALM
behavior does (`SpawnerBehavior`, `DecayBehavior`…). Attach with
``@behavior <master> = zone_reset``; configure with plain ``@set``:

- ``db.reset_interval`` (seconds) — how often the zone tries to reset.
- ``db.reset_spec`` — ``[{"prototype": {...}, "room": <id-or-tag>,
  "count": N}, ...]`` (the spawner's prototype vocabulary).

Each reset **clears this master's prior spawns and reloads them fresh** (the
SMAUG "reset clears then repops" semantic) — no survivor counting, no
accumulation, and a removed spec entry's mobs vanish with the clear. A
cleared spawn takes what it carries with it (a prototype's ``contents``
return with the reload); a player's own thing inside goes to its owner. Safe
because a reset only runs when the zone is **empty of players**: an occupied
zone defers (its timer keeps counting) and repops the instant it empties —
so the area never returns to canonical while someone's watching, by design.
Anything in the zone's rooms with a ``reset_tags`` attribute (``{tag:
present}``) gets those tags put back at each reset: an imported ROM door
(``{"closed": true, "locked": true}``) closes and locks again, as ROM's
area reset sets every exit back to its reset flags. The tags are set
directly, one face at a time; each face carries its own. ``ON_RESET`` fires
on the master for everything else (clear litter, reseed).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.behaviors import Behavior
from realm.core.events import fire_event
from realm.core.query import find_objects
from realm.core.teardown import release_contents
from realm.core.world import get_world
from realm.core.zones import zone_rooms, zone_tags
from realm.std.spawning.spawner import spawn_tracked

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def now() -> float:
    """The wall clock zone resets are timed by (tests replace it)."""
    return time.time()


def _resolve_room(ref, persistence) -> GameObject | None:
    """A reset-spec ``room`` is an object id (``#id`` / bare) or a room tag
    (first matching room)."""
    if not ref:
        return None
    ref = str(ref).lstrip("#")
    if persistence is not None:
        obj = persistence.get_cached(ref)
        if obj is not None:
            return obj
    rooms = find_objects(tag="room", tags=[ref])
    return rooms[0] if rooms else None


class ZoneResetBehavior(Behavior):
    """Repop a zone's canonical contents on a timer, while nobody's inside."""

    behavior_id = "zone_reset"
    blurb = ("repops a zone on a timer while nobody is inside; configured "
             "by reset_interval/reset_spec attributes on the master")

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, master: GameObject, delta: float) -> None:
        interval = master.db.get("reset_interval")
        if not interval:
            return
        at = now()
        if at - float(master.db.get("last_reset") or 0) < float(interval):
            return
        # Presence gate — never repop on top of players; defer (leave
        # last_reset old) so it fires the moment the zone empties.
        for zone in zone_tags(master):
            for room in zone_rooms(zone):
                if any(c.is_player for c in room.contents):
                    return
        await self._reset(master)
        master.db.set("last_reset", at)

    async def _reset(self, master: GameObject) -> None:

        persistence = get_world().store
        marker = f"reset:{master.id}"

        # Custom repop first — litter cleared, randomness reseeded — before
        # the canonical mob wipe/reload.
        await fire_event(None, master, ActionType.ON_RESET)

        # Doors (anything with ``reset_tags``) back as they were authored.
        for zone in zone_tags(master):
            for room in zone_rooms(zone):
                for obj in list(room.contents):
                    wanted = obj.db.get("reset_tags")
                    if not isinstance(wanted, dict):
                        continue
                    changed = False
                    for tag, present in wanted.items():
                        if bool(present) != obj.has_tag(tag):
                            (obj.add_tag if present else obj.remove_tag)(tag)
                            changed = True
                    if changed and persistence is not None:
                        await persistence.save(obj)

        # Clear this master's prior spawns, then reload canonical. No
        # survivor counting: the zone is empty, so churn is invisible, and
        # clearing is what purges the mobs of a since-removed spec entry.
        # What a spawn carries, wears and wields goes with it (its prototype's
        # ``contents`` come back with the reload); a player's own thing it
        # was given goes home to its owner (``release_contents``, as a
        # destroyed object's does). The floor and a corpse are not spawns.
        for obj in list(find_objects(tag=marker)):
            await release_contents(obj, persistence)
            obj.location = None
            if persistence is not None:
                await persistence.delete(obj)

        for entry in master.db.get("reset_spec") or []:
            room = _resolve_room(entry.get("room"), persistence)
            prototype = entry.get("prototype")
            if room is None or not prototype:
                continue
            for _ in range(int(entry.get("count", 1))):
                await spawn_tracked(prototype, room, marker, persistence,
                                    reset=master.id)


__all__ = ["ZoneResetBehavior"]
