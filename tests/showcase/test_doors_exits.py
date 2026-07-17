"""
Showcase verification — Doors, Exits & Access Control (standalone tutorials).

Items: 26 keycard door, 28 one-way exit, 29 timed door, 30 toll gate,
31 guarded exit, 32 airlock, 33 portal pair, 34 climbing exit,
35 size-restricted crawlspace.

Each tutorial's "Build it" command lines are read straight out of its
markdown (docs/showcase/NNN_*.md) and driven through the real dispatcher
by a builder player — so the tests exercise *exactly* what the docs say
to type, and a doc edit that breaks the build breaks the suite. The
plays then walk the tutorials' "Try it" flows and assert outcomes.

Dice are removed via the pluggable check resolver (same convention as
tests/showcase/test_heist.py): a check succeeds iff effective skill
>= 10, margin = effective - 10, so contests go to the higher skill.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(
        success=effective >= 10,
        margin=effective - 10,
        roll=10,
        effective=effective,
        skill=skill,
    )


# --- Build transcripts: parsed from the tutorials themselves --------------------


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


async def run_lines(sim, player, lines):
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, doc_name: str):
    """Run a tutorial's build transcript as a fresh builder, red-flag scanned."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    await run_lines(sim, builder, build_lines(doc_name))
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"{doc_name} build tripped {flag!r}:\n{out}"
    return builder


def room(sim, name):
    matches = [o for o in sim.store.find_cached(name=name) if o.has_tag("room")]
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def text(sim, player):
    return "\n".join(sim.seen(player))


# --- 26. Keycard door ------------------------------------------------------------


class TestKeycardDoor:

    async def test_access_follows_the_card(self, sim):
        builder = await build(sim, "026_keycard_door.md")
        hallway = room(sim, "Records Hallway")
        lab = room(sim, "The Clean Lab")
        assert builder.location is hallway  # walked out; leaving is free

        ina = sim.player("Ina", location=hallway)
        await sim.do(ina, "security door")
        out = text(sim, ina)
        assert "CLEARANCE 3 REQUIRED" in out
        assert "reads level 0" in out          # numeric refusal, empty-handed
        assert ina.location is hallway

        # A level-1 badge is a credential, just not enough of one.
        await sim.do(builder, "give visitor badge to Ina")
        sim.seen(ina)
        await sim.do(ina, "security door")
        assert "reads level 1" in text(sim, ina)
        assert ina.location is hallway

        # The level-3 card opens the way -- for whoever CARRIES it.
        await sim.do(builder, "give white keycard to Ina")
        sim.seen(ina)
        await sim.do(ina, "security door")
        assert ina.location is lab

        # Leaving is free; hand the card back and access leaves with it.
        await sim.do(ina, "security door")
        assert ina.location is hallway
        await sim.do(ina, "give white keycard to Bob")
        sim.seen(ina)
        await sim.do(ina, "security door")
        assert "reads level 1" in text(sim, ina)
        assert ina.location is hallway

    async def test_ward_gates_softcode_teleports_too(self, sim):
        builder = await build(sim, "026_keycard_door.md")
        hallway = room(sim, "Records Hallway")
        lab = room(sim, "The Clean Lab")
        ina = sim.player("Ina", location=hallway)

        # pre_enter fires for move_to as well as walks: same ward, every way in.
        res, err = await sim.eval(ina, f"move_to(enactor, '#{lab.id}')",
                                  enactor=ina)
        assert err is None
        assert ina.location is hallway
        assert "CLEARANCE 3 REQUIRED" in text(sim, ina)

    async def test_builder_with_card_passes_own_scanner(self, sim):
        builder = await build(sim, "026_keycard_door.md")
        lab = room(sim, "The Clean Lab")
        # Bob still holds the white keycard from the build.
        await sim.do(builder, "security door")
        assert builder.location is lab


# --- 28. One-way exit --------------------------------------------------------------


