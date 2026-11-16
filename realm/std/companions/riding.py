"""
Mounts (MUD_PLAN 13.3), after SMAUG's ``mount``/``dismount`` and
CoffeeMud's riding.

A companion tagged ``mount`` can be ridden by its master. Riding is one
attribute each way: ``riding`` on the rider and ``ridden_by`` on the
mount, which is also tagged ``ridden`` so the room listing leaves it out
(its rider is shown "(riding a grey mare)"). The mount follows as any
companion does; where the game charges movement it pays from its own
``move`` pool (``payer``). Rooms tagged ``no_mount``, and indoor rooms
unless ``MOUNTS_INDOORS``, refuse a rider.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.language import singular_name
from realm.core.movement import move_through_exit, resolve_exit_destination
from realm.core.world import get_world
from realm.std.companions.companions import the

if TYPE_CHECKING:
    from realm.core.objects import GameObject

MOUNT_TAG = "mount"
RIDDEN_TAG = "ridden"
NO_MOUNT_TAG = "no_mount"
RIDING_ATTR = "riding"
RIDDEN_BY_ATTR = "ridden_by"


def _cached(obj_id) -> GameObject | None:
    store = get_world().store
    if not obj_id or store is None:
        return None
    return store.get_cached(str(obj_id))


def mount_of(rider: GameObject) -> GameObject | None:
    """What ``rider`` is riding, or None (both ends must agree)."""
    mount = _cached(rider.db.get(RIDING_ATTR))
    if mount is None or mount.db.get(RIDDEN_BY_ATTR) != rider.id:
        return None
    return mount


def rider_of(mount: GameObject) -> GameObject | None:
    """Who is riding ``mount``, or None."""
    rider = _cached(mount.db.get(RIDDEN_BY_ATTR))
    if rider is None or rider.db.get(RIDING_ATTR) != mount.id:
        return None
    return rider


def payer(actor: GameObject) -> GameObject:
    """Who pays for ``actor``'s step: its mount while it rides."""
    return mount_of(actor) or actor


def clear_riding(obj: GameObject) -> None:
    """Undo any riding ``obj`` is part of, at either end (no messages)."""
    mount = _cached(obj.db.get(RIDING_ATTR))
    if mount is not None and mount.db.get(RIDDEN_BY_ATTR) == obj.id:
        mount.db.delete(RIDDEN_BY_ATTR)
        mount.remove_tag(RIDDEN_TAG)
    rider = _cached(obj.db.get(RIDDEN_BY_ATTR))
    if rider is not None and rider.db.get(RIDING_ATTR) == obj.id:
        rider.db.delete(RIDING_ATTR)
    obj.db.delete(RIDING_ATTR)
    obj.db.delete(RIDDEN_BY_ATTR)
    obj.remove_tag(RIDDEN_TAG)


def mount_refusal(rider: GameObject, mount: GameObject) -> str | None:
    """Why ``rider`` cannot climb onto ``mount`` now, or None."""
    from realm.std.companions.companions import master_of
    if mount_of(rider) is not None:
        return "You're already mounted!"
    if not mount.has_tag(MOUNT_TAG) or mount.is_player:
        return f"You can't ride {the(mount, capital=False)}."
    if master_of(mount) is not rider:
        return f"{the(mount)} isn't yours to ride."
    if rider_of(mount) is not None:
        return f"{the(mount)} already has a rider."
    if rider.has_tag("in_combat") or mount.has_tag("in_combat"):
        return "Not in the middle of a fight!"
    if rider.has_tag("resting") or rider.has_tag("sleeping"):
        return "You need to stand up first."
    if any(mount.has_tag(t) for t in ("unconscious", "sleeping", "resting")):
        return f"{the(mount)} must be standing."
    if riding_refused(rider.location):
        return "You can't ride in here."
    return None


def mount(rider: GameObject, mount: GameObject) -> None:
    """Seat ``rider`` on ``mount`` (the caller checked ``mount_refusal``)."""
    rider.db.set(RIDING_ATTR, mount.id)
    mount.db.set(RIDDEN_BY_ATTR, rider.id)
    mount.add_tag(RIDDEN_TAG)


#: how -> (the rider's line, the room's line), ``{mount}`` the mount.
_DISMOUNT_LINES = {
    "dismount": ("You dismount {mount}.", "{rider} dismounts {mount}."),
    "sleep": ("You slide down from {mount}.", "{rider} slides down from {mount}."),
    "fall": ("You fall from {mount}!", "{rider} falls from {mount}!"),
    "behind": ("You leave {mount} behind.", None),
    "parted": ("You are parted from {mount}.", None),
    "quiet": (None, None),
}


