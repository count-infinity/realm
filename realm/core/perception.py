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


def _is_admin(viewer: GameObject) -> bool:
    from realm.permissions.roles import Role, get_role
    return get_role(viewer) >= Role.ADMIN


def room_is_lit(room: GameObject | None) -> bool:
    """
    Whether a room has light: not tagged ``dark``, or containing a
    ``light`` source — directly or carried by someone present.
    """
    if room is None or not room.has_tag(DARK_TAG):
        return True
    for obj in room.contents:
        if obj.has_tag(LIGHT_TAG):
            return True
        for carried in obj.contents:
            if carried.has_tag(LIGHT_TAG):
                return True
    return False


def can_see_room(viewer: GameObject | None, room: GameObject | None) -> bool:
    """Whether the viewer can see the room at all (vs pitch blackness)."""
    if viewer is None or room is None:
        return True
    if room_is_lit(room):
        return True
    return viewer.has_tag(NIGHTVISION_TAG) or _is_admin(viewer)


def can_see(viewer: GameObject | None, obj: GameObject) -> bool:
    """
    Whether the viewer perceives the object.

    You always see yourself; admins see everything; invisibility beats
    normal sight; darkness hides everything in an unlit room from
    viewers without nightvision.
    """
    if viewer is None or viewer is obj:
        return True
    if _is_admin(viewer):
        return True
    if obj.has_tag(INVISIBLE_TAG) and not viewer.has_tag(SEE_INVISIBLE_TAG):
        return False
    location = obj.location
    if location is not None and not can_see_room(viewer, location):
        return False
    return True


def perceived_name(obj: GameObject, looker: GameObject | None = None) -> str:
    """
    The name the looker knows this object by.

    The real name when visible; "Someone" for unseen people and NPCs,
    "something" for unseen things.
    """
    if looker is None or can_see(looker, obj):
        return obj.name
    if obj.has_tag('player') or obj.has_tag('npc'):
        return "Someone"
    return "something"


__all__ = [
    "DARK_TAG",
    "LIGHT_TAG",
    "NIGHTVISION_TAG",
    "INVISIBLE_TAG",
    "SEE_INVISIBLE_TAG",
    "room_is_lit",
    "can_see_room",
    "can_see",
    "perceived_name",
]