class TestOneWayExit:

    async def test_chute_drops_and_flavor_layers_on_stock_lines(self, sim):
        builder = await build(sim, "028_one_way_exit.md")
        landing = room(sim, "Upper Landing")
        laundry = room(sim, "The Laundry Vault")
        assert builder.location is laundry   # build ends below

        pat = sim.player("Pat", location=landing)
        await sim.do(pat, "laundry chute")
        out = text(sim, pat)
        assert "The flap snaps shut over your head." in out   # room ON_LEAVE
        assert "You leave laundry chute." in out              # stock line remains
        assert "mountain of linen" in out                     # room ON_ENTER
        assert pat.location is laundry

    async def test_no_way_back_up_but_a_dead_end_that_explains(self, sim):
        builder = await build(sim, "028_one_way_exit.md")
        landing = room(sim, "Upper Landing")
        laundry = room(sim, "The Laundry Vault")
        # The dig created NO return exit: the landing has exactly one exit.
        landing_exits = [o for o in landing.contents if o.has_tag("exit")]
        assert [e.name for e in landing_exits] == ["laundry chute"]

        pat = sim.player("Pat", location=laundry)
        await sim.do(pat, "up")
        out = text(sim, pat)
        assert "greased brass" in out          # the dead end's fail_msg
        assert pat.location is laundry
        # The legitimate way out works.
        await sim.do(pat, "service stair")
        assert pat.location is landing


# --- 29. Timed door ------------------------------------------------------------------


class TestTimedDoor:

    async def test_switch_opens_and_stacked_presses_slam_once(self, sim):
        builder = await build(sim, "029_timed_door.md")
        gen = room(sim, "Generator Room")
        door = obj(sim, "blast door")
        switch = obj(sim, "pressure switch")

        pat = sim.player("Pat", location=gen)
        await sim.do(pat, "blast door")
        assert "sealed" in text(sim, pat)
        assert pat.location is gen

        # Stage the demo: a zero-second countdown (delay is data).
        await run_lines(sim, builder, ["@set pressure switch/delay = 0"])
        sim.seen(builder)

        await sim.do(pat, "press switch")
        assert "grinds open" in text(sim, pat)
        assert not door.has_tag("closed")
        assert switch.db.get("pending") == 1

        # A second press extends -- two countdowns, ONE slam.
        await sim.do(pat, "press switch")
        assert "countdown resets" in text(sim, pat)
        assert switch.db.get("pending") == 2
        await sim.engine.tick_waits()
        out = text(sim, pat)
        assert out.count("WHAM!") == 1
        assert door.has_tag("closed")
        assert switch.db.get("pending") == 0

    async def test_walk_through_the_window_and_the_door_slams_behind(self, sim):
        builder = await build(sim, "029_timed_door.md")
        gen = room(sim, "Generator Room")
        vault = room(sim, "Reactor Vault")
        door = obj(sim, "blast door")
        await run_lines(sim, builder, ["@set pressure switch/delay = 0"])
        sim.seen(builder)

        pat = sim.player("Pat", location=gen)
        await sim.do(pat, "press switch")
        await sim.do(pat, "blast door")
        assert pat.location is vault
        await sim.engine.tick_waits()
        assert door.has_tag("closed")
        # Sealed again from outside...
        late = sim.player("Late", location=gen)
        await sim.do(late, "blast door")
        assert "sealed" in text(sim, late)
        assert late.location is gen
        # ...and the vault has its humble way out.
        await sim.do(pat, "service hatch")
        assert pat.location is gen

    async def test_manual_close_defuses_the_pending_slam(self, sim):
        builder = await build(sim, "029_timed_door.md")
        gen = room(sim, "Generator Room")
        door = obj(sim, "blast door")
        await run_lines(sim, builder, ["@set pressure switch/delay = 0"])
        sim.seen(builder)

        pat = sim.player("Pat", location=gen)
        await sim.do(pat, "press switch")
        await sim.do(pat, "close blast door")   # hand-close mid-window
        sim.seen(pat)
        await sim.engine.tick_waits()
        # The has_tag guard means no double "WHAM!" onto a shut door.
        assert "WHAM!" not in text(sim, pat)
        assert door.has_tag("closed")


# --- 30. Toll gate -------------------------------------------------------------------


