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

    async def test_wear_all_puts_on_what_fits(self, merc):
        # ROM's `wear all`: everything carried that can be worn where a slot
        # is free; a full slot is passed over, never replaced.
        pat = merc.player("Pat", location=merc.room("Hall"))
        vest = merc.obj("a vest", location=pat, tags=["thing", "wearable"], slot="body")
        shield = merc.obj("a shield", location=pat, tags=["thing", "wearable"], slot="shield")
        rings = [_ring(merc, pat, name) for name in ("a gold ring", "a jade ring",
                                                     "a tin ring")]
        bread = merc.obj("a bread", location=pat, tags=["thing", "food"])
        await merc.do(pat, "wear all")
        out = _text(merc, pat)
        assert vest.has_tag("worn") and shield.has_tag("worn")
        assert [r.has_tag("worn") for r in rings] == [True, True, False]
        assert not bread.has_tag("worn")
        assert "You put on the vest." in out and "You put on the shield." in out
        assert "already wearing" not in out
        await merc.do(pat, "wear all")
        assert _text(merc, pat) == "You have nothing more to wear."

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


class TestGearStaysOnUntilTakenOff:
    """ROM's ``get_obj_carry`` finds only what is not worn (``wear_loc ==
    WEAR_NONE``): ``drop all`` leaves equipment on, ``drop``/``give``/
    ``put``/``sell`` of a worn thing by name says to take it off first
    ("You must remove it first.", ``do_give``), and a name that also fits a
    carried spare means the spare (BACKLOG 2026-11-17)."""

    def _kit(self, sim):
        room = sim.room("Square")
        pat = sim.player("Pat", location=room)
        sword = sim.obj("a long sword", location=pat, tags=["thing", "weapon", "wielded"])
        ring = sim.obj("a gold ring", location=pat, tags=["thing", "wearable", "worn"],
                       slot="finger")
        apple = sim.obj("an apple", location=pat, tags=["thing"])
        sim.seen(pat)
        return room, pat, sword, ring, apple

    async def test_get_all_from_an_empty_container_says_so(self, merc):
        # It read "There's nothing to get corpse of the beastly fido."
        room = merc.room("Hall")
        pat = merc.player("Pat", location=room)
        merc.obj("corpse of the beastly fido", location=room,
                 tags=["thing", "container"], article="the")
        await merc.do(pat, "get all from corpse")
        assert _text(merc, pat) == "There is nothing in the corpse of the beastly fido."

    async def test_drop_all_keeps_what_is_worn_and_wielded(self, merc):
        room, pat, sword, ring, apple = self._kit(merc)
        await merc.do(pat, "drop all")
        assert apple.location is room
        assert sword.location is pat and sword.has_tag("wielded")
        assert ring.location is pat and ring.has_tag("worn")
        assert merc.seen(pat) == ["You drop an apple."]
        await merc.do(pat, "drop all")
        assert merc.seen(pat) == ["You aren't carrying anything."]

    async def test_drop_give_and_put_by_name_say_take_it_off(self, merc):
        room, pat, sword, ring, _apple = self._kit(merc)
        sam = merc.player("Sam", location=room)
        bag = merc.obj("a bag", location=pat, tags=["thing", "container"])
        await merc.do(pat, "drop ring")
        assert merc.seen(pat) == ["You must remove it first."]
        await merc.do(pat, "drop sword")
        assert merc.seen(pat) == ["You must unwield it first."]
        await merc.do(pat, "give ring to Sam")
        assert merc.seen(pat) == ["You must remove it first."]
        await merc.do(pat, "put sword in bag")
        assert merc.seen(pat) == ["You must unwield it first."]
        assert sword.location is pat and ring.location is pat
        assert sword.has_tag("wielded") and ring.has_tag("worn")
        assert not sam.contents and not bag.contents

    async def test_a_carried_spare_answers_before_the_worn_one(self, merc):
        room, pat, sword, _ring_, _apple = self._kit(merc)
        spare = merc.obj("a long sword", location=pat, tags=["thing", "weapon"])
        await merc.do(pat, "drop sword")
        assert spare.location is room and sword.location is pat

    async def test_a_script_cannot_drop_or_give_what_its_npc_wields(self, merc):
        from realm.std.items.verbs import do_drop, do_give
        room = merc.room("Yard")
        guard = merc.obj("a guard", location=room, tags=["npc"])
        pike = merc.obj("a pike", location=guard, tags=["thing", "weapon", "wielded"])
        pat = merc.player("Pat", location=room)
        assert not await do_drop(guard, pike)
        assert not await do_give(guard, pike, pat)
        assert pike.location is guard and pike.has_tag("wielded")

    async def test_sell_and_eat_by_name_say_take_it_off(self, merc):
        from realm.core.behaviors import BehaviorRegistry
        room, pat, _sword, ring, _apple = self._kit(merc)
        keeper = merc.obj("a jeweller", location=room, tags=["npc"], credits=1000)
        keeper.add_behavior(BehaviorRegistry.create("shopkeeper"))
        await merc.do(pat, "sell ring")
        assert merc.seen(pat) == ["You must remove it first."]
        assert ring.location is pat and ring.has_tag("worn")
        bun = merc.obj("a sugared bun", location=pat, tags=["thing", "food", "worn"],
                       slot="held", nourishment=10)
        await merc.do(pat, "eat bun")
        assert merc.seen(pat) == ["You must remove it first."]
        assert bun.location is pat
