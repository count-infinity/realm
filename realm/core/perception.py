"""
Perception: who can see whom, and what unseen things are called.

Tag-driven (no rigid types, per REALM's object model):

- ``dark`` on a room — pitch black unless lit or the viewer has
  ``nightvision``. A room is lit by any ``light``-tagged object in it,
  including one carried by someone present (a held torch lights the
  room for everyone).
- ``invisible`` on an object — hidden from sight unless the viewer has
  ``see_invisible``. Invisible things vanish from room displays and
  can't be targeted; invisible *actors* still act, but bystanders who
  can't see them read "Someone" in messages.
- Admins and above see everything.
- A feature adds rules of its own (``feature.sight_rule``): the ``stealth``
  feature hides a ``hidden`` character, and ``feature.marker`` adds its
  ``(hidden)`` marker to listings.

The single naming entry point is :func:`perceived_name` (exposed as
``GameObject.get_display_name(looker)``) — message formatting, room
rendering, and targeting all route through the same rules, so a
character can never be named in a message but hidden from ``look``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

DARK_TAG = "dark"
LIGHT_TAG = "light"
NIGHTVISION_TAG = "nightvision"
INVISIBLE_TAG = "invisible"
SEE_INVISIBLE_TAG = "see_invisible"


def sees_all(viewer: GameObject) -> bool:
    """Whether ``viewer`` sees through darkness and invisibility — the SEE_ALL
    entitlement (every built-in ADMIN+ has it; a custom role may too)."""
    from realm.permissions.entitlements import SEE_ALL
    from realm.permissions.roles import has_entitlement
    return has_entitlement(viewer, SEE_ALL)


def room_is_lit(room: GameObject | None) -> bool:
    """
    Whether a room has light: not tagged ``dark``, or containing a
    ``light`` source — sitting in the room, or WIELDED by someone present
    (you must hold a torch up; a lantern buried in your pack doesn't
    light the way).
    """
    if room is None or not room.has_tag(DARK_TAG):
        return True
    for obj in room.contents:
        if obj.has_tag(LIGHT_TAG):
            return True
        for carried in obj.contents:
            if carried.has_tag(LIGHT_TAG) and carried.has_tag('wielded'):
                return True
    return False


def can_see_room(viewer: GameObject | None, room: GameObject | None) -> bool:
    """Whether the viewer can see the room at all (vs pitch blackness)."""
    if viewer is None or room is None:
        return True
    if room_is_lit(room):
        return True
    return viewer.has_tag(NIGHTVISION_TAG) or sees_all(viewer)


def can_see(viewer: GameObject | None, obj: GameObject) -> bool:
    """
    Whether the viewer perceives the object.

    You always see yourself; admins see everything; invisibility beats
    normal sight; darkness hides everything in an unlit room from
    viewers without nightvision. Then the world's sight rules
    (``feature.sight_rule``): any False hides.
    """
    if viewer is None or viewer is obj:
        return True
    if sees_all(viewer):
        return True
    if obj.has_tag(INVISIBLE_TAG) and not viewer.has_tag(SEE_INVISIBLE_TAG):
        return False
    location = obj.location
    if location is not None and not can_see_room(viewer, location):
        return False
    from realm.core.world import find_world
    world = find_world()
    if world is not None:
        for rule in world.sight_rules:
            if rule(viewer, obj) is False:
                return False
    return True


def display_markers(obj: GameObject, looker: GameObject | None) -> str:
    """
    CoffeeMud-style parenthetical dispositions appended to a name —
    ``a torch (glowing)``, ``a rusty key (hidden)`` — each shown only to
    a looker who can perceive it:

        glowing   anyone (a ``glowing`` tag; ambient light cue)
        magic     lookers tagged ``detect_magic`` (or admins)
        invisible a see_invisible looker (or admins)

    then the world's markers (``feature.marker``: ``stealth`` shows
    ``hidden`` to an admin, so a builder sees WHY an item is special).
    """
    marks = []
    if obj.has_tag('glowing'):
        marks.append('glowing')
    if obj.has_tag('magic') and looker is not None and (
            looker.has_tag('detect_magic') or sees_all(looker)):
        marks.append('magic')
    if obj.has_tag('invisible') and looker is not None and (
            looker.has_tag('see_invisible') or sees_all(looker)):
        marks.append('invisible')
    from realm.core.world import find_world
    world = find_world()
    for fn in (world.markers if world is not None else ()):
        mark = fn(obj, looker)
        if mark:
            marks.append(mark)
    return f" ({', '.join(marks)})" if marks else ""


import logging

logger = logging.getLogger(__name__)

def perceived_name(obj: GameObject, looker: GameObject | None = None) -> str:
    """
    The name the looker knows this object by — used in MESSAGES, so it
    stays clean (no markers): the real (or resolved) name when visible,
    else "Someone"/"something". Perception markers are a LOOK concern —
    see ``display_markers``, applied by the room renderer.

    When visible, the name passes through the world's name resolvers
    (recognition, disguise — ``feature.name_resolver``). With none, this
    is ``obj.name``.
    """
    if looker is None or can_see(looker, obj):
        name = obj.name
        from realm.core.world import find_world
        world = find_world()
        for fn in (world.name_resolvers if world is not None else ()):
            try:
                name = fn(obj, looker, name)
            except Exception as exc:   # noqa: BLE001 - never blank a name
                logger.error("name resolver %r failed: %s",
                             getattr(fn, "__name__", fn), exc)
        return name
    if obj.is_player or obj.is_npc:
        return "Someone"
    return "something"


__all__ = [
    "DARK_TAG",
    "LIGHT_TAG",
    "NIGHTVISION_TAG",
    "INVISIBLE_TAG",
    "SEE_INVISIBLE_TAG",
    "display_markers",
    "sees_all",
    "room_is_lit",
    "can_see_room",
    "can_see",
    "perceived_name",
]