async def dismount(rider: GameObject, *, how: str = "dismount") -> bool:
    """Take ``rider`` off its mount (``how`` picks the lines: ``dismount``,
    ``sleep``, ``fall``, ``behind``, ``parted``, ``quiet``). False when it
    was not riding."""
    mount = mount_of(rider)
    if mount is None:
        clear_riding(rider)
        return False
    clear_riding(rider)
    own, room_line = _DISMOUNT_LINES[how]
    name = the(mount, capital=False)
    if own:
        rider.msg(own.format(mount=name))
    if room_line and rider.location is not None:
        rider.location.msg_contents(room_line.format(rider=rider.name, mount=name),
                                    exclude=[rider])
    store = get_world().store
    if store is not None:
        await store.save(rider)
        await store.save(mount)
    return True


def riding_refused(room: GameObject | None) -> bool:
    """Is ``room`` closed to riders: tagged ``no_mount``, or indoors
    (``sector:inside``) while ``MOUNTS_INDOORS`` is False."""
    if room is None:
        return False
    if room.has_tag(NO_MOUNT_TAG):
        return True
    return room.has_tag("sector:inside") and not get_world().setting("MOUNTS_INDOORS")


# --- the feature's hooks ------------------------------------------------------------


async def riding_gate(actor: GameObject, exit_obj: GameObject | None,
                      direction: str, *, fleeing: bool) -> str | None:
    """``feature.traversal_gate``: a rider goes only where riding is
    allowed and its mount can carry it; a ridden mount does not walk off
    from under its rider."""
    rider = rider_of(actor)
    if rider is not None and rider.location is actor.location:
        return "You can't walk off with a rider on your back."
    mount = mount_of(actor)
    if mount is None:
        return None
    if mount.location is not actor.location:
        clear_riding(actor)
        return None
    destination = resolve_exit_destination(exit_obj) if exit_obj is not None else None
    if riding_refused(destination):
        return "You can't ride in there."
    if fleeing:
        return None
    if mount.has_tag("unconscious"):
        return "Your mount is hurt far too badly to move."
    if mount.has_tag("sleeping"):
        return "Your mount is sleeping."
    if mount.has_tag("resting"):
        return "Your mount is resting."
    return None


async def after_ride(actor: GameObject, origin: GameObject | None,
                     destination: GameObject, exit_obj: GameObject | None,
                     *, fleeing: bool) -> None:
    """``feature.after_traverse``: the mount has followed (``social``
    walks followers first); a fleeing rider's mount bolts with it
    (CoffeeMud), and a rider who arrives without its mount is off it."""
    mount = mount_of(actor)
    if mount is None:
        return
    if fleeing and mount.location is origin and origin is not None:
        combat = get_world().services.get("combat")
        if combat is not None:
            combat.withdraw(mount)
        mount.remove_tag("in_combat")
        await move_through_exit(mount, destination, exit_obj=exit_obj, fleeing=True)
    if mount.location is not actor.location:
        await dismount(actor, how="behind")


def describe_move(actor: GameObject, direction: str | None, phase: str) -> str | None:
    """``feature.move_describer``: a rider rides; a ridden mount's own
    steps (it follows its rider) print nothing."""
    if rider_of(actor) is not None:
        return ""
    mount = mount_of(actor)
    if mount is None:
        return None
    on = singular_name(mount)
    if phase == "own":
        return f"You ride {direction} on {on}."
    if phase == "leave":
        return f"{{actor}} rides {direction} on {on}."
    return f"{{actor}} arrives, riding {on}."


def riding_marker(obj: GameObject, looker: GameObject | None) -> str | None:
    """``feature.marker``: "(riding a grey mare)" on a rider."""
    if not obj.db.get(RIDING_ATTR):
        return None
    mount = mount_of(obj)
    return f"riding {singular_name(mount)}" if mount is not None else None


__all__ = [
    "MOUNT_TAG",
    "NO_MOUNT_TAG",
    "RIDDEN_BY_ATTR",
    "RIDDEN_TAG",
    "RIDING_ATTR",
    "after_ride",
    "clear_riding",
    "describe_move",
    "dismount",
    "mount",
    "mount_of",
    "mount_refusal",
    "payer",
    "rider_of",
    "riding_gate",
    "riding_marker",
    "riding_refused",
]
