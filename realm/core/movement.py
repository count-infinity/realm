"""
Movement expressed as propagated events.

A move is two actions: ``event:on_leave`` (gates the move — a behavior may block
it) followed by ``event:on_enter`` (informational, fired after the actor has
relocated). Both travel on ``ROOM_TARGET_CHAIN`` because the target of a movement
action is the room itself.

Centralising this means every movement path — the ``go`` command, exit-name
dispatch, and any future teleport/follow — fires the same events through the same
gate, so a behavior like ``GuardBehavior`` cannot be silently bypassed by one path
having forgotten to emit them.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.action_tags import FAILURE, MOVEMENT
from realm.core.propagation import (
    ROOM_TARGET_CHAIN,
    Action,
    deliver_messages,
    propagate,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager

logger = logging.getLogger(__name__)


class DestinationUnavailableError(Exception):
    """A deferred-destination resolver failed abnormally (a broken
    map-provider, not a map edge). The message is shown to the walker —
    distinct from the authored dead-end line, so a builder's bug never
    masquerades as world geography."""


# Deferred exit destinations (ephemeral-rooms.md kernel bit #3): an exit
# may name a resolver (``db.dest_resolver``) instead of storing a
# ``destination``. ``move_through_exit`` consults the registry only after
# the origin-side gates pass, materializes the room beyond (a wilderness
# cell), and the traversal proceeds like any door — wards, locks,
# ``on_enter``, and the follower cascade unchanged.
_DEST_RESOLVERS: dict[str, Callable[[GameObject, GameObject],
                                    Awaitable[GameObject | None]]] = {}


def register_dest_resolver(name: str, resolver) -> None:
    """Register an async ``(exit_obj, actor) -> room | None`` resolver
    under ``name``. An exit opts in with ``db.dest_resolver = name``."""
    _DEST_RESOLVERS[str(name)] = resolver


def has_dest_resolver(exit_obj: GameObject | None) -> bool:
    """Does this exit defer its destination to a registered resolver?"""
    return exit_obj is not None and bool(exit_obj.db.get('dest_resolver'))


async def _resolve_deferred_destination(
    exit_obj: GameObject | None, actor: GameObject,
) -> GameObject | None:
    if exit_obj is None:
        return None
    name = exit_obj.db.get('dest_resolver')
    if not name:
        return None
    resolver = _DEST_RESOLVERS.get(str(name))
    if resolver is None:
        # A typo'd resolver name is a builder bug, not world geography —
        # fail loud, never masquerade as a map edge (vision #10).
        logger.error(
            f"Exit {exit_obj.name} ({exit_obj.id}) names unregistered "
            f"dest_resolver {name!r}")
        raise DestinationUnavailableError("A strange force bars the way.")
    return await resolver(exit_obj, actor)


def resolve_exit_destination(
    exit_obj: GameObject,
    persistence: PersistenceManager | None = None,
) -> GameObject | None:
    """
    Resolve an exit's destination room.

    Prefers an in-memory ``destination_obj`` reference (handy for tests and
    code-built worlds); falls back to resolving the persistence-safe string
    ``destination`` ID through the object cache. Only the string form
    survives a save/load cycle, so world-building code should store IDs.
    Every movement path uses this one resolver so an exit can't work from
    one entry point and fail from another.
    """
    dest_obj = exit_obj.db.get('destination_obj')
    if dest_obj is not None:
        return dest_obj

    dest_id = exit_obj.db.get('destination')
    if dest_id:
        if persistence is None:
            from realm.persistence.manager import get_active_manager
            persistence = get_active_manager()
        if persistence is not None:
            return persistence.get_cached(dest_id)

    return None


async def fire_exit_fail(
    actor: GameObject,
    exit_obj: GameObject | None,
    reason: str,
    *,
    direction: str | None = None,
    destination: GameObject | None = None,
) -> bool:
    """
    Fire ``event:on_fail`` so ``ON_FAIL`` / ``@afail`` softcode can react to
    a thwarted move — a locked, closed, or dead-end (no-destination) exit.

    Post-hoc, like PennMUSH's ``@afail``: the move already failed and its
    message has (or is about to be) shown; witnesses — the exit itself and
    the room — run their ``ON_FAIL``. The one twist is the **dead-end** case:
    an exit whose ``ON_FAIL`` *materializes* the room beyond it (a wilderness
    cell, an instanced dungeon) and moves the actor in. So this returns
    ``True`` when a handler relocated the actor, letting the caller suppress
    the default "leads nowhere" line and show the new room instead.
    """
    if actor is None:
        return False
    origin = actor.location
    fail = Action(
        actor=actor,
        target=exit_obj if exit_obj is not None else destination,
        action_type="event:on_fail",
        chain=ROOM_TARGET_CHAIN,
        extra={"exit": exit_obj, "reason": reason,
               "direction": direction, "destination": destination},
        tags={MOVEMENT, FAILURE},
    )
    await propagate(fail)
    return actor.location is not origin and actor.location is not None


async def move_to(
    actor: GameObject,
    destination: GameObject,
    *,
    extra_tags: set[str] | list[str] | None = None,
    force: bool = False,
    mover: GameObject | None = None,
) -> bool:
    """
    Relocate ``actor`` to ``destination`` with the movement checks baked in —
    the one relocation primitive, ``move_and_slide`` style. The caller just
    names a destination; the engine runs the "physics":

      1. a ``movement``-tagged **leave ward** — the mover/origin room may veto
         (a Bound ward: ``block() if has_atag('movement')``);
      2. the destination's **ENTER** and **TELEPORT locks** (this is a direct
         placement, so a "no teleporting in here" lock applies);
      3. a ``movement``-tagged **pre-enter ward** on the destination — its
         event-veto (a magic-shielded sanctum), which a static lock can't
         express (mirrors Evennia's ``at_pre_object_receive`` / CoffeeMUD's
         destination ``okMessage``);
      4. relocate + an informational ``on_enter``.

    ``force`` skips only the on_check **wards** (steps 1 and 3) — the wizard/
    admin path. It does **not** bypass **locks** (step 2 still runs; only the
    GOD role bypasses a lock, in ``check_lock``) nor **authority** (that's the
    caller's gate). So ``teleport_obj`` == ``move_to(force=True)``: it
    tunnels past a Bound ward but still honors a destination's teleport lock.
    A forced arrival still fires ``on_enter`` — skip the gates, keep the
    notification.

    ``mover`` names whoever is PERFORMING a third-party relocation (the
    @teleport-ing builder, the scripting object). If the mover *controls*
    the destination, its locks don't apply — Penn's ``controls(player,
    dest)`` arm — since a controller could simply re-lock the room anyway.

    The engine always tags the move ``movement`` so a ward can't be dodged by
    an action forgetting to flag itself; callers add domain tags (``magic``
    for a teleport spell). A direct placement carries no ``exit`` in its
    ``adata`` — that absence is how a ward tells a teleport from a walk
    (``has_atag('movement') and not adata('exit')``). Returns ``True`` if the
    actor moved, ``False`` if a ward or lock fizzled it (reason delivered).
    """
    if actor is None or destination is None or actor is destination:
        return False

    from realm.permissions.locks import LockType

    tags = {MOVEMENT, *(str(t) for t in (extra_tags or ()))}
    origin = actor.location

    # 1. Leave ward — skipped by force (the wizard bypass).
    if not force and origin is not None:
        leave = Action(
            actor=actor, target=origin, action_type="event:on_leave",
            chain=ROOM_TARGET_CHAIN, tags=set(tags),
            extra={"destination": destination},
        )
        await propagate(leave, deliver=False)
        if leave.blocked:
            actor.msg(leave.block_reason or "You can't leave.")
            return False

    # 2. Destination LOCKS (Penn's tport_dest_ok). Skipped only when the
    #    ``mover`` — whoever is performing a third-party relocation (an
    #    @teleport-ing builder, a scripting object) — has real authority over
    #    arrivals here: they're ADMIN+, or they genuinely control an OWNED
    #    destination (they could re-lock it anyway). The ``owner is not None``
    #    guard is the same world-trusts-world catch as may_relocate — without
    #    it, any unowned object would "control" any unowned room and tunnel
    #    its lock. Otherwise the locks are evaluated against the object being
    #    moved (Penn evaluates the tport lock against the victim). force skips
    #    wards, never locks.
    if not _mover_owns_destination(mover, destination):
        if _lock_denies(actor, destination, LockType.ENTER,
                        "You can't enter {name}."):
            return False
        if _lock_denies(actor, destination, LockType.TELEPORT,
                        "You can't teleport into {name}."):
            return False

    # 3. Pre-enter ward — the destination's event-veto; skipped by force.
    if not force and await _pre_enter_blocked(
            actor, destination, tags, extra={"from": origin}):
        return False

    # 4. Relocate, then the informational arrival.
    actor.location = destination
    await _fire_arrival(actor, destination, tags, extra={"from": origin})
    return True


def _mover_owns_destination(mover: GameObject | None,
                            destination: GameObject) -> bool:
    """Does ``mover`` have authority over who arrives at ``destination`` —
    so its ENTER/TELEPORT locks yield? True for an ADMIN+ mover, or a mover
    that genuinely controls an OWNED destination (Penn's ``controls(player,
    dest)`` arm of tport_dest_ok). The ``owner is not None`` guard keeps
    world-trusts-world from letting any unowned object tunnel a room's lock.
    """
    if mover is None:
        return False
    from realm.permissions.locks import controls
    from realm.permissions.roles import Role, get_role
    if get_role(mover) >= Role.ADMIN:
        return True
    return destination.owner is not None and controls(mover, destination)


def _lock_denies(actor: GameObject, obj: GameObject, lock_type,
                 default_msg: str) -> bool:
    """Check a lock; on denial, deliver the failure message and return True."""
    from realm.permissions.locks import check_lock, lock_failure_message
    if check_lock(obj, lock_type, actor):
        return False
    actor.msg(lock_failure_message(obj, lock_type, default_msg))
    return True


async def _pre_enter_blocked(actor: GameObject, destination: GameObject,
                             tags: set[str], extra: dict) -> bool:
    """The destination's event-veto: fire ``event:pre_enter`` (check pass
    only) and report whether a ward blocked the arrival. Both walking and
    direct placement run this, so a sanctum's ward guards every way in."""
    pre = Action(
        actor=actor, target=destination, action_type="event:pre_enter",
        chain=ROOM_TARGET_CHAIN, tags=set(tags), extra=extra,
    )
    await propagate(pre, deliver=False)
    if pre.blocked:
        actor.msg(pre.block_reason or "You can't go there.")
        return True
    return False


