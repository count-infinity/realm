"""
MUD_PLAN step 3.4: consumables.

``eat`` and ``drink`` (the ``items`` feature) fire a gated ``item:on_eat`` /
``item:on_drink``, mend the pools in the item's ``restores``, then use the
item up. ``quaff``, ``recite``, ``zap`` and ``brandish`` (the ``abilities``
feature) invoke the spells in the item's ``spells`` at its ``spell_level``,
free and with no class check, then use the item up.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"


@pytest.fixture
async def sim():
    from realm.packs import import_pack
    s = Simulator(game_system=MERC)
    await import_pack("merc-classic", s.store)
    try:
        yield s
    finally:
        s.world.services["combat"].stop_all()
        s.close()


def _player(sim, room, **attrs):
    stats = dict(hp=10, max_hp=30, mana=0, max_mana=100, level=1, wisdom=13,
                 intelligence=13, dexterity=13, constitution=13)
    stats.update(attrs)
    return sim.player("Pat", location=room, **stats)


@pytest.fixture
def max_dice(monkeypatch):
    monkeypatch.setattr("realm.std.abilities.abilities.random.randint", lambda a, b: b)


class TestEatAndDrink:

    async def test_eating_restores_and_removes_the_food(self, sim):
        room = sim.room("Inn")
        pat = _player(sim, room)
        stew = sim.obj("a bowl of stew", location=pat, tags=["thing", "food"],
                       restores={"hp": 4})
        stew.db.on_eat = "pemit(enactor, 'Hearty!')"
        await sim.do(pat, "eat stew")
        assert pat.db.hp == 14
        assert stew.location is None and sim.store.get_cached(stew.id) is None
        seen = sim.seen(pat)
        assert "Hearty!" in seen
        assert "You eat a bowl of stew." in seen

    async def test_what_is_not_food_is_refused(self, sim):
        room = sim.room("Inn")
        pat = _player(sim, room)
        rock = sim.obj("a rock", location=pat, tags=["thing"])
        await sim.do(pat, "eat rock")
        assert rock.location is pat
        assert "That's not edible." in sim.seen(pat)

    async def test_a_gate_can_refuse_the_meal(self, sim):
        room = sim.room("Inn")
        pat = _player(sim, room)
        apple = sim.obj("an apple", location=pat, tags=["thing", "food"], restores={"hp": 4})
        apple.db.on_check = "if atype == 'item:on_eat': block('It is wax.')"
        await sim.do(pat, "eat apple")
        assert apple.location is pat and pat.db.hp == 10
        assert "It is wax." in sim.seen(pat)

    async def test_drinking_lowers_charges_until_empty(self, sim):
        room = sim.room("Inn")
        pat = _player(sim, room)
        flask = sim.obj("a flask", location=pat, tags=["thing", "drink"], charges=2,
                        restores={"hp": 1})
        await sim.do(pat, "drink flask")
        await sim.do(pat, "drink flask")
        assert flask.db.charges == 0 and pat.db.hp == 12
        sim.seen(pat)
        await sim.do(pat, "drink flask")
        assert pat.db.hp == 12
        assert "a flask is empty." in sim.seen(pat)
        assert flask.location is pat                     # a container stays

    async def test_a_fountain_never_runs_dry(self, sim):
        room = sim.room("Square")
        pat = _player(sim, room)
        sim.obj("a fountain", location=room, tags=["thing", "drink", "fixed"],
                restores={"hp": 1})
        for _ in range(3):
            await sim.do(pat, "drink fountain")
        assert pat.db.hp == 13


class TestMagicItems:

    async def test_quaffing_cure_light_heals_and_consumes_it(self, sim, max_dice):
        room = sim.room("Shop")
        pat = _player(sim, room)
        potion = sim.obj("a red potion", location=pat, tags=["thing", "potion"],
                         spells=["cure light"], spell_level=12)
        await sim.do(pat, "quaff red")
        assert pat.db.hp > 10
        assert pat.db.mana == 0                         # free
        assert sim.store.get_cached(potion.id) is None

    async def test_a_warrior_can_use_a_mages_wand(self, sim, max_dice):
        room = sim.room("Field")
        pat = _player(sim, room, character_class="warrior")
        rat = sim.obj("rat", location=room, tags=["npc"], hp=30, max_hp=30)
        wand = sim.obj("a wand", location=pat, tags=["thing", "wand"],
                       spells=["magic missile"], spell_level=4, charges=2)
        await sim.do(pat, "zap wand rat")
        assert rat.db.hp < 30
        assert wand.db.charges == 1 and wand.location is pat

    async def test_a_wand_with_no_charges_fizzles(self, sim):
        room = sim.room("Field")
        pat = _player(sim, room)
        rat = sim.obj("rat", location=room, tags=["npc"], hp=30, max_hp=30)
        wand = sim.obj("a wand", location=pat, tags=["thing", "wand"],
                       spells=["magic missile"], spell_level=4, charges=0)
        await sim.do(pat, "zap wand rat")
        assert rat.db.hp == 30 and wand.location is pat
        assert any("fizzles" in line for line in sim.seen(pat))

    async def test_reciting_fireball_starts_a_fight_like_cast(self, sim, max_dice):
        room = sim.room("Field")
        pat = _player(sim, room)
        rat = sim.obj("rat", location=room, tags=["npc"], hp=300, max_hp=300)
        scroll = sim.obj("a scroll", location=pat, tags=["thing", "scroll"],
                         spells=["fireball"], spell_level=20)
        await sim.do(pat, "recite scroll rat")
        assert rat.db.hp < 300
        assert pat.has_tag("in_combat") and rat.has_tag("in_combat")
        assert sim.store.get_cached(scroll.id) is None

    async def test_brandishing_a_staff_reaches_the_room(self, sim, max_dice):
        room = sim.room("Field")
        pat = _player(sim, room)
        rats = [sim.obj(f"rat {i}", location=room, tags=["npc"], hp=300, max_hp=300)
                for i in range(2)]
        staff = sim.obj("a staff", location=pat, tags=["thing", "staff"],
                        spells=["magic missile"], spell_level=5, charges=3)
        await sim.do(pat, "brandish staff")
        assert all(r.db.hp < 300 for r in rats)
        assert pat.db.hp == 10                          # not at the brandisher
        assert staff.db.charges == 2

    async def test_the_wrong_kind_of_item_is_refused(self, sim):
        room = sim.room("Shop")
        pat = _player(sim, room)
        scroll = sim.obj("a scroll", location=pat, tags=["thing", "scroll"],
                         spells=["cure light"], spell_level=5)
        await sim.do(pat, "quaff scroll")
        assert scroll.location is pat
        assert "You can't quaff a scroll." in sim.seen(pat)

    async def test_an_unknown_spell_does_nothing_but_says_so(self, sim):
        room = sim.room("Shop")
        pat = _player(sim, room)
        potion = sim.obj("a murky potion", location=pat, tags=["thing", "potion"],
                         spells=["polymorph other"], spell_level=5)
        await sim.do(pat, "quaff murky")
        assert sim.store.get_cached(potion.id) is None   # drunk all the same
        assert any("Nothing happens." in line for line in sim.seen(pat))
