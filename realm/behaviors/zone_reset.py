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
accumulation, and a removed spec entry's mobs vanish with the clear. Safe
because a reset only runs when the zone is **empty of players**: an occupied
zone defers (its timer keeps counting) and repops the instant it empties —
so the area never returns to canonical while someone's watching, by design.
``ON_RESET`` fires on the master for everything the spec doesn't cover
(re-lock doors, clear litter, reseed).
"""

from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.query import find_objects
from realm.core.zones import zone_rooms, zone_tags

if TYPE_CHECKING:
    from realm.core.objects import GameObject


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


@BehaviorRegistry.register
class ZoneResetBehavior(Behavior):
    """Repop a zone's canonical contents on a timer, while nobody's inside."""

    behavior_id = "zone_reset"

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, master: GameObject, delta: float) -> None:
        interval = master.db.get("reset_interval")
        if not interval:
            return
        now = _time.time()
        if now - float(master.db.get("last_reset") or 0) < float(interval):
            return
        # Presence gate — never repop on top of players; defer (leave
        # last_reset old) so it fires the moment the zone empties.
        for zone in zone_tags(master):
            for room in zone_rooms(zone):
                if any(c.has_tag("player") for c in room.contents):
                    return
        await self._reset(master)
        master.db.set("last_reset", now)

    async def _reset(self, master: GameObject) -> None:
        from realm.behaviors.spawner import spawn_tracked
        from realm.core.events import fire_event
        from realm.persistence.manager import get_active_manager

        persistence = get_active_manager()
        marker = f"reset:{master.id}"

        # Custom repop first — doors re-locked, litter cleared, randomness
        # reseeded — before the canonical mob wipe/reload.
        await fire_event(None, master, "event:on_reset")

        # Clear this master's prior spawns, then reload canonical. No
        # survivor counting: the zone is empty, so churn is invisible, and
        # clearing is what purges the mobs of a since-removed spec entry.
        for obj in list(find_objects(tag=marker)):
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