class TestTollGate:

    async def test_pay_pass_underpay_refund_and_expiry(self, sim):
        builder = await build(sim, "030_toll_gate.md")
        road = room(sim, "Market Road")
        highway = room(sim, "The King's Highway")
        booth = obj(sim, "toll booth")

        pat = sim.player("Pat", location=road, credits=12)
        await sim.do(pat, "toll gate")
        out = text(sim, pat)
        assert "the toll is 5 credits" in out       # ward quotes the fee
        assert "(pay 5 to toll booth)" in out       # ...and the fix
        assert pat.location is road

        # Underpayment is counted and returned (the refund reads
        # adata('amount') off the payment action).
        await sim.do(pat, "pay 3 to toll booth")
        out = text(sim, pat)
        assert "counts 3 and pushes it back" in out
        assert booth.db.get("credits") == 0
        assert pat.db.get("credits") == 12

        # Full fare: stamped, and the gate opens for a minute.
        await sim.do(pat, "pay 5 to toll booth")
        assert "stamps your wrist" in text(sim, pat)
        assert pat.db.get("credits") == 7
        await sim.do(pat, "toll gate")
        assert pat.location is highway
        # The return face was never tolled.
        await sim.do(pat, "toll gate")
        assert pat.location is road

        # The stamp expires by arithmetic: age it and the gate bars again.
        booth.db.set("pass_" + pat.id, 0)
        sim.seen(pat)
        await sim.do(pat, "toll gate")
        assert "the toll is 5 credits" in text(sim, pat)
        assert pat.location is road

    async def test_the_fare_is_the_payment_not_the_balance(self, sim):
        """The booth reads what THIS payer handed over, not how fat it
        has grown. The till-delta this build retired could not tell the
        difference: it derived the fare from its own balance, so any
        credit movement it didn't witness (a tip, a refill, an admin
        adjustment) was silently credited to the next person to walk up."""
        builder = await build(sim, "030_toll_gate.md")
        road = room(sim, "Market Road")
        booth = obj(sim, "toll booth")

        # Money reaches the booth by a route that is not `pay`.
        await run_lines(
            sim, builder, ["@eval adjust_credits(get('toll booth'), 100)"])
        sim.seen(builder)
        assert booth.db.get("credits") == 100

        pat = sim.player("Pat", location=road, credits=12)
        await sim.do(pat, "pay 3 to toll booth")
        out = text(sim, pat)
        assert "counts 3 and pushes it back" in out     # 3, not 103
        assert "stamps your wrist" not in out
        assert booth.db.get("pass_" + pat.id) is None
        assert booth.db.get("credits") == 100           # refunded in full
        assert pat.db.get("credits") == 12

        # ...and the gate still bars him.
        await sim.do(pat, "toll gate")
        assert "the toll is 5 credits" in text(sim, pat)
        assert pat.location is road

    async def test_only_the_owner_collects_the_till(self, sim):
        builder = await build(sim, "030_toll_gate.md")
        road = room(sim, "Market Road")
        booth = obj(sim, "toll booth")
        pat = sim.player("Pat", location=road, credits=12)
        await run_lines(sim, pat, ["pay 5 to toll booth"])
        sim.seen(pat)

        await sim.do(pat, "collect till")
        assert "not yours to empty" in text(sim, pat)
        assert booth.db.get("credits") == 5

        await run_lines(sim, builder, ["@teleport me = Market Road"])
        sim.seen(builder)
        await sim.do(builder, "collect till")
        assert "You empty the strongbox: 5 credits." in text(sim, builder)
        assert booth.db.get("credits") == 0
        assert builder.db.get("credits") == 5


# --- 31. Guarded exit ----------------------------------------------------------------


