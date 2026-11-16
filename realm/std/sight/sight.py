"""
Darkness, light and invisibility, through the kernel's public sight seams
(``feature.sight_rule``, ``feature.marker``); the kernel's ``can_see``
knows none of these tags.

- ``dark`` on a room: pitch black unless lit or the viewer has
  ``nightvision``. A room is lit by any ``light``-tagged object in it, or
  one wielded by someone present (a held torch lights the room for
  everyone; a lantern in your pack does not).
- ``invisible`` on an object: unseen unless the viewer has
  ``see_invisible``. Invisible things vanish from room displays and can't
  be targeted; invisible actors still act, read as "Someone".
- Markers on listed names: ``glowing`` for anyone, ``magic`` for a
  ``detect_magic`` viewer, ``invisible`` for a ``see_invisible`` one
  (admins, who see everything, see both).

A room is never hidden by its own darkness: messages and listings that
name a dark room still name it. Whether a viewer can see *inside* it is
``can_see_room``, which the ``look`` feature asks through this feature's
service (``world.services["sight"]``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from realm.core.perception import sees_all

if TYPE_CHECKING:
    from realm.core.objects import GameObject

DARK_TAG = "dark"
LIGHT_TAG = "light"
NIGHTVISION_TAG = "nightvision"
INVISIBLE_TAG = "invisible"
SEE_INVISIBLE_TAG = "see_invisible"


#: More reasons a room may be dark, from other features (the ``clock``
#: feature: an outdoor room at night): ``(room) -> bool``. Add one with
#: :func:`add_darkness_test`; a light source lights any dark room.
_darkness_tests: list[Callable[[GameObject], bool]] = []


def add_darkness_test(test: Callable[[GameObject], bool]) -> Callable[[], None]:
    """Make ``test(room)`` another reason a room is dark. Returns the undo
    (a world's closer)."""
    _darkness_tests.append(test)

    def remove() -> None:
        if test in _darkness_tests:
            _darkness_tests.remove(test)
    return remove


def is_dark(room: GameObject) -> bool:
    """Dark before any light source: tagged ``dark``, or a darkness test says so."""
    return room.has_tag(DARK_TAG) or any(test(room) for test in _darkness_tests)


def room_is_lit(room: GameObject | None) -> bool:
    """Not dark (tagged ``dark``, or by another feature's darkness test), or
    holding a ``light`` source: in the room, or wielded by someone present."""
    if room is None or not is_dark(room):
        return True
    for obj in room.contents:
        if obj.has_tag(LIGHT_TAG):
            return True
        for carried in obj.contents:
            if carried.has_tag(LIGHT_TAG) and carried.has_tag('wielded'):
                return True
    return False


def can_see_room(viewer: GameObject | None, room: GameObject | None) -> bool:
    """Whether the viewer can see inside the room at all (vs pitch black)."""
    if viewer is None or room is None or room_is_lit(room):
        return True
    return viewer.has_tag(NIGHTVISION_TAG) or sees_all(viewer)


def invisibility(viewer: GameObject, obj: GameObject) -> bool | None:
    """Sight rule: an invisible thing (not a room) needs ``see_invisible``."""
    if obj.has_tag(INVISIBLE_TAG) and not obj.is_room \
            and not viewer.has_tag(SEE_INVISIBLE_TAG):
        return False
    return None


def darkness(viewer: GameObject, obj: GameObject) -> bool | None:
    """Sight rule: a thing in an unlit room is unseen without nightvision."""
    location = obj.location
    if location is not None and not can_see_room(viewer, location):
        return False
    return None


def glowing_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    return "glowing" if obj.has_tag("glowing") else None


def magic_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    if obj.has_tag("magic") and looker is not None and (
            looker.has_tag("detect_magic") or sees_all(looker)):
        return "magic"
    return None


def invisible_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    if obj.has_tag(INVISIBLE_TAG) and looker is not None and (
            looker.has_tag(SEE_INVISIBLE_TAG) or sees_all(looker)):
        return "invisible"
    return None


__all__ = [
    "DARK_TAG", "LIGHT_TAG", "NIGHTVISION_TAG", "INVISIBLE_TAG", "SEE_INVISIBLE_TAG",
    "room_is_lit", "can_see_room", "invisibility", "darkness",
    "glowing_marker", "magic_marker", "invisible_marker",
]
