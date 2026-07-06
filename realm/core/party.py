"""
Following and parties: one attribute, room-local semantics.

``db.following = <leader id>`` is the whole state — softcode-readable,
softcode-settable (an NPC agreeing to be escorted is
``set_attr(me, 'following', '%#')`` in a $-command). When a leader
walks through an exit, followers in the room walk after them
(movement.py hooks ``bring_followers``); chains cascade naturally and
are loop-safe because each scan is room-local and movers have already
left the room being scanned.

A *party* is the connected component of follow edges among objects in
one room — no party object, no invitations. CP awards split across the
killer's party members present at the kill.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

FOLLOWING_ATTR = "following"


def leader_id(obj: GameObject) -> str | None:
    value = obj.db.get(FOLLOWING_ATTR)
    return str(value) if value else None


def set_following(follower: GameObject, leader: GameObject | None) -> None:
    if leader is None:
        follower.db.delete(FOLLOWING_ATTR)
    else:
        follower.db.set(FOLLOWING_ATTR, leader.id)


def followers_of(leader: GameObject, room: GameObject | None) -> list[GameObject]:
    """Who, in this room, is following the leader?"""
    if room is None:
        return []
    return [obj for obj in room.contents
            if obj is not leader and leader_id(obj) == leader.id]


def party_members(obj: GameObject) -> list[GameObject]:
    """
    Everyone in ``obj``'s room connected to it through follow edges
    (either direction), including ``obj``. Solo = [obj].
    """
    room = obj.location
    if room is None:
        return [obj]

    present = {o.id: o for o in room.contents}
    present[obj.id] = obj

    # Adjacency: follower <-> leader, restricted to this room.
    edges: dict[str, set[str]] = {oid: set() for oid in present}
    for oid, o in present.items():
        lid = leader_id(o)
        if lid and lid in present:
            edges[oid].add(lid)
            edges[lid].add(oid)

    seen = {obj.id}
    queue = [obj.id]
    while queue:
        current = queue.pop()
        for neighbor in edges.get(current, ()):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return [present[oid] for oid in seen]


async def bring_followers(
    leader: GameObject,
    origin: GameObject | None,
    destination: GameObject,
    exit_obj: GameObject | None = None,
) -> None:
    """
    Walk the leader's followers through the exit after them. Blocked,
    unconscious, or mid-combat followers stay behind (the same rules
    they'd face walking themselves — locks and guards apply).
    """
    from realm.core.movement import move_through_exit
    from realm.core.render import render_room

    for obj in followers_of(leader, origin):
        if obj.has_tag('unconscious') or obj.has_tag('in_combat'):
            continue
        moved = await move_through_exit(obj, destination, exit_obj=exit_obj)
        if moved:
            obj.msg(f"You follow {leader.name}.")
            if obj.has_tag('player'):
                obj.msg(render_room(destination, obj))


__all__ = [
    "FOLLOWING_ATTR",
    "leader_id",
    "set_following",
    "followers_of",
    "party_members",
    "bring_followers",
]
