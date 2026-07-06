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

from typing import TYPE_CHECKING

from realm.core.propagation import (
    ROOM_TARGET_CHAIN,
    Action,
    deliver_messages,
    propagate,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager


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


async def move_through_exit(
    actor: GameObject,
    destination: GameObject,
    *,
    exit_obj: GameObject | None = None,
    direction: str | None = None,
    fleeing: bool = False,
) -> bool:
    """
    Move ``actor`` to ``destination``, firing on_leave then on_enter.

    on_leave runs first with ``deliver=False`` and gates the move: if a behavior
    blocks it, the actor stays put, receives the block reason, and this returns
    ``False`` (the leave messages are never delivered). Otherwise the actor
    relocates and on_enter fires — its block flag is advisory and ignored, since
    the actor has already arrived.

    Returns ``True`` if the actor moved, ``False`` if blocked at on_leave.

    Destination resolution and room display are the caller's responsibility; this
    helper owns only the relocation and its two events.
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
    from realm.permissions.locks import LockType, check_lock, lock_failure_message

    if exit_obj is not None and not check_lock(exit_obj, LockType.BASIC, actor):
        actor.msg(lock_failure_message(
            exit_obj, LockType.BASIC, "You can't go {name} — it's locked.",
        ))
        return False

    # Physical door state: a 'closed' exit must be opened first.
    if exit_obj is not None and exit_obj.has_tag('closed'):
        actor.msg(
            exit_obj.db.get('closed_msg') or f"The {exit_obj.name} is closed."
        )
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
            return False

    if not check_lock(destination, LockType.ENTER, actor):
        actor.msg(lock_failure_message(
            destination, LockType.ENTER, "You can't enter {name}.",
        ))
        return False

    # Phase 1: on_leave gates the move.
    if origin is not None:
        leave = Action(
            actor=actor,
            target=origin,
            action_type="event:on_leave",
            chain=ROOM_TARGET_CHAIN,
            extra={"exit": exit_obj, "destination": destination, "direction": direction},
            tags={"movement"},
        )
        leave.add_message("actor", f"You leave {direction}.")
        leave.add_message("room", f"{{actor}} leaves {direction}.")
        await propagate(leave, deliver=False)
        if leave.blocked:
            actor.msg(leave.block_reason or "You can't go that way.")
            return False
        deliver_messages(leave)

    # Phase 2: relocate.
    actor.location = destination

    # Phase 3: on_enter is informational — the actor has already arrived.
    enter = Action(
        actor=actor,
        target=destination,
        action_type="event:on_enter",
        chain=ROOM_TARGET_CHAIN,
        extra={"from": origin, "exit": exit_obj, "direction": direction},
        tags={"movement"},
    )
    enter.add_message("room", "{actor} arrives.")
    await propagate(enter)

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


__all__ = ["move_through_exit", "resolve_exit_destination"]
