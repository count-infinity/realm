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
HIDDEN_TAG = "hidden"

# Actions loud enough to break stealth. Movement is deliberately absent —
# sneaking room to room is the point of hiding; Watchful observers contest it.
LOUD_ACTIONS = {
    "event:speech", "event:shout", "event:ooc",
    "event:emote", "event:semipose", "event:emit",
    "item:on_get", "item:on_open", "item:on_close",
    "combat:on_attack",
}


def _is_admin(viewer: GameObject) -> bool:
    from realm.permissions.roles import Role, get_role
    return get_role(viewer) >= Role.ADMIN


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
    # Hidden (active stealth) isn't countered by see_invisible — only by
    # winning a contest (the `search` command, Watchful observers) or by
    # the hider acting loudly.
    if obj.has_tag(HIDDEN_TAG):
        return False
    location = obj.location
    if location is not None and not can_see_room(viewer, location):
        return False
    return True


def display_markers(obj: GameObject, looker: GameObject | None) -> str:
    """
    CoffeeMud-style parenthetical dispositions appended to a name —
    ``a torch (glowing)``, ``a rusty key (hidden)`` — each shown only to
    a looker who can perceive it:

        glowing   anyone (a ``glowing`` tag; ambient light cue)
        magic     lookers tagged ``detect_magic`` (or admins)
        hidden    only admins/those who can see a still-hidden thing —
                  so a builder sees WHY an item is special
        invisible likewise, for a see_invisible looker
    """
    marks = []
    if obj.has_tag('glowing'):
        marks.append('glowing')
    if obj.has_tag('magic') and looker is not None and (
            looker.has_tag('detect_magic') or _is_admin(looker)):
        marks.append('magic')
    if obj.has_tag(HIDDEN_TAG) and looker is not None and _is_admin(looker):
        marks.append('hidden')
    if obj.has_tag('invisible') and looker is not None and (
            looker.has_tag('see_invisible') or _is_admin(looker)):
        marks.append('invisible')
    return f" ({', '.join(marks)})" if marks else ""


def perceived_name(obj: GameObject, looker: GameObject | None = None) -> str:
    """
    The name the looker knows this object by — used in MESSAGES, so it
    stays clean (no markers): the real name when visible, else "Someone"/
    "something". Perception markers are a LOOK concern — see
    ``display_markers``, applied by the room renderer.
    """
    if looker is None or can_see(looker, obj):
        return obj.name
    if obj.has_tag('player') or obj.has_tag('npc'):
        return "Someone"
    return "something"


def break_stealth(obj: GameObject, reason: str = "") -> bool:
    """
    Drop an object's ``hidden`` tag and announce it. Returns True if the
    object was actually hidden.
    """
    if not obj.has_tag(HIDDEN_TAG):
        return False
    obj.remove_tag(HIDDEN_TAG)
    obj.msg(reason or "You are no longer hidden.")
    room = obj.location
    if room is not None:
        room.msg_contents(
            f"{obj.name} emerges from hiding.", exclude=[obj],
        )
    return True


async def stealth_observer(action) -> None:
    """
    Propagation observer: acting loudly breaks the actor's stealth.

    Registered by GameServer alongside the script engine. Runs after
    delivery, so bystanders hear the unattributed action ("Someone
    says...") and THEN see the hider revealed — you gave yourself away.
    """
    actor = action.actor
    if actor is None or action.blocked:
        return
    if action.action_type in LOUD_ACTIONS and actor.has_tag(HIDDEN_TAG):
        break_stealth(actor, "Your action gives you away!")


__all__ = [
    "DARK_TAG",
    "LIGHT_TAG",
    "NIGHTVISION_TAG",
    "INVISIBLE_TAG",
    "SEE_INVISIBLE_TAG",
    "HIDDEN_TAG",
    "display_markers",
    "LOUD_ACTIONS",
    "room_is_lit",
    "can_see_room",
    "can_see",
    "perceived_name",
    "break_stealth",
    "stealth_observer",
]
