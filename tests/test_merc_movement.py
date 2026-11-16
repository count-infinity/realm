"""
MUD_PLAN step 2.5: under Merc, walking spends movement points.

The destination's ``move_cost``, else its ``sector:<name>`` tag (the ROM
importer writes these), is paid from the walker's ``move`` pool. A player
who cannot pay stays put; NPCs and the fleeing walk free; a world whose
rules declare no ``move`` pool is untouched.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"


@pytest.fixture
def merc():
    s = Simulator(game_system=MERC)
    try:
        yield s
    finally:
        s.close()


def _path(sim, *, tags=(), **attrs):
    here = sim.room("Road")
    there = sim.room("Beyond", **attrs)
    for tag in tags:
        there.add_tag(tag)
    door = sim.obj("north", location=here, tags=["exit"])
    door.db.set("destination", there.id)
    back = sim.obj("south", location=there, tags=["exit"])
    back.db.set("destination", here.id)
    return here, there


async def test_walking_drains_move_by_sector(merc):
    here, there = _path(merc, tags=["sector:forest"])
    pat = merc.player("Pat", location=here, move=10, max_move=10)
    await merc.do(pat, "north")
    assert pat.location is there
    assert pat.db.move == 7                       # forest: 3


async def test_a_room_move_cost_wins_over_its_sector(merc):
    here, there = _path(merc, tags=["sector:mountain"], move_cost=2)
    pat = merc.player("Pat", location=here, move=10, max_move=10)
    await merc.do(pat, "north")
    assert pat.db.move == 8


async def test_an_unknown_sector_costs_one(merc):
    here, there = _path(merc)
    pat = merc.player("Pat", location=here, move=10, max_move=10)
    await merc.do(pat, "north")
    assert pat.db.move == 9


async def test_a_walk_the_pool_cannot_pay_is_refused(merc):
    here, there = _path(merc, tags=["sector:mountain"])
    door = next(o for o in here.contents if o.name == "north")
    door.db.on_fail = "set_attr(me, 'why', adata('reason'))"
    pat = merc.player("Pat", location=here, move=5, max_move=10)
    await merc.do(pat, "north")
    assert pat.location is here
    assert pat.db.move == 5
    assert "You are too exhausted." in merc.seen(pat)
    assert door.db.why == "exhausted"


async def test_resting_restores_it(merc):
    here, there = _path(merc, tags=["sector:mountain"])
    pat = merc.player("Pat", location=here, move=5, max_move=100, dexterity=13, level=1)
    await merc.boot()                             # vitals finds the tired at boot
    await merc.do(pat, "rest")
    await merc.world.services["vitals"].tick()
    assert pat.db.move > 5


async def test_npcs_and_the_fleeing_walk_free(merc):
    from realm.core.movement import move_through_exit
    here, there = _path(merc, tags=["sector:mountain"])
    dog = merc.obj("dog", location=here, tags=["npc"], move=1, max_move=10)
    await move_through_exit(dog, there, direction="north")
    assert dog.location is there and dog.db.move == 1
    pat = merc.player("Pat", location=there, move=1, max_move=10)
    await move_through_exit(pat, here, direction="south", fleeing=True)
    assert pat.location is here and pat.db.move == 1


async def test_a_gurps_world_is_unaffected():
    sim = Simulator()
    try:
        here, there = _path(sim, tags=["sector:mountain"])
        pat = sim.player("Pat", location=here, move=1, max_move=10)
        await sim.do(pat, "north")
        assert pat.location is there
        assert pat.db.move == 1
    finally:
        sim.close()
