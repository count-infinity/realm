"""
MUD_PLAN step 2.1 and 2.2: the ``vitals`` feature.

Characters regain their pools over time out of combat (the game system
says how much), faster resting and asleep. Positions are tags: ``resting``
and ``sleeping``. A sleeper does not walk, sees nothing, hears nothing from
the room, and answers most input with "You are asleep."
"""

from __future__ import annotations

import pytest

from realm.core.action_tags import HOSTILE
from realm.core.pools import harm, settle
from realm.core.propagation import Action, propagate
from realm.std import CLASSIC
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _vitals(sim):
    return sim.world.services["vitals"]


async def _hurt(sim, obj, amount, pool="hp"):
    await settle(harm(obj, pool, amount))


# --- 2.1 regeneration ------------------------------------------------------------


class TestRegeneration:

    async def test_a_hurt_player_regains_hit_points_and_stops_at_max(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room, hp=10, max_hp=10)
        await _hurt(sim, pat, 3)
        assert pat.db.hp == 7
        await _vitals(sim).tick()
        assert pat.db.hp == 8                      # neutral: max(1, 10 // 20)
        for _ in range(10):
            await _vitals(sim).tick()
        assert pat.db.hp == 10
        assert pat.id not in _vitals(sim).tracked  # full: no longer swept

    async def test_characters_hurt_before_boot_are_found_at_boot(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room, hp=4, max_hp=10)
        rat = sim.obj("rat", location=room, tags=["npc"], hp=1, max_hp=5)
        rock = sim.obj("rock", location=room, hp=1, max_hp=5)
        await sim.boot()
        await _vitals(sim).tick()
        assert (pat.db.hp, rat.db.hp, rock.db.hp) == (5, 2, 1)   # a rock is no character

    async def test_a_fighter_in_combat_does_not_regenerate(self, sim):
        room = sim.room("Pit")
        pat = sim.player("Pat", location=room, hp=10, max_hp=10)
        await _hurt(sim, pat, 5)
        pat.add_tag("in_combat")
        await _vitals(sim).tick()
        assert pat.db.hp == 5
        pat.remove_tag("in_combat")
        await _vitals(sim).tick()
        assert pat.db.hp == 6

    async def test_a_pool_regenerates_only_if_its_spec_allows(self, sim):
        room = sim.room("Dock")
        ship = sim.obj("cutter", location=room, tags=["npc"],
                       shields=20, max_shields=20, hull=30, max_hull=30,
                       damage_pool="shields",
                       pools={"shields": {"overflow": "hull", "regen": False},
                              "hull": {}})
        await _hurt(sim, ship, 25, pool="shields")
        assert (ship.db.shields, ship.db.hull) == (0, 25)
        await _vitals(sim).tick()
        assert ship.db.shields == 0
        assert ship.db.hull == 26

    async def test_an_up_pool_falls_toward_its_floor(self, sim):
        room = sim.room("Lab")
        pat = sim.player("Pat", location=room, stress=0, max_stress=10,
                         pools={"stress": {"direction": "up"}})
        await _hurt(sim, pat, 5, pool="stress")
        await _vitals(sim).tick()
        assert pat.db.stress == 4

    async def test_without_vitals_nothing_regenerates(self):
        sim = Simulator(features=[f for f in CLASSIC if f != "vitals"])
        try:
            assert "vitals" not in sim.world.services
            room = sim.room("Glade")
            pat = sim.player("Pat", location=room, hp=10, max_hp=10)
            await _hurt(sim, pat, 5)
            await sim.boot()
            for reaper in sim.world.reapers:
                await reaper(sim.store)
            assert pat.db.hp == 5
            assert sim.dispatcher.get_command("rest") is None
        finally:
            sim.close()

    async def test_without_rules_the_amount_is_one(self):
        sim = Simulator(features=["basics", "look", "vitals"])
        try:
            room = sim.room("Glade")
            pat = sim.player("Pat", location=room, hp=10, max_hp=200)
            await _hurt(sim, pat, 5)
            await _vitals(sim).tick()
            assert pat.db.hp == 6
        finally:
            sim.close()

    async def test_the_sweep_runs_every_regen_interval(self, sim, monkeypatch):
        clock = [1000.0]
        monkeypatch.setattr("realm.std.vitals.regen.monotonic", lambda: clock[0])
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room, hp=10, max_hp=10)
        await _hurt(sim, pat, 5)
        from realm.std.vitals.regen import regen_sweep as sweep
        await sweep(sim.store)                     # starts the clock
        clock[0] += 14
        await sweep(sim.store)
        assert pat.db.hp == 5
        clock[0] += 1                              # REGEN_INTERVAL (15) has passed
        await sweep(sim.store)
        assert pat.db.hp == 6
        assert sweep in sim.world.reapers

    async def test_other_features_scale_the_amount(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room, hp=200, max_hp=200)
        await _hurt(sim, pat, 100)
        _vitals(sim).multipliers.append(lambda obj, pool: 0.5)
        await _vitals(sim).tick()
        assert pat.db.hp == 105                    # 200 // 20 = 10, halved


