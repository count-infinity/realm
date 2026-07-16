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

import realm.behaviors  # noqa: F401  (registers ZoneResetBehavior)
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
