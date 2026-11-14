"""
Hiding: the ``hidden`` tag and what it does.

A ``hidden`` character or thing is out of sight (a sight rule) until it is
found (``search``, a Watchful observer) or, for a character, acts loudly.
``see_invisible`` does not counter it; only a contest does. Admins see it
anyway, marked ``(hidden)`` so a builder sees why an item is special.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.perception import sees_all
from realm.std.combat.actions import CombatAction
from realm.std.items.actions import ItemAction
from realm.std.talk.actions import TalkAction

if TYPE_CHECKING:
    from realm.core.objects import GameObject

HIDDEN_TAG = "hidden"

# Actions loud enough to break stealth. Movement is deliberately absent —
# sneaking room to room is the point of hiding; Watchful observers contest it.
LOUD_ACTIONS = {
    TalkAction.SPEECH, TalkAction.SHOUT, TalkAction.OOC,
    TalkAction.EMOTE, TalkAction.SEMIPOSE, TalkAction.EMIT,
    ItemAction.ON_GET, ItemAction.ON_OPEN, ItemAction.ON_CLOSE,
    CombatAction.ON_ATTACK,
}


def hidden_from_sight(viewer: GameObject, obj: GameObject) -> bool | None:
    """The sight rule: a hidden thing is out of sight (False); otherwise
    no opinion. The kernel has already let a SEE_ALL viewer through."""
    return False if obj.has_tag(HIDDEN_TAG) else None


def hidden_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    """``(hidden)`` on a listing, for a looker who sees everything."""
    if obj.has_tag(HIDDEN_TAG) and looker is not None and sees_all(looker):
        return "hidden"
    return None


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

    Runs after delivery, so bystanders hear the unattributed action
    ("Someone says...") and THEN see the hider revealed — you gave
    yourself away.
    """
    actor = action.actor
    if actor is None or action.blocked:
        return
    if action.action_type in LOUD_ACTIONS and actor.has_tag(HIDDEN_TAG):
        break_stealth(actor, "Your action gives you away!")


__all__ = ["HIDDEN_TAG", "LOUD_ACTIONS", "hidden_from_sight", "hidden_marker",
           "break_stealth", "stealth_observer"]
