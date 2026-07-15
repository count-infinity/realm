"""
Ephemeral instanced areas — a private, transient copy of a template area,
materialized on demand, reaped when idle. See docs/design/ephemeral-rooms.md.

The hard part (deep-copy an area with fresh ids and remap references) is
``worldio.import_objects``; this module is the thin orchestration around it:
clone a template, tag the copy ``ephemeral`` (so it never persists) plus an
instance identity, drop the owner in, bump activity, and GC when idle.

Keyed per player. ``mode='shared'`` lets the owner's followers route into
the owner's copy instead of their own; ``mode='solo'`` gives everyone a
private copy.

Note: the ``instance_template`` opt-in is enforced at the softcode surface
(``enter_instance``), not here — Python callers of ``enter()`` are trusted
kernel/game code and may clone any zone.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from realm.core.movement import register_dest_resolver
from realm.core.query import find_objects
from realm.core.teardown import (
    EPHEMERAL_TAG,
    evacuation_room,
    release_contents,
    subtree_has_player,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject

TEMPLATE_TAG = "instance_template"    # opt-in mark on a source area
MASTER_TAG = "instance_master"        # the per-copy lifecycle object
ENTRY_TAG = "instance_entry"          # the template room players arrive in
RESOLVER_NAME = "instance"            # portal exits: db.dest_resolver = this

DEFAULT_IDLE_TTL = 900.0              # seconds empty before a copy is reaped

logger = logging.getLogger(__name__)


def _clock() -> float:
    return time.time()


def _instance_tag(template: str, owner_id: str) -> str:
    return f"instance:{template}:{owner_id}"


def _masters(template: str | None = None) -> list[GameObject]:
    out = find_objects(tag=MASTER_TAG)
    if template is not None:
        out = [m for m in out if m.db.get("template") == template]
    return out


def _leader_ids(player: GameObject) -> list[str]:
    """The follow chain above ``player`` (nearest leader first),
    cycle-guarded. Routing walks the whole chain: when A follows B
    follows C, A is party to C's shared copy even though A's direct
    leader owns nothing."""
    from realm.persistence.manager import get_active_manager
    manager = get_active_manager()
    ids: list[str] = []
    seen = {player.id}
    current = player.db.get("following")
    while current and str(current) not in seen:
        current = str(current)
        ids.append(current)
        seen.add(current)
        leader = manager.get_cached(current) if manager else None
        current = leader.db.get("following") if leader is not None else None
    return ids


def instance_for(template: str, player: GameObject) -> GameObject | None:
    """The instance-master this player should enter for ``template``:
    their own copy, or — if anyone up their follow chain owns a
    ``shared`` copy — that owner's copy. None means one must be
    materialized."""
    for master in _masters(template):
        if master.db.get("owner") == player.id:
            return master
    for leader_id in _leader_ids(player):
        for master in _masters(template):
            if (master.db.get("owner") == leader_id
                    and master.db.get("mode") == "shared"):
                return master
    return None


async def materialize(
    template: str, owner: GameObject, persistence, *,
    mode: str = "solo", return_room: GameObject | None = None,
    idle_ttl: float = DEFAULT_IDLE_TTL,
) -> tuple[GameObject | None, GameObject]:
    """Clone ``template`` (a zone in the world) into a private, transient
    copy owned by ``owner``. Returns (entry_room, master)."""
    from realm.core.objects import GameObject as GameObjectCls
    from realm.persistence.worldio import export_zone, import_objects

    data = export_zone(template)
    inst_tag = _instance_tag(template, owner.id)
    # Full owner id — a truncated prefix could collide and merge two
    # players' instances into one zone (leaking zone alarms / $-commands
    # across copies, the very audience-sharing this design prevents).
    inst_zone = f"zone:{template}#{owner.id}"         # isolate zone queries
    # Born ephemeral: inject the tags into the data so the clones never hit
    # the DB (import_objects saves them, and the save path skips ephemeral).
    for entry in data.get("objects", []):
        tags = set(entry.get("tags") or [])
        tags.discard(f"zone:{template}")
        tags.update({EPHEMERAL_TAG, inst_tag, inst_zone})
        entry["tags"] = sorted(tags)

    created = await import_objects(data, persistence)
    entry = next((o for o in created if o.has_tag(ENTRY_TAG)), None)
    if entry is None:
        entry = next((o for o in created if o.has_tag("room")), None)

    master = GameObjectCls(
        name=f"instance:{template}:{owner.name}",
        tags=[EPHEMERAL_TAG, MASTER_TAG, inst_tag],
    )
    master.db.set("template", template)
    master.db.set("owner", owner.id)
    master.db.set("mode", mode)
    master.db.set("return_room", return_room.id if return_room else None)
    master.db.set("idle_ttl", float(idle_ttl))
    master.db.set("entry", entry.id if entry else None)
    master.db.set("last_active", _clock())
    await persistence.save(master)         # registered in cache, skipped from DB
    return entry, master


async def find_or_materialize(
    template: str, player: GameObject, persistence, *,
    mode: str = "solo", return_room: GameObject | None = None,
    idle_ttl: float = DEFAULT_IDLE_TTL,
) -> tuple[GameObject | None, GameObject]:
    """The router: this player's live copy (their own, or their shared
    leader's), rebuilt if its entry went stale, else a freshly
    materialized one. On reuse, ``mode``/``return_room``/``idle_ttl``
    are ignored — the master keeps its creation-time values. Bumps
    activity. Returns (entry_room, master)."""
    master = instance_for(template, player)
    if master is None:
        entry, master = await materialize(
            template, player, persistence, mode=mode,
            return_room=return_room, idle_ttl=idle_ttl)
    else:
        entry = persistence.get_cached(master.db.get("entry"))
        if entry is None:
            # Stale master — its entry room is gone (partial teardown).
            # Rebuild rather than silently keeping the corpse alive.
            await destroy_instance(master, persistence)
            entry, master = await materialize(
                template, player, persistence, mode=mode,
                return_room=return_room, idle_ttl=idle_ttl)
    master.db.set("last_active", _clock())
    return entry, master


async def enter(
    template: str, player: GameObject, persistence, *,
    mode: str = "solo", return_room: GameObject | None = None,
    idle_ttl: float = DEFAULT_IDLE_TTL,
) -> GameObject | None:
    """Find-or-materialize this player's instance of ``template`` and
    place them in its entry room — the scripted API (softcode
    ``enter_instance`` drains here; a placement, like ``move_to``).
    Portal *exits* use :func:`resolve_instance_exit` instead, so the
    walk is a real traversal. Returns the entry room."""
    entry, _master = await find_or_materialize(
        template, player, persistence, mode=mode,
        return_room=return_room, idle_ttl=idle_ttl)
    if entry is not None:
        player.location = entry
    return entry


async def resolve_instance_exit(
    exit_obj: GameObject, actor: GameObject,
) -> GameObject | None:
    """The registered deferred-destination resolver for **instance
    portals** — a real exit with ``db.dest_resolver = "instance"`` and:

    - ``instance_template`` — the template zone (required);
    - ``instance_mode`` — ``solo`` (default) | ``shared``;
    - ``instance_return`` — evacuation room id (default: the portal's
      own room, so a reaped straggler lands back where they entered);
    - ``instance_ttl`` — idle seconds before the copy reaps.

    Walking the portal IS the consent — the traversal is a normal
    ``move_through_exit``, so wards, locks, ``on_enter``, and the
    follower cascade run unchanged. Followers re-resolve individually
    (see ``bring_followers``), which makes this the portal-router of
    ephemeral-rooms.md: the owner gets their copy, a follower of a
    ``shared`` owner is routed into the owner's copy, a follower of a
    ``solo`` owner is bounced at the threshold, and a mob never
    materializes a copy of its own."""
    from realm.core.zones import zone_rooms
    from realm.permissions.locks import LockType, check_lock
    from realm.persistence.manager import get_active_manager

    persistence = get_active_manager()
    template = exit_obj.db.get("instance_template")
    if not template or persistence is None:
        logger.warning(
            f"instance portal {exit_obj.name} ({exit_obj.id}) has no "
            f"instance_template; treating as dead-end")
        return None
    template = str(template)

    rooms = zone_rooms(template)
    if not any(r.has_tag(TEMPLATE_TAG) for r in rooms):
        # A portal into a zone that never opted in is a builder bug, not
        # geography — fail loud, never clone an arbitrary area.
        logger.error(
            f"instance portal {exit_obj.name} ({exit_obj.id}) names zone "
            f"{template!r}, which has no {TEMPLATE_TAG!r} room")
        from realm.core.movement import DestinationUnavailableError
        raise DestinationUnavailableError("A strange force bars the way.")

    # Authored gate, checked pre-materialize against the walker (the
    # clone re-checks in the move pipeline; refusing here avoids
    # importing a whole copy just to bounce at its door).
    template_entry = (next((r for r in rooms if r.has_tag(ENTRY_TAG)), None)
                      or next((r for r in rooms if r.has_tag(TEMPLATE_TAG)),
                              None))
    if template_entry is not None and not check_lock(
            template_entry, LockType.ENTER, actor):
        return None

    pre_existing = instance_for(template, actor) is not None
    if not pre_existing:
        # No copy to route into. Solo bounce (the ephemeral-rooms.md
        # decision): a follower of a solo owner — anywhere up the follow
        # chain — is refused at the threshold, not silently handed a
        # private copy.
        chain = _leader_ids(actor)
        if chain and any(
                m.db.get("owner") in chain and m.db.get("mode") == "solo"
                for m in _masters(template)):
            return None
        # Copies are per-PLAYER: a mob may be routed into an existing
        # shared copy above, but never materializes its own.
        if not actor.has_tag("player"):
            return None

    return_room = None
    if exit_obj.db.get("instance_return"):
        return_room = persistence.get_cached(
            str(exit_obj.db.get("instance_return")))
    if return_room is None:
        return_room = exit_obj.location

    idle_ttl = DEFAULT_IDLE_TTL
    raw_ttl = exit_obj.db.get("instance_ttl")
    if raw_ttl is not None:
        try:
            idle_ttl = float(raw_ttl)
        except (TypeError, ValueError):
            logger.warning(
                f"instance portal {exit_obj.name} instance_ttl {raw_ttl!r} "
                f"is not a number; using the {DEFAULT_IDLE_TTL:.0f}s default")

    entry, master = await find_or_materialize(
        template, actor, persistence,
        mode=str(exit_obj.db.get("instance_mode") or "solo"),
        return_room=return_room, idle_ttl=idle_ttl)
    if entry is not None and not check_lock(entry, LockType.ENTER, actor):
        # An identity-sensitive lock (one reading the room's tags/ids,
        # not just the caller) can pass on the template yet deny on the
        # fresh clone. Don't leave the just-imported copy lingering
        # until the reaper — tear it down and present a clean dead-end.
        if not pre_existing:
            await destroy_instance(master, persistence)
        return None
    return entry


def _occupied(inst_tag: str) -> bool:
    # Subtree scan: a player inside a vehicle inside a copied room still
    # holds the copy open.
    for obj in find_objects(tag=inst_tag):
        if obj.has_tag("room") and subtree_has_player(obj):
            return True
    return False


async def destroy_instance(master: GameObject, persistence) -> None:
    """Evacuate any stragglers, then destroy the whole copy + its master."""
    template = master.db.get("template")
    owner_id = master.db.get("owner")
    inst_tag = _instance_tag(template, owner_id)
    return_room = (persistence.get_cached(master.db.get("return_room"))
                   if master.db.get("return_room") else None)

    objects = find_objects(tag=inst_tag)
    # R9 disposition for every room's occupants: players evacuated down
    # the return_room → home → start_room ladder, player-owned property
    # to its owner's refuge, everything else destroyed loudly. Objects
    # cloned with the copy (inst-tagged) are deleted below alongside it.
    doomed = {obj.id for obj in objects} | {master.id}
    for room in objects:
        if not room.has_tag("room"):
            continue
        await release_contents(room, persistence,
                               return_room=return_room, doomed_ids=doomed)

    # The master carries the instance tag too, so it's already in `objects`;
    # dedupe by id so we don't delete it twice.
    targets = {obj.id: obj for obj in objects}
    targets[master.id] = master
    for obj in targets.values():
        obj.location = None
        await persistence.delete(obj)   # removes from DB + unregisters from cache


async def reap_idle(persistence, *, now: float | None = None) -> int:
    """GC pass: reap every copy that's been empty past its idle_ttl. Returns
    the number reaped. Call from the world tick."""
    now = _clock() if now is None else now
    reaped = 0
    for master in list(_masters()):
        inst_tag = _instance_tag(master.db.get("template"), master.db.get("owner"))
        if _occupied(inst_tag):
            master.db.set("last_active", now)
            continue
        ttl = float(master.db.get("idle_ttl") or DEFAULT_IDLE_TTL)
        if now - float(master.db.get("last_active") or 0) > ttl:
            await destroy_instance(master, persistence)
            reaped += 1
    return reaped


# Private space: every walker may land in a different copy, so flee
# refuses these exits (see register_dest_resolver).
register_dest_resolver(RESOLVER_NAME, resolve_instance_exit,
                       shared_destination=False)


__all__ = [
    "EPHEMERAL_TAG", "TEMPLATE_TAG", "MASTER_TAG", "ENTRY_TAG",
    "RESOLVER_NAME", "DEFAULT_IDLE_TTL", "evacuation_room",
    "instance_for", "find_or_materialize", "materialize", "enter",
    "resolve_instance_exit", "destroy_instance", "reap_idle",
]
