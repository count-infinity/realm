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
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from realm.core.query import find_objects

if TYPE_CHECKING:
    from realm.core.objects import GameObject

EPHEMERAL_TAG = "ephemeral"          # transient — never persisted (see manager)
TEMPLATE_TAG = "instance_template"    # opt-in mark on a source area
MASTER_TAG = "instance_master"        # the per-copy lifecycle object
ENTRY_TAG = "instance_entry"          # the template room players arrive in

DEFAULT_IDLE_TTL = 900.0              # seconds empty before a copy is reaped


def _clock() -> float:
    return time.time()


def _instance_tag(template: str, owner_id: str) -> str:
    return f"instance:{template}:{owner_id}"


def evacuation_room(persistence, occupant: GameObject,
                    return_room: GameObject | None = None) -> GameObject | None:
    """Where to send a player displaced by a room's destruction: the
    instance's ``return_room``, else their ``home``, else the world's start
    room. The start-room floor means an evacuee is never stranded at
    ``None`` while a world exists (see vision invariant #10 — fail loud, not
    into the void)."""
    home = (persistence.get_cached(occupant.db.get("home"))
            if persistence else None)
    floor = next(iter(find_objects(tag="start_room")), None)
    return return_room or home or floor


def _masters(template: str | None = None) -> list[GameObject]:
    out = find_objects(tag=MASTER_TAG)
    if template is not None:
        out = [m for m in out if m.db.get("template") == template]
    return out


def instance_for(template: str, player: GameObject) -> GameObject | None:
    """The instance-master this player should enter for ``template``: their
    own copy, or — if following someone whose copy is ``shared`` — that
    owner's copy. None means one must be materialized."""
    for master in _masters(template):
        if master.db.get("owner") == player.id:
            return master
    leader_id = player.db.get("following")
    if leader_id:
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


async def enter(
    template: str, player: GameObject, persistence, *,
    mode: str = "solo", return_room: GameObject | None = None,
    idle_ttl: float = DEFAULT_IDLE_TTL,
) -> GameObject | None:
    """Find-or-materialize this player's instance of ``template`` and move
    them into its entry room. Returns the entry room."""
    master = instance_for(template, player)
    if master is None:
        entry, master = await materialize(
            template, player, persistence, mode=mode,
            return_room=return_room, idle_ttl=idle_ttl)
    else:
        entry = persistence.get_cached(master.db.get("entry"))
    if entry is not None:
        player.location = entry
    master.db.set("last_active", _clock())
    return entry


def _occupied(inst_tag: str) -> bool:
    for obj in find_objects(tag=inst_tag):
        if obj.has_tag("room") and any(
                c.has_tag("player") for c in obj.contents):
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
    # Evacuate players along the return_room → home → start_room ladder.
    for room in objects:
        if not room.has_tag("room"):
            continue
        for occupant in list(room.contents):
            if occupant.has_tag("player"):
                occupant.location = evacuation_room(
                    persistence, occupant, return_room)

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


__all__ = [
    "EPHEMERAL_TAG", "TEMPLATE_TAG", "MASTER_TAG", "ENTRY_TAG",
    "DEFAULT_IDLE_TTL",
    "instance_for", "materialize", "enter", "destroy_instance", "reap_idle",
]