class TestMercRegeneration:

    def test_merc_amounts_follow_level_and_stats(self, sim):
        from realm.games.merc import MercSystem
        merc = MercSystem()
        room = sim.room("Square")
        low = sim.player("Low", location=room, level=1, constitution=13,
                         intelligence=13, wisdom=13, dexterity=13,
                         hp=10, max_hp=10, mana=50, max_mana=100, move=50, max_move=100)
        high = sim.player("High", location=room, level=30, constitution=18,
                          intelligence=13, wisdom=18, dexterity=18,
                          hp=10, max_hp=300, mana=50, max_mana=100, move=50, max_move=100)
        assert merc.regen(low, "hp") < merc.regen(high, "hp")
        assert merc.regen(low, "mana") < merc.regen(high, "mana")
        assert merc.regen(low, "move") < merc.regen(high, "move")
        assert min(merc.regen(low, p) for p in ("hp", "mana", "move")) >= 1


# --- 2.2 positions ------------------------------------------------------------------


class TestPositions:

    async def test_rest_sleep_stand_and_their_refusals(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room)
        await sim.do(pat, "stand")
        assert "You are already standing." in sim.seen(pat)
        await sim.do(pat, "rest")
        assert pat.has_tag("resting") and "You sit down and rest." in sim.seen(pat)
        await sim.do(pat, "rest")
        assert "You are already resting." in sim.seen(pat)
        await sim.do(pat, "sleep")
        assert pat.has_tag("sleeping") and not pat.has_tag("resting")
        assert "You lie down and go to sleep." in sim.seen(pat)
        await sim.do(pat, "sleep")
        assert "You are already asleep." in sim.seen(pat)
        await sim.do(pat, "wake")
        assert not pat.has_tag("sleeping") and not pat.has_tag("resting")
        assert "You wake and stand up." in sim.seen(pat)
        await sim.do(pat, "rest")
        await sim.do(pat, "stand")
        assert not pat.has_tag("resting")
        assert "You stand up." in sim.seen(pat)

    async def test_no_resting_in_a_fight(self, sim):
        room = sim.room("Pit")
        pat = sim.player("Pat", location=room)
        pat.add_tag("in_combat")
        await sim.do(pat, "rest")
        await sim.do(pat, "sleep")
        seen = sim.seen(pat)
        assert "You can't rest while fighting!" in seen
        assert "You can't sleep while fighting!" in seen
        assert not pat.has_tag("resting") and not pat.has_tag("sleeping")

    async def test_the_room_sees_the_position_change(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room)
        sam = sim.player("Sam", location=room)
        await sim.do(pat, "rest")
        assert "Pat sits down and rests." in sim.seen(sam)

    async def test_resting_and_sleeping_regenerate_faster(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room, hp=40, max_hp=40)
        await _hurt(sim, pat, 39)
        await _vitals(sim).tick()
        assert pat.db.hp == 3                      # standing: 40 // 20
        pat.add_tag("resting")
        await _vitals(sim).tick()
        assert pat.db.hp == 7                      # REST_REGEN 2
        pat.remove_tag("resting")
        pat.add_tag("sleeping")
        await _vitals(sim).tick()
        assert pat.db.hp == 15                     # SLEEP_REGEN 4

    async def test_moving_while_resting_is_refused(self, sim):
        here = sim.room("Glade")
        there = sim.room("Wood")
        door = sim.obj("north", location=here, tags=["exit"])
        door.db.set("destination", there.id)
        pat = sim.player("Pat", location=here)
        await sim.do(pat, "rest")
        sim.seen(pat)
        await sim.do(pat, "north")
        assert pat.location is here
        assert "You need to stand up first." in sim.seen(pat)
        await sim.do(pat, "stand")
        await sim.do(pat, "north")
        assert pat.location is there

    async def test_an_attack_stands_the_victim(self, sim):
        room = sim.room("Glade")
        wolf = sim.obj("wolf", location=room, tags=["npc"])
        pat = sim.player("Pat", location=room)
        sam = sim.player("Sam", location=room)
        pat.add_tag("sleeping")
        await propagate(Action(actor=wolf, target=pat, action_type="combat:on_attack",
                               tags={HOSTILE}))
        assert not pat.has_tag("sleeping")
        assert any("You are jolted to your feet" in line for line in sim.seen(pat))
        assert "Pat scrambles to their feet." in sim.seen(sam)

    async def test_a_sleeper_is_marked_in_the_room(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room)
        sam = sim.player("Sam", location=room)
        pat.add_tag("sleeping")
        await sim.do(sam, "look")
        assert any("Pat (sleeping)" in line for line in sim.seen(sam))
        pat.remove_tag("sleeping")
        pat.add_tag("resting")
        await sim.do(sam, "look")
        assert any("Pat (resting)" in line for line in sim.seen(sam))


