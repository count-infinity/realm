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


async def spawn_tracked(prototype: dict[str, Any], room: GameObject,
                        marker: str, persistence, **load_extra: Any) -> GameObject:
    """Spawn a prototype into ``room``, tag it ``marker``, persist, and fire
    ``ON_LOAD``. The one shared spawn primitive for the room spawner and the
    zone reset — so "instantiate a prototype into the world" lives in one
    place."""
    from realm.core.events import fire_event
    spawn = spawn_from_prototype(prototype, room)
    spawn.add_tag(marker)
    if persistence is not None:
        await persistence.save(spawn)
    # actor=None: the spawn reacts to its OWN creation, so it's the witnessed
    # target, not the excluded-from-witnessing actor.
    await fire_event(None, spawn, "event:on_load",
                     extra={"marker": marker, **load_extra})
    return spawn


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
    param_spec = {
        'prototype': ({}, 'the object minted: name, tags, attrs'),
        'count': (1, 'population kept alive at once'),
        'respawn_ticks': (150, 'world beats before a dead spawn returns'),
        'key': (None, 'marker tag naming this spawner\'s brood (default: derived)'),
        'announce': (None, 'room line on each respawn'),
    }

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

        # Spawn one (shared spawn+tag+save+ON_LOAD core).
        spawn = await spawn_tracked(prototype, room, f"spawned:{key}",
                                    persistence, spawner=key)
        alive.append(spawn.id)
        room.db.set(ids_attr, alive)
        room.db.set(f"spawner_{key}_seeded", True)
        room.db.delete(timer_attr)

        announce = self.get_param('announce')
        if announce:
            room.msg_contents(str(announce))
        logger.info(f"Spawner '{key}' spawned {spawn.name} in {room.name}")


def object_prototype(obj: GameObject) -> dict[str, Any]:
    """Snapshot a live object into a spawn prototype (name, description,
    tags, attrs, behaviors) — the object half of a repop."""
    return {
        'name': obj.name,
        'description': str(obj.db.get('description') or ''),
        'tags': [t for t in obj.tags.to_list()
                 if not t.startswith('stocked:') and t != 'prototype'],
        'attrs': {k: v for k, v in obj.db.all().items()
                  if k != 'description'},
        'behaviors': [{'behavior_id': b.behavior_id, 'params': dict(b.params)}
                      for b in obj.get_behaviors()],
    }