class TestGuardedExit:

    async def test_stranger_is_barred_and_the_room_hears_it(self, sim):
        builder = await build(sim, "031_guarded_exit.md")
        gate = room(sim, "Gatehouse")
        mook = sim.player("Mook", location=gate)

        await sim.do(mook, "archway")
        out = text(sim, mook)
        assert "Bruk plants his halberd" in out            # the ward's block
        assert 'Bruk says, "The list is the list. Walk away, Mook."' in out
        assert mook.location is gate                       # ON_FAIL heard aloud

    async def test_guest_list_walks_straight_through(self, sim):
        builder = await build(sim, "031_guarded_exit.md")
        gate = room(sim, "Gatehouse")
        hall = room(sim, "Feast Hall")
        raven = sim.player("Raven", location=gate)
        await sim.do(raven, "archway")
        assert raven.location is hall

    async def test_persuasion_earns_permanent_passage(self, sim):
        builder = await build(sim, "031_guarded_exit.md")
        gate = room(sim, "Gatehouse")
        hall = room(sim, "Feast Hall")
        bruk = obj(sim, "Bruk")

        silver = sim.player("Silver", location=gate, skill_persuasion=14)
        # Deterministic first impression (reaction_roll is memoized): +1.
        bruk.db.set("dispositions", {silver.id: 1})

        await sim.do(silver, "consider Bruk")
        assert "well-disposed" in text(sim, silver)        # friendly, not enough
        await sim.do(silver, "archway")
        sim.seen(silver)
        assert silver.location is gate

        await sim.do(silver, "persuade Bruk")              # 14 vs will 8: +1 -> 2
        assert "nods along" in text(sim, silver)
        await sim.do(silver, "archway")
        assert silver.location is hall

    async def test_fasttalk_cons_a_temporary_welcome(self, sim):
        builder = await build(sim, "031_guarded_exit.md")
        gate = room(sim, "Gatehouse")
        hall = room(sim, "Feast Hall")
        bruk = obj(sim, "Bruk")

        con = sim.player("Con", location=gate, skill_fast_talk=14)
        bruk.db.set("dispositions", {con.id: 0})           # neutral baseline
        await sim.do(con, "fasttalk Bruk")                 # 14 vs detect_lies 8
        assert "buys every word" in text(sim, con)
        await sim.do(con, "archway")
        assert con.location is hall

    async def test_no_guard_no_gate(self, sim):
        builder = await build(sim, "031_guarded_exit.md")
        gate = room(sim, "Gatehouse")
        hall = room(sim, "Feast Hall")
        bruk = obj(sim, "Bruk")
        bruk.location = hall                               # lured off his post

        walkin = sim.player("Walkin", location=gate)
        await sim.do(walkin, "archway")
        assert walkin.location is hall


# --- 32. Airlock ---------------------------------------------------------------------


