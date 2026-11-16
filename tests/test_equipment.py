"""
MUD_PLAN step 3.1: wear slots and the ``equipment`` command.

The game system names its slots and how many items each holds
(``GameSystem.wear_slots``). Merc has Diku's: two rings, two necks, two
wrists, one of each other place. A neutral system has none, which means any
slot name, one item each, as before.
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


@pytest.fixture
def gurps():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _ring(sim, owner, name):
    return sim.obj(name, location=owner, tags=["thing", "wearable"], slot="finger")


def _text(sim, player):
    return "\n".join(sim.seen(player))


class TestMercSlots:

    def test_merc_names_diku_slots(self, merc):
        slots = dict(merc.game_system.wear_slots())
        assert slots["finger"] == 2 and slots["neck"] == 2 and slots["wrist"] == 2
        assert slots["body"] == 1 and slots["held"] == 1 and slots["light"] == 1
        assert [name for name, _n in merc.game_system.wear_slots()][:3] == [
            "light", "finger", "neck"]

    async def test_two_rings_then_a_third_is_refused(self, merc):
        room = merc.room("Shop")
        pat = merc.player("Pat", location=room)
        gold, silver, iron = (_ring(merc, pat, n) for n in
                              ("a gold ring", "a silver ring", "an iron ring"))
        await merc.do(pat, "wear gold")
        await merc.do(pat, "wear silver")
        assert gold.has_tag("worn") and silver.has_tag("worn")
        merc.seen(pat)
        await merc.do(pat, "wear iron")
        assert not iron.has_tag("worn")
        out = _text(merc, pat)
        assert "a gold ring" in out and "a silver ring" in out
        assert "wear iron ring replace" in out

    async def test_replace_takes_off_the_oldest(self, merc):
        room = merc.room("Shop")
        pat = merc.player("Pat", location=room)
        gold, silver, iron = (_ring(merc, pat, n) for n in
                              ("a gold ring", "a silver ring", "an iron ring"))
        await merc.do(pat, "wear gold")
        await merc.do(pat, "wear silver")
        await merc.do(pat, "wear iron replace")
        assert iron.has_tag("worn") and silver.has_tag("worn")
        assert not gold.has_tag("worn")
        assert "You take off a gold ring." in _text(merc, pat)

    async def test_a_cursed_ring_cannot_be_replaced(self, merc):
        room = merc.room("Shop")
        pat = merc.player("Pat", location=room)
        gold, silver, iron = (_ring(merc, pat, n) for n in
                              ("a gold ring", "a silver ring", "an iron ring"))
        gold.db.on_check = "if atype == 'item:on_remove': block('It is welded on.')"
        await merc.do(pat, "wear gold")
        await merc.do(pat, "wear silver")
        await merc.do(pat, "wear iron replace")
        assert gold.has_tag("worn") and not iron.has_tag("worn")

    async def test_a_slot_the_system_lacks_is_refused(self, merc):
        room = merc.room("Shop")
        pat = merc.player("Pat", location=room)
        halo = merc.obj("a halo", location=pat, tags=["thing", "wearable"], slot="float")
        await merc.do(pat, "wear halo")
        assert not halo.has_tag("worn")
        assert "float" in _text(merc, pat)

    async def test_equipment_lists_every_slot(self, merc):
        room = merc.room("Shop")
        pat = merc.player("Pat", location=room)
        gold = _ring(merc, pat, "a gold ring")
        merc.obj("a short sword", location=pat, tags=["thing", "weapon", "wielded"])
        await merc.do(pat, "wear gold")
        merc.seen(pat)
        await merc.do(pat, "eq")
        lines = "\n".join(merc.seen(pat)).splitlines()
        out = "\n".join(lines)
        for slot, count in merc.game_system.wear_slots():
            assert sum(f"<{slot}>" in line for line in lines) == count, slot
        assert "a gold ring" in out and "a short sword" in out
        assert sum("nothing" in line for line in lines) >= 15
        assert gold.has_tag("worn")


class TestInventoryAndNeutral:

    async def test_inventory_no_longer_lists_worn_and_wielded(self, merc):
        room = merc.room("Shop")
        pat = merc.player("Pat", location=room)
        _ring(merc, pat, "a gold ring")
        merc.obj("a short sword", location=pat, tags=["thing", "weapon", "wielded"])
        merc.obj("a loaf", location=pat, tags=["thing"])
        await merc.do(pat, "wear gold")
        merc.seen(pat)
        await merc.do(pat, "inventory")
        out = _text(merc, pat)
        assert "a loaf" in out
        assert "gold ring" not in out and "short sword" not in out

    async def test_a_gurps_world_behaves_as_before(self, gurps):
        assert gurps.game_system.wear_slots() == []
        room = gurps.room("Lab")
        pat = gurps.player("Pat", location=room)
        goggles = gurps.obj("goggles", location=pat, tags=["thing", "wearable"], slot="eyes")
        visor = gurps.obj("visor", location=pat, tags=["thing", "wearable"], slot="eyes")
        badge = gurps.obj("badge", location=pat, tags=["thing", "wearable"])
        await gurps.do(pat, "wear goggles")
        await gurps.do(pat, "wear visor")
        await gurps.do(pat, "wear badge")
        assert goggles.has_tag("worn") and badge.has_tag("worn")
        assert not visor.has_tag("worn")
        assert "You're already wearing goggles there." in _text(gurps, pat)
        await gurps.do(pat, "equipment")
        out = _text(gurps, pat)
        assert "<eyes>" in out and "goggles" in out and "badge" in out
