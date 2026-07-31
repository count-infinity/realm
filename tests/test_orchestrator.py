"""The mob orchestrator (PopulationBehavior) and the pickpocket (steal).

PopulationBehavior keeps a mob population spread across MANY rooms (a whole
zone, or every 'outdoor' room) between min_alive and max_alive, with random
placement and trickle-in batches -- a true zone-level spawner, not the
per-room `spawner`. StealBehavior is the ROM spec_thief: a stealth contest
that lifts a little coin.
"""

from __future__ import annotations

import pytest

from realm.behaviors.npc import StealBehavior
from realm.behaviors.spawner import PopulationBehavior
from realm.persistence.manager import get_active_manager
from realm.testing import Simulator

WOLF = {"name": "a grey wolf", "tags": ["npc"],
        "attrs": {"hp": 12, "max_hp": 12}}


def _wolves(sim):
    return [o for o in sim.store.all_cached() if o.name == "a grey wolf"]


async def _tick_until(beh, master, n):
    for _ in range(n):
        await beh.tick(master, 4.0)


# --- the orchestrator -------------------------------------------------------

@pytest.mark.asyncio
class TestPopulation:

    async def test_fills_to_max_only_in_matching_rooms(self):
        sim = Simulator()
        try:
            outdoor = [sim.room(f"Field {i}") for i in range(3)]
            for r in outdoor:
                r.add_tag("outdoor")
            hut = sim.room("Hut")                      # indoor, excluded
            master = sim.obj("wolf den")
            beh = PopulationBehavior(prototype=WOLF, min_alive=3, max_alive=6,
                                     room_tags=["outdoor"], spawn_batch=2,
                                     respawn_ticks=0)
            master.add_behavior(beh)
            await _tick_until(beh, master, 30)
            wolves = _wolves(sim)
            assert len(wolves) == 6                    # filled to max
            assert all(w.location in outdoor for w in wolves)
            assert not any(o.name == "a grey wolf" for o in hut.contents)
            # Spread across rooms, not piled in one.
            assert len({w.location.id for w in wolves}) > 1
        finally:
            sim.close()

    async def test_hysteresis_refills_after_a_cull(self):
        sim = Simulator()
        try:
            fields = [sim.room(f"Plain {i}") for i in range(4)]
            for r in fields:
                r.add_tag("outdoor")
            master = sim.obj("den")
            beh = PopulationBehavior(prototype=WOLF, min_alive=2, max_alive=5,
                                     room_tags=["outdoor"], spawn_batch=5,
                                     respawn_ticks=0)
            master.add_behavior(beh)
            await _tick_until(beh, master, 20)
            assert len(_wolves(sim)) == 5
            # Cull below min: delete 4 (1 left < min 2).
            persistence = get_active_manager()
            for w in _wolves(sim)[:4]:
                w.location = None
                await persistence.delete(w)
            assert len(_wolves(sim)) == 1
            await _tick_until(beh, master, 20)
            assert len(_wolves(sim)) == 5              # refilled to max
        finally:
            sim.close()

    async def test_idles_between_min_and_max(self):
        # A population between min and max is left alone (no thrash).
        sim = Simulator()
        try:
            field = sim.room("Steppe")
            field.add_tag("outdoor")
            master = sim.obj("den")
            beh = PopulationBehavior(prototype=WOLF, min_alive=1, max_alive=4,
                                     room_tags=["outdoor"], spawn_batch=4,
                                     respawn_ticks=0)
            master.add_behavior(beh)
            await _tick_until(beh, master, 20)
            assert len(_wolves(sim)) == 4
            persistence = get_active_manager()
            _wolves(sim)[0].location = None            # 4 -> 3, still >= min
            await persistence.delete(_wolves(sim)[0])
            await _tick_until(beh, master, 20)
            assert len(_wolves(sim)) == 3              # idled, not refilled
        finally:
            sim.close()

    async def test_defaults_to_the_masters_zone(self):
        # With no room_tags, eligible rooms are the master's own zone.
        sim = Simulator()
        try:
            r1 = sim.room("Glade")
            r1.add_tag("zone:wildwood")
            elsewhere = sim.room("Town")
            elsewhere.add_tag("zone:city")
            master = sim.obj("wildwood warden")
            master.add_tag("zone:wildwood")
            beh = PopulationBehavior(prototype=WOLF, min_alive=2, max_alive=2,
                                     spawn_batch=2, respawn_ticks=0)
            master.add_behavior(beh)
            await _tick_until(beh, master, 10)
            wolves = _wolves(sim)
            assert len(wolves) == 2
            assert all(w.location is r1 for w in wolves)  # only the zone
        finally:
            sim.close()


# --- pickpocket -------------------------------------------------------------

@pytest.mark.asyncio
class TestSteal:

    async def test_successful_lift_transfers_coin_and_flees(self, monkeypatch):
        sim = Simulator()
        try:
            room = sim.room("Bazaar")
            exit_room = sim.room("Alley")
            door = sim.obj("alley", location=room, tags=["exit"])
            door.db.set("destination", exit_room.id)
            thief = sim.obj("a cutpurse", location=room, tags=["npc"])
            mark = sim.player("Mark", location=room)
            mark.db.set("credits", 100)
            monkeypatch.setattr("realm.behaviors.npc.random.random",
                                lambda: 0.0)            # always try
            monkeypatch.setattr("realm.behaviors.npc.random.randint",
                                lambda a, b: b)          # take the max
            monkeypatch.setattr("realm.core.checks.contest",
                                lambda *a, **k: True)    # the thief wins
            beh = StealBehavior(max_take=30, flee=True)
            await beh.tick(thief, 4.0)
            from realm.core.economy import get_credits
            assert get_credits(mark) == 70               # 30 lifted
            assert get_credits(thief) == 30
            assert thief.location is exit_room           # slipped away
        finally:
            sim.close()

    async def test_a_botched_lift_is_noticed(self, monkeypatch):
        sim = Simulator()
        try:
            room = sim.room("Bazaar")
            thief = sim.obj("a cutpurse", location=room, tags=["npc"])
            mark = sim.player("Mark", location=room)
            mark.db.set("credits", 100)
            monkeypatch.setattr("realm.behaviors.npc.random.random",
                                lambda: 0.0)
            monkeypatch.setattr("realm.core.checks.contest",
                                lambda *a, **k: False)   # caught
            await StealBehavior().tick(thief, 4.0)
            from realm.core.economy import get_credits
            assert get_credits(mark) == 100              # nothing taken
            assert any("pick your pocket" in m for m in sim.seen(mark))
        finally:
            sim.close()

    async def test_immortals_are_not_targeted(self, monkeypatch):
        sim = Simulator()
        try:
            room = sim.room("Bazaar")
            thief = sim.obj("a cutpurse", location=room, tags=["npc"])
            admin = sim.player("Wiz", location=room)
            admin.add_tag("admin")
            admin.db.set("credits", 100)
            monkeypatch.setattr("realm.behaviors.npc.random.random",
                                lambda: 0.0)
            called = []
            monkeypatch.setattr("realm.core.checks.contest",
                                lambda *a, **k: called.append(1) or True)
            await StealBehavior().tick(thief, 4.0)
            from realm.core.economy import get_credits
            assert get_credits(admin) == 100 and not called  # never tried
        finally:
            sim.close()
