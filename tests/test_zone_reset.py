"""
ZoneResetBehavior — presence-gated scheduled repopulation of a zone's
canonical contents, a behavior on the zone master (SMAUG area reset). The
whole zone returns to its authored state on a timer, but only while no
player is inside; each reset clears the master's prior spawns and reloads
the declarative ``reset_spec`` fresh, and fires ``ON_RESET`` for the rest.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core.behaviors import BehaviorRegistry
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    crypt = sim.room("Crypt")
    crypt.add_tag("zone:crypt")
    hall = sim.room("Hall")                        # outside the zone
    master = sim.obj("Crypt Brain", tags=["zone_master", "zone:crypt"])
    master.db.set("reset_interval", 300)
    master.db.set("reset_spec", [
        {"prototype": {"name": "a skeleton", "tags": ["npc"]},
         "room": crypt.id, "count": 2},
    ])
    behavior = BehaviorRegistry.create("zone_reset")
    master.add_behavior(behavior)
    alice = sim.player("Alice", location=hall)     # not in the zone
    try:
        yield SimpleNamespace(sim=sim, store=sim.store, crypt=crypt, hall=hall,
                              master=master, behavior=behavior, alice=alice)
    finally:
        sim.close()


def _skeletons(room):
    return [o for o in room.contents if o.name == "a skeleton"]


async def _force_due(w):
    w.master.db.set("last_reset", 0)               # long overdue
    await w.behavior.tick(w.master, 4.0)


@pytest.mark.asyncio
class TestZoneReset:

    async def test_repops_when_empty_and_due(self, world):
        w = world
        await _force_due(w)
        assert len(_skeletons(w.crypt)) == 2

    async def test_deferred_while_a_player_is_present(self, world):
        w = world
        w.alice.location = w.crypt                  # someone's watching
        await _force_due(w)
        assert _skeletons(w.crypt) == []           # no pop on top of players
        assert float(w.master.db.get("last_reset")) == 0   # not bumped; will retry

    async def test_not_due_does_not_reset(self, world):
        w = world
        w.master.db.set("last_reset", time.time())  # just reset
        await w.behavior.tick(w.master, 4.0)        # far from due
        assert _skeletons(w.crypt) == []

    async def test_reset_clears_then_reloads_no_accumulation(self, world):
        w = world
        await _force_due(w)
        first = set(o.id for o in _skeletons(w.crypt))
        assert len(first) == 2
        # Reset again — clears the prior two and reloads fresh (not 4).
        await _force_due(w)
        second = set(o.id for o in _skeletons(w.crypt))
        assert len(second) == 2
        assert first.isdisjoint(second)            # cleared, reloaded

    async def test_removed_spec_entry_mobs_are_purged(self, world):
        w = world
        await _force_due(w)
        assert len(_skeletons(w.crypt)) == 2
        w.master.db.set("reset_spec", [])          # builder removed the entry
        await _force_due(w)
        assert _skeletons(w.crypt) == []           # old spawns cleared, none new

    async def test_on_reset_fires_on_the_master(self, world):
        w = world
        w.master.db.set("on_reset", "set_attr(me, 'ticked', 1)")
        await _force_due(w)
        assert w.master.db.get("ticked") == 1

    async def test_reset_spawns_are_persistent_canonical(self, world):
        w = world
        await _force_due(w)
        skel = _skeletons(w.crypt)[0]
        assert skel.has_tag(f"reset:{w.master.id}")
        assert not skel.has_tag("ephemeral")

    async def test_a_cleared_mob_takes_what_it_carries_with_it(self, world):
        # A spec prototype's ``contents`` (the importer's G and E resets)
        # come with each spawn; a reset clears them with their mob rather
        # than leaving them inside a deleted mob (BACKLOG 2026-11-17).
        w = world
        w.master.db.set("reset_spec", [
            {"prototype": {"name": "a skeleton", "tags": ["npc"], "contents": [
                {"name": "a rusty sword", "tags": ["thing", "weapon", "wielded"]},
                {"name": "a bone", "tags": ["thing"]}]},
             "room": w.crypt.id, "count": 1},
        ])
        await _force_due(w)
        [first] = _skeletons(w.crypt)
        sword = next(o for o in first.contents if o.name == "a rusty sword")
        await _force_due(w)
        [second] = _skeletons(w.crypt)
        assert {o.name for o in second.contents} == {"a rusty sword", "a bone"}
        assert w.store.get_cached(sword.id) is None and sword.location is None
        swords = [o for o in w.store.all_cached() if o.name == "a rusty sword"]
        assert swords == [next(o for o in second.contents if o.name == "a rusty sword")]

    async def test_a_reset_leaves_the_floor_a_corpse_and_a_players_things(self, world):
        # Only the master's spawns and what is inside them go: a thing on
        # the floor, a corpse, and a player's own thing a skeleton was given
        # (it goes home to its owner) stay in the world.
        w = world
        await _force_due(w)
        skeleton = _skeletons(w.crypt)[0]
        litter = w.sim.obj("a torn map", location=w.crypt, tags=["thing"])
        corpse = w.sim.obj("corpse of a skeleton", location=w.crypt,
                           tags=["thing", "container"])
        ring = w.sim.obj("Alice's ring", location=skeleton, tags=["thing"])
        ring.owner = w.alice
        w.alice.db.set("home", w.hall.id)
        await _force_due(w)
        assert litter.location is w.crypt and corpse.location is w.crypt
        assert ring.location is w.hall and w.store.get_cached(ring.id) is ring


@pytest.mark.asyncio
async def test_a_reset_puts_doors_back_as_they_were(world):
    # ROM's reset_room sets every exit back to its reset flags (the room
    # file's door and the area's D resets): a gate players opened closes, a
    # lock they picked locks, a door they shut opens. Here an object's
    # ``reset_tags`` ({tag: present}) are put back at each reset.
    w = world
    gate = w.sim.obj("west", location=w.crypt, tags=["exit", "door"],
                     destination=w.hall.id,
                     reset_tags={"closed": True, "locked": True})
    hatch = w.sim.obj("down", location=w.crypt, tags=["exit", "door", "closed"],
                      destination=w.hall.id,
                      reset_tags={"closed": False, "locked": False})
    outside = w.sim.obj("east", location=w.hall, tags=["exit", "door"],
                        destination=w.crypt.id, reset_tags={"closed": True})
    await _force_due(w)
    assert gate.has_tag("closed") and gate.has_tag("locked")
    assert not hatch.has_tag("closed")
    assert not outside.has_tag("closed")           # the hall is not the master's zone
