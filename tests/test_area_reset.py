"""
Area (zone) reset — presence-gated scheduled repopulation of a zone's
canonical contents, keyed on the zone master (SMAUG ``area_update`` / tbaMUD
zone reset). The whole zone returns to its authored state on a timer, but
only while no player is watching; a declarative ``reset_spec`` tops each
entry back to ``count``, and ``ON_RESET`` fires for the rest (doors, litter).
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core import area_reset
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    crypt = sim.room("Crypt")
    crypt.add_tag("zone:crypt")
    hall = sim.room("Hall")                       # outside the zone
    master = sim.obj("Crypt Brain", tags=["zone_master", "zone:crypt"])
    master.db.set("reset_interval", 300)
    master.db.set("reset_spec", [
        {"prototype": {"name": "a skeleton", "tags": ["npc"]},
         "room": crypt.id, "count": 2},
    ])
    alice = sim.player("Alice", location=hall)     # not in the zone
    try:
        yield SimpleNamespace(sim=sim, store=sim.store, crypt=crypt,
                              hall=hall, master=master, alice=alice)
    finally:
        sim.close()


def _skeletons(room):
    return [o for o in room.contents if o.name == "a skeleton"]


@pytest.mark.asyncio
class TestAreaReset:

    async def test_repops_when_empty_and_due(self, world):
        w = world
        n = await area_reset.reset_zones(w.store, now=time.time())
        assert n == 1
        assert len(_skeletons(w.crypt)) == 2

    async def test_deferred_while_a_player_is_present(self, world):
        w = world
        w.alice.location = w.crypt                 # someone's watching
        n = await area_reset.reset_zones(w.store, now=time.time())
        assert n == 0
        assert _skeletons(w.crypt) == []           # no pop on top of players

    async def test_not_due_does_not_reset(self, world):
        w = world
        w.master.db.set("last_reset", 1000.0)
        n = await area_reset.reset_zones(w.store, now=1010.0)   # only 10s on
        assert n == 0
        assert _skeletons(w.crypt) == []

    async def test_kill_then_reset_tops_up_not_doubles(self, world):
        w = world
        await area_reset.reset_zones(w.store, now=1000.0)       # spawns 2
        victim = _skeletons(w.crypt)[0]
        victim.location = None
        await w.store.delete(victim)               # a player killed one

        await area_reset.reset_zones(w.store, now=2000.0)       # due again

        assert len(_skeletons(w.crypt)) == 2       # topped back to 2, not 4

    async def test_on_reset_fires_on_the_master(self, world):
        w = world
        w.master.db.set("on_reset", "set_attr(me, 'ticked', 1)")
        await area_reset.reset_zones(w.store, now=time.time())
        assert w.master.db.get("ticked") == 1

    async def test_reset_spawns_are_persistent_canonical(self, world):
        w = world
        await area_reset.reset_zones(w.store, now=time.time())
        skel = _skeletons(w.crypt)[0]
        # Tagged for liveness, NOT ephemeral (canonical area contents survive).
        assert skel.has_tag(f"reset:{w.master.id}:0")
        assert not skel.has_tag("ephemeral")
