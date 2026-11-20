"""
MUD_PLAN step 12: hunger, thirst and fatigue (the ``needs`` feature),
after CoffeeMud.

``food`` and ``water`` are down pools the game system declares (Merc does,
Decision D6); ``fatigue`` is an up pool a game adds itself. Every
``NEEDS_INTERVAL`` an online, awake player loses food by its weight and
water by its weight times the room's thirst rate; walking costs an
interval more. Going without escalates reminders and, past
``HUNGER_DEATH_HOURS`` / ``THIRST_DEATH_HOURS``, kills through the
ordinary death path. Hunger and thirst each halve recovery. Food is eaten
a bite at a time; drink is drunk a sip at a time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from realm.config.loader import Settings
from realm.core.action_types import ActionType
from realm.core.pools import harm, mend, settle
from realm.core.propagation import Action, propagate
from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"
GURPS = "realm.games.gurps.system.GurpsSystem"
MIDGAARD = (Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard"
            / "data" / "areas" / "midgaard.json")


def _sim(system=MERC, **raw):
    return Simulator(game_system=system, settings=Settings(raw=raw))


@pytest.fixture
def merc():
    s = _sim()
    try:
        yield s
    finally:
        s.close()


def _needs(sim):
    return sim.world.services["needs"]


def _eater(sim, room, name="Pat", **attrs):
    """A Merc character made as character creation makes one: the system's
    baseline gives full food and water."""
    stats = dict(hp=20, max_hp=20)
    stats.update(attrs)
    player = sim.player(name, location=room, **stats)
    sim.world.rules.apply_baseline(player)
    return player


async def _ticks(sim, n):
    for _ in range(n):
        await _needs(sim).tick()


def _path(sim, *, tags=()):
    here = sim.room("Road")
    there = sim.room("Beyond")
    for tag in tags:
        there.add_tag(tag)
    door = sim.obj("north", location=here, tags=["exit"])
    door.db.set("destination", there.id)
    return here, there


def _zone(sim, name, **attrs):
    return sim.obj(f"{name} master", tags=["zone_master", f"zone:{name}"], **attrs)


# --- 12.1 the pools ----------------------------------------------------------------


class TestThePools:

    def test_a_new_merc_character_has_a_full_stomach(self, merc):
        pat = _eater(merc, merc.room("Inn"))
        assert (pat.db.food, pat.db.max_food) == (500, 500)
        assert (pat.db.water, pat.db.max_water) == (1000, 1000)

    def test_the_stomach_scales_by_weight(self, merc):
        ox = _eater(merc, merc.room("Inn"), weight=300)
        assert (ox.db.max_food, ox.db.max_water) == (1000, 2000)
        assert merc.world.rules.stomach(ox) == (1000, 2000)

    def test_the_settings_are_the_base_maximums(self):
        sim = _sim(FOOD_FULL=200, WATER_FULL=300)
        try:
            pat = _eater(sim, sim.room("Inn"))
            assert (pat.db.max_food, pat.db.max_water) == (200, 300)
        finally:
            sim.close()

    @pytest.mark.parametrize("system", [GURPS, "realm.games.d20.system.D20System"])
    def test_gurps_and_d20_have_no_needs(self, system):
        sim = _sim(system)
        try:
            pat = _eater(sim, sim.room("Inn"))
            assert pat.db.get("food") is None and pat.db.get("water") is None
        finally:
            sim.close()

    async def test_a_character_made_before_gets_them_at_login(self, merc):
        inn = merc.room("Inn")
        old = merc.player("Old", location=inn, hp=20, max_hp=20)
        assert old.db.get("food") is None
        await propagate(Action(actor=old, target=inn, action_type=ActionType.CONNECT))
        assert (old.db.food, old.db.water) == (500, 1000)

    async def test_food_and_water_do_not_regenerate(self, merc):
        pat = _eater(merc, merc.room("Inn"), food=100, water=100)
        await settle(harm(pat, "hp", 5))
        await merc.world.services["vitals"].tick()
        assert (pat.db.food, pat.db.water) == (100, 100)
        assert pat.db.hp > 15


# --- 12.2 losing them --------------------------------------------------------------


class TestLosingThem:

    async def test_the_pools_fall_each_interval(self, merc):
        pat = _eater(merc, merc.room("Inn"))
        await _ticks(merc, 3)
        assert (pat.db.food, pat.db.water) == (497, 997)

    async def test_a_heavy_character_falls_faster_and_a_light_one_slower(self, merc):
        inn = merc.room("Inn")
        ox = _eater(merc, inn, name="Ox", weight=300)
        mouse = _eater(merc, inn, name="Mouse", weight=75)
        await _ticks(merc, 3)
        assert ox.db.food == 1000 - 6                 # twice the base weight: 2 a tick
        assert mouse.db.food == 250 - 1               # half: 0.5 a tick, carried over
        assert mouse.db.food_debt == pytest.approx(0.5)

    async def test_the_loss_settings_scale_it(self):
        sim = _sim(FOOD_LOSS=200, WATER_LOSS=50)
        try:
            pat = _eater(sim, sim.room("Inn"))
            await _ticks(sim, 2)
            assert (pat.db.food, pat.db.water) == (496, 999)
        finally:
            sim.close()

    async def test_only_online_awake_mortal_players_lose(self, merc):
        inn = merc.room("Inn")
        sleeper = _eater(merc, inn, name="Sleeper")
        sleeper.add_tag("sleeping")
        admin = _eater(merc, inn, name="Wiz")
        admin.add_tag("admin")
        exempt = _eater(merc, inn, name="Ghost")
        exempt.add_tag("no_needs")
        offline = merc.obj("Gone", location=inn, tags=["player"], food=500, max_food=500,
                           water=1000, max_water=1000)
        rat = merc.obj("rat", location=inn, tags=["npc"], hp=5, max_hp=5)
        await _ticks(merc, 5)
        for who in (sleeper, admin, exempt, offline):
            assert (who.db.food, who.db.water) == (500, 1000), who.name
        assert rat.db.get("food") is None                 # NPCs are never given them

    async def test_a_no_needs_zone_is_exempt(self, merc):
        lounge = merc.room("Lounge")
        lounge.add_tag("zone:haven")
        _zone(merc, "haven", no_needs=True)
        pat = _eater(merc, lounge)
        await _ticks(merc, 4)
        assert (pat.db.food, pat.db.water) == (500, 1000)

    async def test_the_climate_sets_the_thirst_rate(self, merc):
        hot = merc.room("Furnace")
        hot.add_tag("climate:hot")
        desert = merc.room("Dunes")
        desert.add_tag("climate:hot")
        desert.add_tag("climate:dry")
        marsh = merc.room("Marsh")
        marsh.add_tag("climate:wet")
        a = _eater(merc, hot, name="A")
        b = _eater(merc, desert, name="B")
        c = _eater(merc, marsh, name="C")
        await _ticks(merc, 2)
        assert a.db.water == 1000 - 4                 # hot doubles it
        assert b.db.water == 1000 - 6                 # hot and dry: three times
        assert c.db.water == 1000                     # wet removes it
        assert {a.db.food, b.db.food, c.db.food} == {498}   # hunger ignores climate

    async def test_a_zone_master_gives_its_rooms_a_climate(self, merc):
        dune = merc.room("Dune")
        dune.add_tag("zone:desert")
        _zone(merc, "desert").add_tag("climate:windy")
        pat = _eater(merc, dune)
        await _ticks(merc, 1)
        assert pat.db.water == 998

    async def test_walking_costs_one_more_interval(self, merc):
        here, there = _path(merc, tags=["climate:hot"])
        pat = _eater(merc, here, move=100, max_move=100)
        await merc.do(pat, "north")
        assert pat.location is there
        assert (pat.db.food, pat.db.water) == (499, 998)

    async def test_the_sweep_ticks_once_per_interval_of_its_clock(self, merc, monkeypatch):
        import realm.std.needs.needs as needs_module
        clock = [100.0]
        monkeypatch.setattr(needs_module, "now", lambda: clock[0])
        pat = _eater(merc, merc.room("Inn"))
        await _needs(merc).sweep()                    # starts the clock
        clock[0] += 3
        await _needs(merc).sweep()
        assert pat.db.food == 500
        clock[0] += 9                                 # 12 s since the start: 3 intervals
        await _needs(merc).sweep()
        assert pat.db.food == 497

    async def test_fatigue_rises_awake_and_falls_asleep(self, merc):
        inn = merc.room("Inn")
        pat = merc.player("Pat", location=inn, fatigue=0, max_fatigue=10,
                          pools={"fatigue": {"direction": "up", "regen": False}})
        await _ticks(merc, 7)
        assert pat.db.fatigue == 7
        pat.add_tag("sleeping")
        await _ticks(merc, 2)
        assert pat.db.fatigue == 1                    # FATIGUE_SLEEP_RECOVERY: 3
        await _ticks(merc, 1)
        assert pat.db.fatigue == 0


# --- 12.3 going without ---------------------------------------------------------


#: 200 ticks to death from hunger or thirst (2 hours of 36-second
#: intervals); a reminder every 10.
GOING_WITHOUT = dict(NEEDS_INTERVAL=36, HUNGER_DEATH_HOURS=2, THIRST_DEATH_HOURS=2,
                     NEEDS_REMINDER_TICKS=10, PLAYER_DEATH="respawn")


@pytest.fixture
def starving():
    s = _sim(**GOING_WITHOUT)
    try:
        yield s
    finally:
        s.world.services["combat"].stop_all()
        s.close()


class TestGoingWithout:

    async def test_the_hunger_reminders_escalate(self, starving):
        inn = starving.room("Inn")
        pat = _eater(starving, inn, food=0, home=inn.id)
        heard: dict[int, list[str]] = {}
        for tick in range(1, 201):
            await _needs(starving).tick()
            lines = [line for line in starving.seen(pat) if "hungry" in line.lower()
                     or "famished" in line or "starved" in line.lower()]
            if lines:
                heard[tick] = lines
        assert heard[1] == ["You are hungry."]
        assert 2 not in heard and 10 not in heard
        assert heard[11] == ["You are hungry."]
        assert heard[91] == ["You are hungry."]
        assert heard[101] == ["You are famished! Eat something!"]
        assert heard[151] == ["You are starved! Eat something!"]
        assert heard[161] == ["You are starved! Eat something!"]
        assert all(heard[t] == ["You are starved, and near death. EAT SOMETHING!"]
                   for t in range(171, 201))
        assert pat.db.hungry_ticks == 200

    async def test_the_thirst_lines(self, starving):
        inn = starving.room("Inn")
        marsh = starving.room("Marsh")
        marsh.add_tag("climate:wet")                  # no thirst lost, so food stays put
        pat = _eater(starving, marsh, water=0, home=inn.id)
        seen = []
        for _ in range(199):
            await _needs(starving).tick()
            seen.extend(starving.seen(pat))
        assert seen[0] == "You are thirsty."
        assert "You are parched! Drink something!" in seen
        assert "You are dehydrated! Drink something!" in seen
        assert seen[-1] == "You are dehydrated, and near death. DRINK SOMETHING!"

    async def test_eating_resets_the_count(self, starving):
        pat = _eater(starving, starving.room("Inn"), food=0)
        await _ticks(starving, 5)
        assert pat.db.hungry_ticks == 5
        await settle(mend(pat, "food", 10))
        assert pat.db.get("hungry_ticks") is None
        await _ticks(starving, 1)
        assert pat.db.get("hungry_ticks") is None

    async def test_death_comes_at_the_limit_through_the_death_path(self, starving):
        road = starving.room("Road")
        home = starving.room("Home")
        witness = starving.obj("witness", location=road)
        witness.db.on_death = "incr('deaths')"
        pat = _eater(starving, road, food=0, home=home.id)
        await _ticks(starving, 200)
        assert pat.location is road
        await _ticks(starving, 1)
        assert "YOU ARE DYING OF HUNGER!" in starving.seen(pat)
        assert witness.db.deaths == 1                 # ON_DEATH: the ordinary path
        assert pat.location is home                   # PLAYER_DEATH = respawn
        assert any(o.name == "corpse of Pat" for o in road.contents)
        assert (pat.db.food, pat.db.water) == (500, 1000)   # restored, as CoffeeMud
        assert pat.db.get("hungry_ticks") is None

    async def test_no_death_when_the_setting_is_zero(self):
        sim = _sim(**{**GOING_WITHOUT, "HUNGER_DEATH_HOURS": 0})
        try:
            pat = _eater(sim, sim.room("Inn"), food=0)
            await _ticks(sim, 400)
            seen = sim.seen(pat)
            assert pat.db.hp == 20
            assert "YOU ARE DYING OF HUNGER!" not in seen
            assert set(line for line in seen if "hungry" in line.lower()) == {
                "You are hungry."}
        finally:
            sim.close()

    async def test_hunger_and_thirst_each_halve_regeneration(self, merc):
        vitals = merc.world.services["vitals"]
        pat = _eater(merc, merc.room("Inn"), hp=10, max_hp=200, level=40,
                     constitution=18)
        full = vitals.amount(pat, "hp")
        assert full == 8                              # Merc: (18 - 3 + 20) // 4
        pat.db.food = 0
        assert vitals.amount(pat, "hp") == round(full / 2)
        pat.db.water = 0
        assert vitals.amount(pat, "hp") == 0          # both: no recovery
        pat.db.food = 10
        assert vitals.amount(pat, "hp") == round(full / 2)

    async def test_fatigue_halves_mana_and_movement_only(self, merc):
        vitals = merc.world.services["vitals"]
        pat = _eater(merc, merc.room("Inn"), level=40, intelligence=18, dexterity=18,
                     fatigue=5, max_fatigue=5,
                     pools={"fatigue": {"direction": "up", "regen": False}})
        assert vitals.amount(pat, "mana") == round(((18 + 40) // 4) / 2)
        assert vitals.amount(pat, "move") == round(((18 + 40) // 4) / 2)
        assert vitals.amount(pat, "hp") == (13 - 3 + 20) // 4

    async def test_exhaustion_is_told_at_the_reminder_interval(self, starving):
        pat = starving.player("Pat", location=starving.room("Inn"), fatigue=4,
                              max_fatigue=5,
                              pools={"fatigue": {"direction": "up", "regen": False}})
        seen = []
        for _ in range(12):
            await _needs(starving).tick()
            seen.extend(starving.seen(pat))
        assert seen.count("You are exhausted.") == 2  # ticks 1 and 11 spent

    async def test_hungry_award_scales_experience(self):
        from realm.std.rules.system import award
        sim = _sim(HUNGRY_AWARD=0)
        try:
            pat = _eater(sim, sim.room("Inn"), xp=0)
            assert award(pat, 100) == 100
            assert pat.db.xp == 100
            pat.db.water = 0
            assert award(pat, 100) == 0
            assert pat.db.xp == 100
        finally:
            sim.close()

    async def test_a_kill_pays_through_award(self, merc):
        seen = []
        merc.world.services["rules"].award_filters.append(
            lambda player, amount: seen.append((player.name, amount)) or amount)
        pit = merc.room("Pit")
        pat = _eater(merc, pit, xp=0)
        rat = merc.obj("rat", location=pit, tags=["npc"], hp=1, max_hp=1, points=100)
        await settle(harm(rat, "hp", 5), source=pat)
        assert seen == [("Pat", 200)]                   # 100, doubled at level 1 (ROM)
        assert pat.db.xp == 200


# --- 12.4 eating and drinking ---------------------------------------------------


class TestEatingAndDrinking:

    async def test_a_bite_at_a_time_empties_a_loaf(self, merc):
        pat = _eater(merc, merc.room("Inn"), food=0)
        loaf = merc.obj("a loaf of bread", location=pat, tags=["thing", "food"],
                        nourishment=300, bite=100)
        await merc.do(pat, "eat loaf")
        assert pat.db.food == 100 and loaf.db.nourishment == 200
        seen = merc.seen(pat)
        assert "You take a bite of a loaf of bread." in seen
        assert "You are no longer hungry." in seen
        await merc.do(pat, "eat loaf")
        await merc.do(pat, "eat loaf")
        assert pat.db.food == 300
        assert loaf.location is None and merc.store.get_cached(loaf.id) is None
        assert "You eat a loaf of bread." in merc.seen(pat)

    async def test_without_a_bite_it_is_eaten_whole(self, merc):
        pat = _eater(merc, merc.room("Inn"), food=100)
        merc.obj("a biscuit", location=pat, tags=["thing", "food"], nourishment=80)
        await merc.do(pat, "eat biscuit")
        assert pat.db.food == 180

    async def test_food_gain_scales_a_bite(self):
        sim = _sim(FOOD_GAIN=50)
        try:
            pat = _eater(sim, sim.room("Inn"), food=0)
            sim.obj("a biscuit", location=pat, tags=["thing", "food"], nourishment=80)
            await sim.do(pat, "eat biscuit")
            assert pat.db.food == 40
        finally:
            sim.close()

    async def test_a_full_stomach_refuses_more(self, merc):
        pat = _eater(merc, merc.room("Inn"))
        loaf = merc.obj("a loaf", location=pat, tags=["thing", "food"], nourishment=300)
        await merc.do(pat, "eat loaf")
        assert "You are too full to eat more." in merc.seen(pat)
        assert loaf.location is pat and loaf.db.nourishment == 300

    async def test_eating_to_the_brim_says_so(self, merc):
        pat = _eater(merc, merc.room("Inn"), food=450)
        merc.obj("a loaf", location=pat, tags=["thing", "food"], nourishment=300)
        await merc.do(pat, "eat loaf")
        assert pat.db.food == 500
        assert "You are full." in merc.seen(pat)

    async def test_a_sip_at_a_time(self, merc):
        pat = _eater(merc, merc.room("Inn"), water=0)
        skin = merc.obj("a water skin", location=pat, tags=["thing", "drink"],
                        liquid="water", liquid_held=120, liquid_remaining=120)
        await merc.do(pat, "drink skin")
        assert pat.db.water == 50 and skin.db.liquid_remaining == 70
        seen = merc.seen(pat)
        assert "You drink water from a water skin." in seen
        assert "You are no longer thirsty." in seen
        await merc.do(pat, "drink skin")
        await merc.do(pat, "drink skin")              # the last 20
        assert pat.db.water == 120 and skin.db.liquid_remaining == 0
        merc.seen(pat)
        await merc.do(pat, "drink skin")
        assert "a water skin is empty." in merc.seen(pat)
        assert skin.location is pat                   # a container stays

    async def test_a_container_sets_its_own_sip(self):
        sim = _sim(WATER_GAIN=200)
        try:
            pat = _eater(sim, sim.room("Inn"), water=0)
            sim.obj("a mug", location=pat, tags=["thing", "drink"], liquid="ale",
                    liquid_held=100, liquid_remaining=100, sip=25)
            await sim.do(pat, "drink mug")
            assert pat.db.water == 50                 # 25, doubled by WATER_GAIN
            assert "You drink ale from a mug." in sim.seen(pat)
        finally:
            sim.close()

    async def test_a_fountain_is_not_consumed(self, merc):
        square = merc.room("Square")
        pat = _eater(merc, square, water=0)
        fountain = merc.obj("a fountain", location=square,
                            tags=["thing", "drink", "fountain", "fixed"], liquid="water")
        for _ in range(3):
            await merc.do(pat, "drink fountain")
        assert pat.db.water == 150
        assert fountain.db.get("liquid_remaining") is None
        assert fountain.location is square

    async def test_drink_alone_drinks_from_a_fountain_or_the_water_here(self, merc):
        square = merc.room("Square")
        merc.obj("a fountain", location=square, tags=["thing", "drink", "fountain"],
                 liquid="water")
        river = merc.room("River")
        river.add_tag("water_source")
        pat = _eater(merc, square, water=0)
        await merc.do(pat, "drink")
        assert pat.db.water == 50
        pat.location = river
        await merc.do(pat, "drink")
        assert pat.db.water == 100
        assert "You drink water here." in merc.seen(pat)

    async def test_too_full_to_drink(self, merc):
        pat = _eater(merc, merc.room("Inn"))
        skin = merc.obj("a skin", location=pat, tags=["thing", "drink"], liquid="water",
                        liquid_held=100, liquid_remaining=100)
        await merc.do(pat, "drink skin")
        assert "You are too full to drink more." in merc.seen(pat)
        assert skin.db.liquid_remaining == 100

    async def test_fill_a_container_at_a_fountain(self, merc):
        square = merc.room("Square")
        merc.obj("a fountain", location=square, tags=["thing", "drink", "fountain"],
                 liquid="water")
        pat = _eater(merc, square)
        skin = merc.obj("a water skin", location=pat, tags=["thing", "drink"],
                        liquid="ale", liquid_held=200, liquid_remaining=0)
        await merc.do(pat, "fill skin fountain")
        assert (skin.db.liquid, skin.db.liquid_remaining) == ("water", 200)
        assert "You fill a water skin from a fountain." in merc.seen(pat)
        skin.db.liquid_remaining = 10
        await merc.do(pat, "fill skin")               # the fountain here
        assert skin.db.liquid_remaining == 200
        await merc.do(pat, "fill skin")
        assert "a water skin is already full." in merc.seen(pat)

    async def test_fill_needs_a_source(self, merc):
        pat = _eater(merc, merc.room("Desert"))
        merc.obj("a water skin", location=pat, tags=["thing", "drink"], liquid="water",
                 liquid_held=200, liquid_remaining=0)
        await merc.do(pat, "fill skin")
        assert "There is nothing here to fill it from." in merc.seen(pat)

    def test_fill_keeps_fi_for_first_aid(self, merc):
        dispatcher = merc.dispatcher
        assert dispatcher.get_command("fi").name == "firstaid"
        assert dispatcher._find_prefix_matches("fil") == ["fill"]

    async def test_a_character_without_the_pools_still_eats(self):
        sim = _sim(GURPS)
        try:
            pat = _eater(sim, sim.room("Inn"))
            loaf = sim.obj("a loaf", location=pat, tags=["thing", "food"],
                           nourishment=300, bite=100)
            await sim.do(pat, "eat loaf")
            assert loaf.db.nourishment == 200
            assert pat.db.get("food") is None
        finally:
            sim.close()


# --- 12.5 showing it -----------------------------------------------------------


class TestShowingIt:

    async def test_merc_score_says_hungry_and_thirsty_the_diku_way(self, merc):
        pat = _eater(merc, merc.room("Inn"), food=125, water=251)
        await merc.do(pat, "score")
        sheet = "\n".join(merc.seen(pat))
        assert "You are hungry." in sheet             # a quarter or less
        assert "You are thirsty." not in sheet
        assert "Food" not in sheet and "Water" not in sheet
        assert "HP: 20/20" in sheet

    async def test_the_neutral_sheet_lists_them_as_pools(self):
        from realm.std.rules.system import GameSystem

        class PlainRules(GameSystem):
            """The neutral sheet: the character's pools."""

        sim = _sim(PlainRules)
        try:
            pat = sim.player("Pat", location=sim.room("Inn"), food=10, max_food=500,
                             pools={"food": {"regen": False}})
            await sim.do(pat, "score")
            assert "Food: 10/500" in "\n".join(sim.seen(pat))
        finally:
            sim.close()

    async def test_softcode_hungry_and_thirsty(self, merc):
        inn = merc.room("Inn")
        pat = _eater(merc, inn, food=0)
        sign = merc.obj("sign", location=inn)
        result, err = await merc.eval(sign, "result = [hungry(enactor), thirsty(enactor)]",
                                      enactor=pat)
        assert err is None and result == [True, False]

    async def test_a_gurps_character_is_never_hungry(self):
        sim = _sim(GURPS)
        try:
            inn = sim.room("Inn")
            pat = _eater(sim, inn)
            await _ticks(sim, 50)
            sign = sim.obj("sign", location=inn)
            result, err = await sim.eval(sign, "result = hungry(enactor)", enactor=pat)
            assert err is None and result is False
            assert not sim.seen(pat)
        finally:
            sim.close()


