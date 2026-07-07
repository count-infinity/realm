"""
Zones: areas as a tag convention plus one master object.

A room belongs to a zone by carrying a ``zone:<name>`` tag; the zone's
brain is any object tagged ``zone_master`` that shares the tag:

    @create Castle Zone
    @tag Castle Zone = zone_master
    @tag Castle Zone = zone:castle
    @tag here = zone:castle          (each member room)

The engine consults masters in three places: the softcode trigger
search (zone-wide $-commands/^listens — the PennMUSH Zone Master Room),
event triggers (the master's ON_ENTER/ON_DEATH fire for events in any
member room), and numeric policy via :func:`zone_property`
(``@set Castle Zone/xp_multiplier = 1.2``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

ZONE_PREFIX = "zone:"
MASTER_TAG = "zone_master"


def zone_tags(obj: GameObject | None) -> list[str]:
    """The ``zone:*`` tags on an object (usually a room)."""
    if obj is None:
        return []
    return [t for t in obj.tags.to_list() if t.startswith(ZONE_PREFIX)]


def zone_masters(room: GameObject | None) -> list[GameObject]:
    """Masters of every zone this room belongs to."""
    wanted = set(zone_tags(room))
    if not wanted:
        return []
    from realm.core.query import find_objects
    return [m for m in find_objects(tag=MASTER_TAG)
            if wanted & set(zone_tags(m))]


def zone_property(room: GameObject | None, name: str, default: Any = None) -> Any:
    """
    A policy attribute read from the room's zone masters.

    Numeric values from overlapping zones combine with max (the most
    generous multiplier wins); otherwise the first found is returned.
    """
    values = [m.db.get(name) for m in zone_masters(room)
              if m.db.get(name) is not None]
    if not values:
        return default
    if all(isinstance(v, (int, float)) for v in values):
        return max(values)
    return values[0]


def zone_rooms(zone: str) -> list[GameObject]:
    """Every room tagged into the zone."""
    from realm.core.query import find_objects
    zone = zone if zone.startswith(ZONE_PREFIX) else ZONE_PREFIX + zone
    return find_objects(tag='room', tags=[zone])


__all__ = ["ZONE_PREFIX", "MASTER_TAG", "zone_tags", "zone_masters",
           "zone_property", "zone_rooms"]
