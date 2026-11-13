"""
Softcode functions: Tags and zones.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='Tags & zones', readonly=True)
def has_tag(frame, obj: GameObject | str | None, tag: str) -> bool:
    """Check if an object has a tag.

    Example: has_tag(enactor, 'player')
    """
    target = frame.resolve(obj)
    return target.has_tag(tag) if target else False

@softfn(group='Tags & zones', readonly=True)
def tags(frame, obj: GameObject | str | None) -> list[str]:
    """Get all tags on an object.

    Example: 'npc' in tags(enactor)
    """
    target = frame.resolve(obj)
    return target.tags.to_list() if target else []

@softfn(group='Tags & zones')
def add_tag(frame, obj: GameObject | str | None, tag: str) -> bool:
    """Add a tag to an object the executor controls.

    Example: add_tag(me, 'glowing')

    Role tags (god/admin/wizard/builder/staff) are refused unless the
    executor's own role outranks the privilege — control of an object
    never implies control of its *rank*, or a self-owned script could
    grant itself admin.
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(ops.tag, target, str(tag)) is not None


@softfn(group='Tags & zones')
def remove_tag(frame, obj: GameObject | str | None, tag: str) -> bool:
    """Remove a tag from an object the executor controls.

    Example: remove_tag(me, 'hostile')

    Role tags follow the same rank rule as :meth:`add_tag` — you cannot
    strip a privilege you do not outrank.
    """
    from realm.core import ops
    target = frame.resolve(obj)
    return target is not None and frame.apply(ops.untag, target, str(tag)) is not None


@softfn(group='Tags & zones', readonly=True)
def tag_values(frame, obj, prefix: str) -> list:
    """All values of a namespaced tag: tag_values(here, 'zone')
    -> ['castle', 'haunted'].

    Example: tag_values(here, 'zone')  # -> ['castle', 'haunted']
    """
    target = frame.resolve(obj)
    if target is None:
        return []
    p = str(prefix).rstrip(':') + ':'
    return [t[len(p):] for t in target.tags.to_list() if t.startswith(p)]

@softfn(group='Tags & zones', readonly=True)
def tag_value(frame, obj, prefix: str):
    """First value of a namespaced tag: tag_value(here, 'zone')
    -> 'castle' (None if untagged).

    Example: tag_value(here, 'zone')   # -> 'castle'
    """
    values = frame.tag_values(obj, prefix)
    return values[0] if values else None

@softfn(group='Tags & zones', readonly=True)
def zone_rooms(frame, zone: str):
    """Rooms tagged into a zone: zone_rooms('castle').

    Example: zone_rooms('castle')
    """
    from realm.core.zones import zone_rooms as _zone_rooms
    return _zone_rooms(str(zone))

@softfn(group='Tags & zones', readonly=True)
def zones_of(frame, obj):
    """The zone names an object belongs to (no 'zone:' prefix).

    Example: zones_of(here)
    """
    from realm.core.zones import zone_tags
    target = frame.resolve(obj)
    return [t.split(':', 1)[1] for t in zone_tags(target)]