# --- saved worlds -------------------------------------------------------------------


class TestSavedWorlds:
    """Food and drink converted before step 12 (``restores``, ``charges``)
    still work until the area is imported again."""

    async def test_old_food_and_drink_still_work(self, merc):
        square = merc.room("Square")
        pat = _eater(merc, square, food=0, water=0)
        bread = merc.obj("bread", location=pat, tags=["thing", "food"],
                         restores={"food": 18})
        cup = merc.obj("water cup", location=pat, tags=["thing", "drink"],
                       restores={"water": 4}, charges=3)
        merc.obj("fountain water", location=square,
                 tags=["thing", "fountain", "drink"], restores={"water": 4})
        await merc.do(pat, "eat bread")
        assert pat.db.food == 18 and bread.location is None
        await merc.do(pat, "drink cup")
        assert pat.db.water == 4 and cup.db.charges == 2
        await merc.do(pat, "drink fountain")
        assert pat.db.water == 4 + 4 + 50


# --- the ROM import ------------------------------------------------------------------


class TestMidgaard:

    def test_food_drink_and_fountains_carry_the_new_fields(self):
        data = json.loads(MIDGAARD.read_text())
        by_type: dict[str, list[dict]] = {}
        for obj in data["objects"]:
            attrs = obj.get("attrs") or {}
            by_type.setdefault(attrs.get("item_type"), []).append(obj)
        bread = next(o for o in by_type["food"] if o["name"] == "a bread")
        assert bread["attrs"]["nourishment"] == 360           # 18 hours, times 20
        assert "restores" not in bread["attrs"]
        skin = next(o for o in by_type["drink"] if o["name"] == "a buffalo water skin")
        assert skin["attrs"]["liquid"] == "water"
        assert skin["attrs"]["liquid_held"] == skin["attrs"]["liquid_remaining"] == 64 * 30
        assert "charges" not in skin["attrs"] and "restores" not in skin["attrs"]
        fountain = by_type["fountain"][0]
        assert "fountain" in fountain["tags"] and "drink" in fountain["tags"]
        assert fountain["attrs"]["liquid"] == "water"


async def test_report_leaves_the_stomach_out(merc):
    """`report` says what recovers on its own (ROM's hp, mana and move):
    food and water are on `score`, not said aloud."""
    pat = _eater(merc, merc.room("Inn"))
    merc.seen(pat)
    await merc.do(pat, "report")
    said = "\n".join(merc.seen(pat))
    assert "hp" in said and "food" not in said and "water" not in said