@BehaviorRegistry.register
class RestockBehavior(Behavior):
    """
    Keep an owner's canonical objects present: a shop's wares, a room's floor
    loot — the object half of a repop (ROM O/G/E resets). On the first tick
    it snapshots what the owner holds (things, not mobs or exits); thereafter
    it re-mints any that get bought, taken, or destroyed.

    Attach to a room (floor loot) or a shopkeeper (stock). Snapshotting at
    boot means only imported/authored objects are captured, never a player's
    later droppings.

    Params:
        interval (int): world beats between restock checks (default 30).
        filter_tag (str): only restock objects carrying this tag
            (default 'thing').
    """

    behavior_id = "restock"
    param_spec = {
        'interval': (30, 'world beats between restock checks'),
        'filter_tag': ('thing', 'only restock objects with this tag'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, owner: GameObject, delta: float) -> None:
        from realm.persistence.manager import get_active_manager
        persistence = get_active_manager()
        ftag = str(self.get_param('filter_tag', 'thing'))

        # First tick: snapshot the canonical contents.
        if owner.db.get('restock_stock') is None:
            stock = []
            for o in list(owner.contents):
                if not o.has_tag(ftag) or o.has_tag('exit'):
                    continue
                stock.append({'key': o.id, 'prototype': object_prototype(o)})
                o.add_tag(f"stocked:{o.id}")
            owner.db.set('restock_stock', stock)
            owner.db.set('restock_wait', int(self.get_param('interval', 30)))
            return

        wait = int(owner.db.get('restock_wait') or 0)
        if wait > 0:
            owner.db.set('restock_wait', wait - 1)
            return
        owner.db.set('restock_wait', int(self.get_param('interval', 30)))

        for entry in owner.db.get('restock_stock') or []:
            key = entry['key']
            if any(o.has_tag(f"stocked:{key}") for o in owner.contents):
                continue                        # a copy is still here
            item = spawn_from_prototype(entry['prototype'], owner)
            item.add_tag(f"stocked:{key}")
            if persistence is not None:
                await persistence.save(item)


@BehaviorRegistry.register
class PopulationBehavior(Behavior):
    """
    A zone-level mob orchestrator: keep a population of a prototype spread
    across MANY rooms, not just one.

    Where ``spawner`` maintains ``count`` of a mob in a single room, this
    keeps between ``min_alive`` and ``max_alive`` of a mob scattered at
    random across every room matching ``room_tags`` (e.g. ``['outdoor']``,
    ``['zone:midgaard']``, ``['sector:forest']``). When the live count drops
    below ``min_alive`` it trickles ``spawn_batch`` in per top-up until it
    reaches ``max_alive``. Attach it to a zone master (or any object); with
    no ``room_tags`` it uses the master's own ``zone:`` rooms — so it pairs
    naturally with the reset/zone machinery.

    Params:
        prototype (dict): the mob minted (name, tags, attrs, behaviors).
        min_alive (int): replenish when the live count falls below this (1).
        max_alive (int): population cap (default = min_alive).
        room_tags (list[str]): eligible rooms carry ANY of these tags
            (default: the master's own zone).
        respawn_ticks (int): world beats between top-ups (default 20).
        spawn_batch (int): most minted per top-up, so they trickle in (1).
        key (str): marker for this population (default: the prototype name).
        announce (str): room line when one appears.

    State in master.db: ``pop_<key>_ids`` (tracked spawns), ``pop_<key>_wait``.
    """

    behavior_id = "population"
    param_spec = {
        'prototype': ({}, 'the mob minted: name, tags, attrs, behaviors'),
        'min_alive': (1, 'replenish when the live count falls below this'),
        'max_alive': (None, 'population cap (default = min_alive)'),
        'room_tags': (None, 'eligible rooms carry ANY of these tags '
                            '(default: the master zone)'),
        'respawn_ticks': (20, 'world beats between top-ups'),
        'spawn_batch': (1, 'most minted per top-up (they trickle in)'),
        'key': (None, "marker for this population (default: prototype name)"),
        'announce': (None, 'room line when one appears'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    def _key(self) -> str:
        key = self.get_param('key')
        if key:
            return str(key)
        name = str((self.get_param('prototype') or {}).get('name', 'mob'))
        return name.lower().replace(' ', '_')

    def _eligible_rooms(self, master: GameObject) -> list:
        from realm.core.query import find_objects
        from realm.core.zones import zone_rooms, zone_tags

        tags = self.get_param('room_tags')
        if tags:
            return [r for r in find_objects(tag='room')
                    if any(r.has_tag(t) for t in tags)]
        rooms, seen = [], set()
        for zone in zone_tags(master):
            for room in zone_rooms(zone):
                if room.id not in seen:
                    seen.add(room.id)
                    rooms.append(room)
        return rooms

    async def tick(self, master: GameObject, delta: float) -> None:
        import random

        prototype = self.get_param('prototype')
        if not prototype:
            return
        interval = int(self.get_param('respawn_ticks', 20)) + 1
        key = self._key()
        if not self.countdown(master, f'pop_{key}_wait', interval):
            return

        rooms = self._eligible_rooms(master)
        if not rooms:
            return
        from realm.persistence.manager import get_active_manager
        persistence = get_active_manager()

        ids_attr = f'pop_{key}_ids'
        tracked = list(master.db.get(ids_attr) or [])
        if persistence is not None:
            alive = [i for i in tracked
                     if persistence.get_cached(i) is not None]
        else:
            marker = f'spawned:{key}'
            alive = [o.id for r in rooms for o in r.contents
                     if o.has_tag(marker)]

        min_a = int(self.get_param('min_alive', 1))
        max_a = max(min_a, int(self.get_param('max_alive') or min_a))
        # Hysteresis: dropping below min starts a refill up to max; the
        # population then idles and decays back toward min before refilling
        # again (so it does not thrash one-in-one-out at the threshold).
        filling_attr = f'pop_{key}_filling'
        filling = bool(master.db.get(filling_attr))
        if len(alive) < min_a:
            filling = True
        if len(alive) >= max_a:
            filling = False
        master.db.set(filling_attr, filling)
        if not filling:
            master.db.set(ids_attr, alive)      # healthy: prune and rest
            return

        batch = min(int(self.get_param('spawn_batch', 1)), max_a - len(alive))
        announce = self.get_param('announce')
        for _ in range(max(0, batch)):
            room = random.choice(rooms)
            spawn = await spawn_tracked(prototype, room, f'spawned:{key}',
                                        persistence, population=key)
            alive.append(spawn.id)
            if announce:
                room.msg_contents(str(announce))
        master.db.set(ids_attr, alive)


__all__ = ["SpawnerBehavior", "RestockBehavior", "PopulationBehavior",
           "spawn_from_prototype", "spawn_tracked", "object_prototype"]