class TestSleeping:

    async def test_a_sleeper_is_answered_you_are_asleep(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room)
        pat.add_tag("sleeping")
        await sim.input(pat, "look")
        assert sim.seen(pat) == ["You are asleep."]
        await sim.input(pat, "score")
        assert sim.seen(pat) != ["You are asleep."]
        await sim.input(pat, "wake")
        assert not pat.has_tag("sleeping")
        await sim.input(pat, "look")
        assert any("Glade" in line for line in sim.seen(pat))

    async def test_a_sleeper_hears_nothing_said_in_the_room(self, sim):
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room)
        sam = sim.player("Sam", location=room)
        pat.add_tag("sleeping")
        await sim.do(sam, "say hello")
        assert not any("hello" in line for line in sim.seen(pat))
        pat.remove_tag("sleeping")
        await sim.do(sam, "say hello")
        assert any("hello" in line for line in sim.seen(pat))

    async def test_a_sleeper_sees_only_themselves(self, sim):
        from realm.core.perception import can_see
        room = sim.room("Glade")
        pat = sim.player("Pat", location=room)
        rock = sim.obj("rock", location=room)
        pat.add_tag("sleeping")
        assert can_see(pat, pat)
        assert not can_see(pat, rock)

    async def test_a_message_addressed_to_the_sleeper_still_arrives(self, sim):
        room = sim.room("Glade")
        sam = sim.player("Sam", location=room)
        pat = sim.player("Pat", location=room)
        pat.add_tag("sleeping")
        action = Action(actor=sam, target=pat, action_type="talk:whisper")
        action.add_message("target", "Sam whispers to you.")
        action.add_message("room", "Sam whispers to Pat.")
        await propagate(action)
        assert "Sam whispers to you." in sim.seen(pat)
