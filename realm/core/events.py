"""
Lifecycle event hooks — fire ``ON_<EVENT>`` triggers from game code.

REALM's event stream is open: any propagated ``Action`` whose type ends in a
suffix ``X`` lets a witnessing object's ``ON_X`` softcode react (and its
``on_check`` ward veto, when the event is gated). This helper is the one
call site game code uses to fire such a lifecycle event, so every hook —
equip, door, spawn, expiry, low-HP, cast — looks the same.

Gated events (``gated=True``) run the check pass with ``deliver=False`` and
return the Action so the caller can honor a veto (``action.blocked``) — a
cursed ring refusing removal, a sealed door refusing to unlock. Informational
events just fire the triggers.
"""

from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING

from realm.core.propagation import Action, propagate

if TYPE_CHECKING:
    from realm.core.objects import GameObject


async def fire_event(
    actor: GameObject | None,
    target: GameObject | None,
    action_type: str,
    *,
    tags: set[str] | list[str] | None = None,
    extra: dict | None = None,
    gated: bool = False,
) -> Action:
    """Propagate a lifecycle event so witnesses' ``ON_<EVENT>`` triggers (and,
    when gated, their ``on_check`` wards) fire. Returns the Action — check
    ``.blocked`` for a gated event."""
    action = Action(
        actor=actor,
        target=target,
        action_type=action_type,
        tags=set(tags or ()),
        extra=extra or {},
    )
    await propagate(action, deliver=not gated)
    return action


async def reap_expired(persistence, *, now: float | None = None) -> int:
    """The object self-expiry primitive (tbaMUD's ``OTRIG_TIMER``). Any object
    with a ``db.expires_at`` timestamp that has passed fires ``event:on_expire``
    and is then destroyed — a summoned wolf, a smoke cloud, a temporary portal.
    Unlike a softcode ``wait()`` (which dies with its script), the countdown
    lives on the object and survives across ticks. Runs on the world tick.
    Returns the number reaped.

    ``expires_at`` is the single source of truth for "should die". An
    ``ON_EXPIRE`` handler survives ONLY by clearing or pushing out
    ``expires_at`` (``expire(me, 999)``) — relocating the object or applying
    an effect is not enough; if the timestamp still reads past-due after the
    hook, the object is destroyed at wherever it now sits. (A witness that
    vetoes the informational ``on_expire`` action suppresses the ``ON_EXPIRE``
    reaction but does NOT stay the destruction — death is decided by the
    field, not the hook.)
    """
    from realm.core.query import find_objects
    from realm.core.teardown import release_contents

    now = _time.time() if now is None else now
    reaped = 0
    for obj in list(find_objects(attr='expires_at')):
        at = obj.db.get('expires_at')
        if at is None or float(at) > now:
            continue
        # actor=None: this is the object reacting to ITSELF — as the target
        # it witnesses its own ON_EXPIRE (the actor is excluded from
        # witnessing, so it must not be the actor here).
        await fire_event(None, obj, "event:on_expire")
        # Re-check: the handler may have renewed the lease, or already moved
        # / destroyed the object.
        at = obj.db.get('expires_at')
        if at is None or float(at) > now:
            continue
        await release_contents(obj, persistence)   # R9 disposition of contents
        obj.location = None
        if persistence is not None:
            await persistence.delete(obj)
        reaped += 1
    return reaped


__all__ = ["fire_event", "reap_expired"]