class TestAirlock:

    async def _built(self, sim):
        builder = await build(sim, "032_airlock.md")
        return (builder, room(sim, "Crew Deck"), room(sim, "Airlock Chamber"),
                room(sim, "Hull Exterior"))

    def _faces(self, sim, name):
        return sim.store.find_cached(name=name)

    async def test_build_ends_sealed_and_mirrored(self, sim):
        builder, deck, chamber, hull = await self._built(sim)
        faces = self._faces(sim, "inner door") + self._faces(sim, "outer door")
        assert len(faces) == 4
        assert all(f.has_tag("closed") for f in faces)

    async def test_interlock_refuses_a_second_open_from_any_side(self, sim):
        builder, deck, chamber, hull = await self._built(sim)

        pat = sim.player("Pat", location=deck)
        await sim.do(pat, "open inner door")     # outer sealed: allowed
        sim.seen(pat)
        await sim.do(pat, "inner door")
        assert pat.location is chamber

        await sim.do(pat, "open outer door")     # invariant holds
        assert "interlock light burns red" in text(sim, pat)
        assert all(f.has_tag("closed") for f in self._faces(sim, "outer door"))

        # ...and holds a room away, on the far face, via the mirror.
        ghost = sim.player("Ghost", location=hull)
        await sim.do(ghost, "open outer door")
        assert "interlock light burns red" in text(sim, ghost)

    async def test_opening_from_the_chamber_does_not_cross_fire(self, sim):
        """The chamber holds a face of BOTH doors, so `open inner door`
        there propagates item:on_open to the outer door face as well.
        Each mirror hook keys on `target == me`, so only the door that
        was actually opened mirrors itself onto its twin. Without that
        guard the outer door's hook runs too and unseals its hull face —
        breaking both the mirror and the airlock's one invariant."""
        builder, deck, chamber, hull = await self._built(sim)
        pat = sim.player("Pat", location=chamber)

        await sim.do(pat, "open inner door")
        # The inner door opened, both faces agreeing...
        assert all(not f.has_tag("closed")
                   for f in self._faces(sim, "inner door"))
        # ...and the outer door is untouched on BOTH sides.
        assert all(f.has_tag("closed")
                   for f in self._faces(sim, "outer door"))

        # The invariant is intact, so the hull side still refuses.
        ghost = sim.player("Ghost", location=hull)
        await sim.do(ghost, "open outer door")
        assert "interlock light burns red" in text(sim, ghost)
        assert ghost.location is hull

    async def test_closing_from_the_chamber_does_not_cross_fire(self, sim):
        """The same guard on the ON_CLOSE side: hand-closing one door
        must not drag the other door's faces shut with it."""
        builder, deck, chamber, hull = await self._built(sim)
        pat = sim.player("Pat", location=chamber)

        await sim.do(pat, "open inner door")
        await sim.do(pat, "close inner door")
        assert all(f.has_tag("closed")
                   for f in self._faces(sim, "inner door"))

        # With the inner door shut, the outer may now open — and its
        # own mirror still reaches its twin.
        await sim.do(pat, "open outer door")
        assert "interlock light burns red" not in text(sim, pat)
        assert all(not f.has_tag("closed")
                   for f in self._faces(sim, "outer door"))
        assert all(f.has_tag("closed")
                   for f in self._faces(sim, "inner door"))

    async def test_cycle_sequence_walks_deck_to_hull_and_back(self, sim):
        builder, deck, chamber, hull = await self._built(sim)
        await run_lines(sim, builder, ["@set airlock panel/cycle_time = 0"])
        sim.seen(builder)

        pat = sim.player("Pat", location=deck)
        await sim.do(pat, "open inner door")
        await sim.do(pat, "inner door")
        assert pat.location is chamber
        sim.seen(pat)

        await sim.do(pat, "cycle out")
        out = text(sim, pat)
        assert "Bolts thud home" in out
        # Mid-cycle: everything sealed (the invariant holds at every instant)
        # and the panel latches out overlapping cycles.
        assert all(f.has_tag("closed") for f in
                   self._faces(sim, "inner door") + self._faces(sim, "outer door"))
        await sim.do(pat, "cycle in")
        assert "pumps are already running" in text(sim, pat)

        await sim.engine.tick_waits()
        out = text(sim, pat)
        assert "outer door unseals" in out
        assert all(not f.has_tag("closed") for f in self._faces(sim, "outer door"))
        assert all(f.has_tag("closed") for f in self._faces(sim, "inner door"))
        await sim.do(pat, "outer door")
        assert pat.location is hull

        # While the outer stands open, the deck-side inner face refuses too.
        dee = sim.player("Dee", location=deck)
        await sim.do(dee, "open inner door")
        assert "interlock light burns red" in text(sim, dee)

        # Cycle back in.
        await sim.do(pat, "outer door")
        assert pat.location is chamber
        await sim.do(pat, "cycle in")
        await sim.engine.tick_waits()
        assert "inner door unseals" in text(sim, pat)
        await sim.do(pat, "inner door")
        assert pat.location is deck

    async def test_bad_cycle_argument_is_coached(self, sim):
        builder, deck, chamber, hull = await self._built(sim)
        pat = sim.player("Pat", location=chamber)
        await sim.do(pat, "cycle sideways")
        assert "CYCLE IN or CYCLE OUT" in text(sim, pat)


# --- 33. Portal pair -----------------------------------------------------------------


class TestPortalPair:

    async def test_two_way_traversal_with_arrival_flavor(self, sim):
        builder = await build(sim, "033_portal_pair.md")
        obs = room(sim, "The Observatory")
        crater = room(sim, "The Shattered Crater")
        assert builder.location is obs           # the build walks the loop

        pat = sim.player("Pat", location=obs)
        await sim.do(pat, "shimmering portal")
        out = text(sim, pat)
        assert pat.location is crater
        assert "ears popping" in out             # crater ON_ENTER
        await sim.do(pat, "shimmering portal")
        out = text(sim, pat)
        assert pat.location is obs
        assert "ears popping" in out             # observatory ON_ENTER

    async def test_collapse_reaps_both_ends_with_narration(self, sim):
        builder = await build(sim, "033_portal_pair.md")
        obs = room(sim, "The Observatory")
        pat = sim.player("Pat", location=obs)
        sim.seen(pat)

        assert len(sim.store.find_cached(name="shimmering portal")) == 2
        reaped = await reap_expired(sim.store, now=time.time() + 300)
        assert reaped == 2
        assert sim.store.find_cached(name="shimmering portal") == []
        assert "snaps shut with a thunderclap" in text(sim, pat)

        # The map healed: no half-link survives, no exit to walk.
        await sim.do(pat, "shimmering portal")
        assert pat.location is obs


