"""
Area (zone) reset — presence-gated scheduled repopulation of a zone's
canonical contents (SMAUG ``area_update``/``reset_area``; tbaMUD zone reset).

REALM already has per-*room* spawners (`SpawnerBehavior`), but no
*area-level* reset: the whole zone returning to its authored state on a
timer, and only **while nobody is watching**. That's what this adds, keyed
on the **zone master** (the object crowned with `@zone/master`):

- ``db.reset_interval`` (seconds) — how often the zone tries to reset.
- ``db.reset_spec`` — a declarative repop list, each entry
  ``{"prototype": {...}, "room": <id-or-tag>, "count": N}`` (the same
  prototype vocabulary the spawner uses). Idempotent: each reset tops each
  entry back up to ``count``, so killing a mob and leaving means it's back
  next reset — but it will *not* pop on top of a player still in the zone.
- ``event:on_reset`` fires on the master, so softcode can do the rest
  (re-close/-lock doors, clear litter, reseed randomness).

The presence gate is the whole point: an occupied zone defers (its timer
keeps counting), and repops the instant it empties. Configure with plain
``@set`` on the master; the reset runs on the world tick.
"""

from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING

from realm.core.events import fire_event
from realm.core.query import find_objects
from realm.core.zones import MASTER_TAG, zone_rooms, zone_tags

if TYPE_CHECKING:
    from realm.core.objects import GameObject

RESET_INTERVAL_ATTR = "reset_interval"
LAST_RESET_ATTR = "last_reset"
RESET_SPEC_ATTR = "reset_spec"


def _zone_has_player(zones: list[str]) -> bool:
    for zone in zones:
        for room in zone_rooms(zone):
            if any(c.has_tag("player") for c in room.contents):
                return True
    return False


def _resolve_room(ref, persistence) -> GameObject | None:
    """A reset-spec ``room`` is an object id (``#id`` or bare) or a room
    tag (first matching room)."""
    if not ref:
        return None
    ref = str(ref).lstrip("#")
    if persistence is not None:
        obj = persistence.get_cached(ref)
        if obj is not None:
            return obj
    rooms = find_objects(tag="room", tags=[ref])
    return rooms[0] if rooms else None


async def reset_zones(persistence, *, now: float | None = None) -> int:
    """Reset every zone whose master is due and whose rooms hold no player.
    Runs on the world tick. Returns the number of zones reset."""
    now = _time.time() if now is None else now
    reset = 0
    for master in list(find_objects(tag=MASTER_TAG)):
        interval = master.db.get(RESET_INTERVAL_ATTR)
        if not interval:
            continue
        if now - float(master.db.get(LAST_RESET_ATTR) or 0) < float(interval):
            continue
        # Presence gate — never repop on top of players; defer (leave
        # last_reset old) so it fires the moment the zone empties.
        if _zone_has_player(zone_tags(master)):
            continue
        await fire_event(None, master, "event:on_reset")
        await _apply_reset_spec(master, persistence)
        master.db.set(LAST_RESET_ATTR, now)
        reset += 1
    return reset


async def _apply_reset_spec(master: GameObject, persistence) -> None:
    from realm.behaviors.spawner import spawn_from_prototype

    for i, entry in enumerate(master.db.get(RESET_SPEC_ATTR) or []):
        room = _resolve_room(entry.get("room"), persistence)
        prototype = entry.get("prototype")
        if room is None or not prototype:
            continue
        count = int(entry.get("count", 1))
        # Liveness by tag — find_objects returns only cached (living)
        # objects, so a killed reset-spawn drops out and is topped back up.
        tag = f"reset:{master.id}:{i}"
        alive = find_objects(tag=tag)
        for _ in range(max(0, count - len(alive))):
            spawn = spawn_from_prototype(prototype, room)
            spawn.add_tag(tag)
            if persistence is not None:
                await persistence.save(spawn)
            await fire_event(None, spawn, "event:on_load",
                             extra={"reset": master.id})


__all__ = ["reset_zones"]
