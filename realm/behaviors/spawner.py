"""
SpawnerBehavior: rooms that repopulate themselves.

Attach to a room with an NPC prototype (plain data — name, tags, db
attributes, behaviors); the spawner keeps ``count`` of them alive,
respawning ``respawn_ticks`` after one dies. Death is detected through
the identity map: killed NPCs are deleted from the persistence cache,
so a dead spawn's ID simply stops resolving — no scanning, no
double-bookkeeping.

    lobby.add_behavior(SpawnerBehavior(
        key="door_guard",
        prototype={
            "name": "Nexagen door guard",
            "tags": ["npc", "zone:nexagen"],
            "attrs": {"hp": 12, "max_hp": 12, "skill_melee": 12, "points": 50},
            "behaviors": [{"behavior_id": "watchful",
                           "params": {"challenge": "Building's closed."}}],
        },
        respawn_ticks=150,
        announce="A relief guard steps out of the security office.",
    ))

Spawned NPCs are tagged ``spawned:<key>`` and their IDs tracked in the
room's ``db.spawner_<key>_ids`` — all state persists, so respawn timers
survive reboots.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


def spawn_from_prototype(prototype: dict[str, Any],
                         location: GameObject) -> GameObject:
    """Instantiate a prototype dict as a live GameObject."""
    from realm.core.objects import GameObject as GameObjectCls

    obj = GameObjectCls(
        name=str(prototype.get('name', 'creature')),
        description=str(prototype.get('description', '')),
        tags=list(prototype.get('tags', ['npc'])),
    )
    for key, value in (prototype.get('attrs') or {}).items():
        obj.db.set(key, value)
    for spec in prototype.get('behaviors') or []:
        behavior = BehaviorRegistry.from_dict({
            'behavior_id': spec.get('behavior_id'),
            'params': spec.get('params', {}),
        })
        if behavior is not None:
            obj.add_behavior(behavior)
        else:
            logger.warning(
                f"Spawner prototype references unknown behavior "
                f"{spec.get('behavior_id')!r}"
            )
    obj.location = location
    return obj


@BehaviorRegistry.register
class SpawnerBehavior(Behavior):
    """
    Keep N copies of a prototype alive in this room.

    Params:
        key (str): identifies this spawner's population (required-ish;
            defaults to the prototype name slug).
        prototype (dict): see module docstring.
        count (int): how many to maintain (default 1).
        respawn_ticks (int): ticks between a death and the replacement
            (default 150 ≈ 10 min at 4s). First spawn is immediate.
        announce (str): room message when a spawn appears.
    """

    behavior_id = "spawner"

    @property
    def should_tick(self) -> bool:
        return True

    def _key(self) -> str:
        key = self.get_param('key')
        if key:
            return str(key)
        name = str((self.get_param('prototype') or {}).get('name', 'spawn'))
        return name.lower().replace(' ', '_')

    async def tick(self, room: GameObject, delta: float) -> None:
        from realm.persistence.manager import get_active_manager

        prototype = self.get_param('prototype')
        if not prototype:
            return
        persistence = get_active_manager()
        key = self._key()
        ids_attr = f"spawner_{key}_ids"
        timer_attr = f"spawner_{key}_timer"

        # Liveness: an ID that no longer resolves in the identity map is
        # a dead (deleted) spawn. Without persistence (bare tests), fall
        # back to counting tagged occupants of the room.
        tracked: list[str] = list(room.db.get(ids_attr) or [])
        if persistence is not None:
            alive = [obj_id for obj_id in tracked
                     if persistence.get_cached(obj_id) is not None]
        else:
            alive = [obj.id for obj in room.contents
                     if obj.has_tag(f"spawned:{key}")]
        if len(alive) != len(tracked):
            room.db.set(ids_attr, alive)

        wanted = int(self.get_param('count', 1))
        if len(alive) >= wanted:
            return

        # A vacancy: run the respawn countdown. First-ever spawn (no
        # timer, never tracked anyone) fills immediately.
        timer = room.db.get(timer_attr)
        if timer is None:
            timer = 0 if not room.db.get(f"spawner_{key}_seeded") \
                else int(self.get_param('respawn_ticks', 150))
        else:
            timer = int(timer)

        if timer > 0:
            room.db.set(timer_attr, timer - 1)
            return

        # Spawn one.
        spawn = spawn_from_prototype(prototype, room)
        spawn.add_tag(f"spawned:{key}")
        alive.append(spawn.id)
        room.db.set(ids_attr, alive)
        room.db.set(f"spawner_{key}_seeded", True)
        room.db.delete(timer_attr)

        if persistence is not None:
            await persistence.save(spawn)

        announce = self.get_param('announce')
        if announce:
            room.msg_contents(str(announce))
        logger.info(f"Spawner '{key}' spawned {spawn.name} in {room.name}")


__all__ = ["SpawnerBehavior", "spawn_from_prototype"]