async def _fire_arrival(actor: GameObject, destination: GameObject,
                        tags: set[str], extra: dict) -> None:
    """The informational ``on_enter`` — the actor has already arrived."""
    enter = Action(
        actor=actor, target=destination, action_type="event:on_enter",
        chain=ROOM_TARGET_CHAIN, tags=set(tags), extra=extra,
    )
    enter.add_message("room", "{actor} arrives.")
    await propagate(enter)


async def move_through_exit(
    actor: GameObject,
    destination: GameObject | None,
    *,
    exit_obj: GameObject | None = None,
    direction: str | None = None,
    fleeing: bool = False,
) -> bool:
    """
    Move ``actor`` to ``destination``, firing on_leave then on_enter.

    on_leave runs first with ``deliver=False`` and gates the move: if a behavior
    blocks it, the actor stays put, receives the block reason, and this returns
    ``False`` (the leave messages are never delivered). The destination then
    gets its own event-veto (``event:pre_enter``, same as ``move_to`` — a
    sanctum's ward guards walk-ins and teleports alike). Only then does the
    actor relocate; on_enter is informational, the actor has already arrived.

    Returns ``True`` if the actor moved, ``False`` if blocked.

    Deliberate asymmetries with ``move_to`` (traversal vs direct placement):
    the in_combat/unconscious gates and follower cascade apply only here —
    walking is embodied travel; a teleport is the spell's problem — and the
    TELEPORT lock applies only to ``move_to`` (walking in isn't teleporting).

    ``destination`` may be ``None`` when the exit carries a registered
    ``dest_resolver`` — the room beyond is materialized on demand, *after*
    the origin-side gates pass (so a refused walker creates nothing).

    Static destination resolution and room display are the caller's
    responsibility; this helper owns the relocation and its events.
    """
    if direction is None and exit_obj is not None:
        direction = exit_obj.name
    direction = direction or "away"

    origin = actor.location

    # Mid-combat, leaving the room requires a flee attempt (which sets
    # ``fleeing=True``); everything else stays free.
    if actor.has_tag('in_combat') and not fleeing:
        actor.msg("You're in the middle of combat — flee to escape!")
        return False
    if actor.has_tag('unconscious'):
        actor.msg("You are unconscious.")
        return False

    # Phase 0: locks gate the move before any events fire. The exit's
    # 'basic' lock controls traversal; the destination's 'enter' lock
    # controls entry. These are checked here (not in the propagation pass)
    # because neither object is the target of the gating on_leave action.
    from realm.permissions.locks import LockType

    if exit_obj is not None and _lock_denies(
            actor, exit_obj, LockType.BASIC, "You can't go {name} — it's locked."):
        await fire_exit_fail(actor, exit_obj, 'locked', direction=direction)
        return False

    # Physical door state: a 'closed' exit must be opened first.
    if exit_obj is not None and exit_obj.has_tag('closed'):
        actor.msg(
            exit_obj.db.get('closed_msg') or f"The {exit_obj.name} is closed."
        )
        await fire_exit_fail(actor, exit_obj, 'closed', direction=direction)
        return False

    # Skill-gated exits (fire escapes, ledges): db.check_skill names the
    # skill, db.check_difficulty subtracts, db.check_fail_msg customizes.
    check_skill = exit_obj.db.get('check_skill') if exit_obj is not None else None
    if check_skill:
        from realm.core.checks import check
        difficulty = int(exit_obj.db.get('check_difficulty') or 0)
        result = check(actor, str(check_skill), -difficulty)
        if not result.success:
            actor.msg(
                exit_obj.db.get('check_fail_msg')
                or f"You fail to make it {direction} ({check_skill} check)."
            )
            if origin is not None:
                origin.msg_contents(
                    f"{actor.get_display_name(None)} tries to go {direction} and fails.",
                    exclude=[actor],
                )
            await fire_exit_fail(actor, exit_obj, 'skill', direction=direction)
            return False

    # Deferred destination (kernel bit #3): the room beyond this exit may
    # not exist yet — materialize it now, only after every origin-side
    # gate above has passed. From here on the traversal is
    # indistinguishable from walking any door.
    if destination is None:
        error_msg: str | None = None
        try:
            destination = await _resolve_deferred_destination(exit_obj, actor)
        except DestinationUnavailableError as exc:
            error_msg = str(exc) or "A strange force bars the way."
        if destination is None:
            # The dead-end contract (same as the legacy branch in the
            # entry points): fire on_fail FIRST — an authored @afail may
            # relocate the actor, in which case the fail line is
            # suppressed and the caller renders the new room.
            reason = 'resolver_error' if error_msg else 'no_destination'
            if await fire_exit_fail(actor, exit_obj, reason,
                                    direction=direction):
                return True
            fail = error_msg or (
                exit_obj.db.get('fail_msg') if exit_obj is not None else None)
            actor.msg(fail or "You can't go that way.")
            return False

    if _lock_denies(actor, destination, LockType.ENTER,
                    "You can't enter {name}."):
        await fire_exit_fail(actor, exit_obj, 'locked_destination',
                             direction=direction, destination=destination)
        return False

    # Phase 1: on_leave gates the move.
    if origin is not None:
        leave = Action(
            actor=actor,
            target=origin,
            action_type="event:on_leave",
            chain=ROOM_TARGET_CHAIN,
            extra={"exit": exit_obj, "destination": destination, "direction": direction},
            tags={MOVEMENT},
        )
        leave.add_message("actor", f"You leave {direction}.")
        leave.add_message("room", f"{{actor}} leaves {direction}.")
        await propagate(leave, deliver=False)
        if leave.blocked:
            actor.msg(leave.block_reason or "You can't go that way.")
            await fire_exit_fail(actor, exit_obj, 'blocked', direction=direction)
            return False

    # Phase 1.5: the destination's event-veto — the same pre_enter ward
    # move_to runs, so a warded sanctum stops walk-ins too, not just
    # teleports. Carries the exit in adata: a ward can still distinguish
    # a walk (adata('exit')) from a teleport (no exit).
    if await _pre_enter_blocked(
            actor, destination, {MOVEMENT},
            extra={"from": origin, "exit": exit_obj, "direction": direction}):
        await fire_exit_fail(actor, exit_obj, 'blocked_destination',
                             direction=direction, destination=destination)
        return False

    # Leave messages deliver only once BOTH ends have allowed the move —
    # a destination veto shouldn't announce a departure that never happened.
    if origin is not None:
        deliver_messages(leave)

    # Phase 2: relocate.
    actor.location = destination

    # Phase 3: on_enter is informational — the actor has already arrived.
    await _fire_arrival(
        actor, destination, {MOVEMENT},
        extra={"from": origin, "exit": exit_obj, "direction": direction})

    # Structured client data (GMCP Room.Info) — no-op without a client
    # that negotiated OOB.
    actor.msg_oob("Room.Info", {
        "id": destination.id,
        "name": destination.name,
        "exits": [o.name for o in destination.contents if o.has_tag('exit')],
    })

    # Followers walk after their leader (room-local scan of the origin,
    # so chains cascade and cycles self-resolve — the mover already left
    # the room being scanned). Fleeing breaks the chain: you escape
    # alone.
    if not fleeing:
        from realm.core.party import bring_followers
        await bring_followers(actor, origin, destination, exit_obj)

    return True


__all__ = ["move_through_exit", "resolve_exit_destination", "fire_exit_fail",
           "move_to", "register_dest_resolver", "has_dest_resolver",
           "DestinationUnavailableError"]