# --- 34. Climbing exit ---------------------------------------------------------------


class TestClimbingExit:

    async def test_skilled_climber_goes_up_and_down(self, sim):
        builder = await build(sim, "034_climbing_exit.md")
        floor = room(sim, "Gully Floor")
        ledge = room(sim, "Eagle Ledge")

        goat = sim.player("Goat", location=floor,
                          skill_climbing=14, hp=13, max_hp=13)
        await sim.do(goat, "rock chimney")       # 14 - 2 = 12 >= 10
        assert goat.location is ledge
        await sim.do(goat, "rock chimney")       # descent at -0
        assert goat.location is floor
        assert goat.db.get("hp") == 13           # never a scratch

    async def test_failed_climb_costs_a_fall(self, sim):
        builder = await build(sim, "034_climbing_exit.md")
        floor = room(sim, "Gully Floor")
        scholar = sim.player("Scholar", location=floor,
                             skill_climbing=8, hp=13, max_hp=13)
        witness = sim.player("Witness", location=floor)
        sim.seen(witness)

        await sim.do(scholar, "rock chimney")    # 8 - 2 = 6 < 10
        out = text(sim, scholar)
        assert "a hold crumbles under your fingers" in out
        assert "You land hard in the scree" in out       # exit ON_FAIL
        assert scholar.location is floor                 # refused BEFORE moving
        assert scholar.db.get("hp") < 13                 # 1d6 landed
        assert "Scholar tries to go rock chimney and fails." in text(sim, witness)

    async def test_descent_is_its_own_easier_roll(self, sim):
        builder = await build(sim, "034_climbing_exit.md")
        floor = room(sim, "Gully Floor")
        ledge = room(sim, "Eagle Ledge")

        # Climbing 11 fails the way up (11-2=9) but manages the way down (11-0).
        slick = sim.player("Slick", location=ledge,
                           skill_climbing=11, hp=13, max_hp=13)
        await sim.do(slick, "rock chimney")
        assert slick.location is floor
        assert slick.db.get("hp") == 13
        sim.seen(slick)
        await sim.do(slick, "rock chimney")
        out = text(sim, slick)
        assert "a hold crumbles under your fingers" in out
        assert slick.location is floor
        assert slick.db.get("hp") < 13


# --- 35. Size-restricted crawlspace ----------------------------------------------------


class TestCrawlspace:

    async def test_overloaded_refusal_quotes_the_numbers(self, sim):
        builder = await build(sim, "035_crawlspace.md")
        cellar = room(sim, "Dusty Cellar")
        nook = room(sim, "Smugglers' Nook")

        pat = sim.player("Pat", location=cellar)
        for crate_name in ("iron crate", "oak crate"):
            crate = sim.obj(crate_name, location=pat, tags=["thing"])
            crate.db.set("weight", 3)

        await sim.do(pat, "narrow crawlspace")
        out = text(sim, pat)
        assert "6 lbs of bulk against a 5 lb squeeze" in out
        assert pat.location is cellar

        await sim.do(pat, "drop iron crate")
        sim.seen(pat)
        await sim.do(pat, "narrow crawlspace")   # 3 lbs slides through
        assert pat.location is nook

    async def test_the_loot_does_not_fit_back_out(self, sim):
        builder = await build(sim, "035_crawlspace.md")
        cellar = room(sim, "Dusty Cellar")
        nook = room(sim, "Smugglers' Nook")

        pat = sim.player("Pat", location=cellar)
        crate = sim.obj("oak crate", location=pat, tags=["thing"])
        crate.db.set("weight", 3)
        await sim.do(pat, "narrow crawlspace")
        assert pat.location is nook
        sim.seen(pat)

        await sim.do(pat, "get strongbox")       # the 9-lb prize (built stock)
        assert obj(sim, "strongbox").location is pat
        await sim.do(pat, "narrow crawlspace")   # 3 + 9 = 12 against 5
        out = text(sim, pat)
        assert "12 lbs of bulk against a 5 lb squeeze" in out
        assert pat.location is nook

        # Shed everything and the wriggle out is free.
        await sim.do(pat, "drop strongbox")
        await sim.do(pat, "drop oak crate")
        sim.seen(pat)
        await sim.do(pat, "narrow crawlspace")
        assert pat.location is cellar
