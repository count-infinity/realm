"""
Showcase verification — Time, Scheduling & Automation (items 144-153).

Items: 144 game calendar & clock, 145 scheduled world events, 146 item
decay (batch sweeper), 147 zone repop, 148 delayed actions, 149
maintenance sweeper, 150 global countdown events, 151 business hours,
152 reboot-surviving timers, 153 time scaling.

Every command line in each tutorial's "Build it" section is read
straight out of its markdown (docs/showcase/NNN_*.md) and driven through
the real dispatcher (raw input in -> session output out) by a builder
player — the doc IS the test input, so a tutorial edit that breaks the
build breaks this suite. The plays then exercise the tutorials' "Try it"
flows and assert outcomes.

Time is virtual throughout: script_ticker heartbeats are advanced by
hand (one tick() call fires an interval:1 on_tick once), wait() fuses
fire on tick_waits() pumps (the Simulator defers waits to a virtual
clock), expire() lifetimes are reaped with a forged clock, and the
zone_reset behavior is driven directly like tests/test_zone_reset.py.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401  (registers zone_reset / script_ticker)
from realm.core.events import reap_expired
from realm.testing import Simulator


# --- Build transcripts: read straight out of the tutorials ----------------------

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_FILES = {
    144: "144_game_calendar.md",
    145: "145_scheduled_events.md",
    146: "146_item_decay.md",
    147: "147_zone_repop.md",
    148: "148_delayed_actions.md",
    149: "149_maintenance_sweeper.md",
    150: "150_countdown_events.md",
    151: "151_business_hours.md",
    152: "152_persistent_timers.md",
    153: "153_time_scaling.md",
}


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text(encoding="utf-8")
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    # GameServer wires the session manager at startup; the Simulator
    # leaves it to the test (some builtins consult it).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    simulator.close()


async def build(sim, item: int):
    """Run a tutorial's "Build it" transcript — read from its markdown — as a
    builder standing in Limbo. The doc IS the test input: an edit that breaks
    the build breaks this suite."""
    doc_name = DOC_FILES[item]
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    for line in build_lines(doc_name):
        await sim.do(builder, line)
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


def objs(sim, name):
    return sim.store.find_cached(name=name)


def text(sim, player):
    return "\n".join(sim.seen(player))


async def tick(obj, times=1):
    """Advance every should_tick behavior on obj once per call (an
    interval:1 script_ticker fires its on_tick exactly once per tick())."""
    for _ in range(times):
        for behavior in list(obj.get_behaviors()):
            await behavior.tick(obj, 4.0)


# --- 144. Game calendar & clock -------------------------------------------------


class TestGameCalendar:

    async def test_tick_advances_and_time_renders_a_scifi_date(self, sim):
        await build(sim, 144)
        deck = room(sim, "Observation Deck")
        chrono = obj(sim, "ship chronometer")
        zara = sim.player("Zara", location=deck)

        assert chrono.db.get("game_min") == 0
        await tick(chrono)                      # +step (30)
        assert chrono.db.get("game_min") == 30

        await sim.do(zara, "date")
        assert "CS 812.01.01 // 00:30 -- month of Ignis." in text(sim, zara)

    async def test_derived_fields_divide_out_of_one_counter(self, sim):
        builder = await build(sim, 144)
        deck = room(sim, "Observation Deck")
        zara = sim.player("Zara", location=deck)

        # 2 months + 13 days + 17h + 42m past year zero.
        await sim.do(builder, "@set ship chronometer/game_min = 88662")
        await sim.do(zara, "date")
        assert "CS 812.03.14 // 17:42 -- month of Terra." in text(sim, zara)


# --- 145. Scheduled world events ------------------------------------------------


class TestScheduledEvents:

    async def test_daily_timetable_fires_once_per_hour_zone_wide(self, sim):
        await build(sim, 145)
        command = room(sim, "Command Deck")
        hydro = room(sim, "Hydro Bay")
        clock = obj(sim, "colony clock")
        ai = obj(sim, "Colony AI")
        deckhand = sim.player("Deckhand", location=command)
        botanist = sim.player("Botanist", location=hydro)

        # Hour 5 -> 6: the dawn klaxon reaches BOTH colony rooms.
        await tick(clock)
        await tick(ai)
        assert "A dawn klaxon echoes through the colony." in text(sim, deckhand)
        assert "A dawn klaxon echoes through the colony." in text(sim, botanist)

        # Same hour again: dedup — no second klaxon.
        sim.seen(deckhand)
        await tick(ai)
        assert "dawn klaxon" not in text(sim, deckhand)

        # Hour 6 -> 7: nothing is scheduled.
        await tick(clock)
        await tick(ai)
        assert "klaxon" not in text(sim, deckhand)

        # Roll on to hour 12 (7->12): the mess call goes out.
        await tick(clock, 5)
        await tick(ai)
        assert "Midday rations are served in the mess." in text(sim, deckhand)
        assert "Midday rations are served in the mess." in text(sim, botanist)

    async def test_outside_the_zone_hears_nothing(self, sim):
        await build(sim, 145)
        clock = obj(sim, "colony clock")
        ai = obj(sim, "Colony AI")
        outsider = sim.player("Outsider", location=room(sim, "Limbo"))

        await tick(clock)     # -> hour 6
        await tick(ai)
        assert "klaxon" not in text(sim, outsider)


# --- 146. Item decay (batch sweeper) --------------------------------------------


class TestItemDecay:

    async def test_one_sweeper_rots_many_items_on_a_shared_clock(self, sim):
        await build(sim, 146)
        hold = room(sim, "Cargo Hold")
        sweeper = obj(sim, "pantry sweeper")
        hauler = sim.player("Hauler", location=hold)

        # Two sweeps: shelves burn down, nothing spoils yet.
        await tick(sweeper, 2)
        assert obj(sim, "crate of rations").db.get("shelf") == 1
        assert obj(sim, "field medkit").db.get("shelf") == 3

        # Third sweep: the crate (shelf 3) hits zero and becomes sludge;
        # the medkit (shelf 5) rides on.
        await tick(sweeper)
        assert "The crate of rations has spoiled into reeking sludge." in text(sim, hauler)
        assert objs(sim, "crate of rations") == []
        assert objs(sim, "a puddle of sludge")
        assert obj(sim, "field medkit").db.get("shelf") == 2

    async def test_items_carry_no_behavior_of_their_own(self, sim):
        await build(sim, 146)
        crate = obj(sim, "crate of rations")
        assert crate.get_behaviors() == []      # pure data; the sweeper owns the clock


# --- 147. Zone repop ------------------------------------------------------------


def _drones(bridge):
    return [o for o in bridge.contents if o.name == "a maintenance drone"]


def _zone_reset(master):
    return [b for b in master.get_behaviors() if b.behavior_id == "zone_reset"][0]


class TestZoneRepop:

    async def test_repops_the_empty_zone_and_fires_on_reset(self, sim):
        builder = await build(sim, 147)
        bridge = room(sim, "Derelict Bridge")
        master = obj(sim, "Bridge Systems")
        await sim.do(builder, "out")            # clear the zone

        master.db.set("last_reset", 0)          # long overdue
        await _zone_reset(master).tick(master, 4.0)
        assert len(_drones(bridge)) == 2
        assert master.db.get("cycles") == 1     # ON_RESET ran

    async def test_presence_gate_defers_while_a_player_is_aboard(self, sim):
        builder = await build(sim, 147)
        bridge = room(sim, "Derelict Bridge")
        master = obj(sim, "Bridge Systems")
        sim.player("Straggler", location=bridge)   # someone's watching

        master.db.set("last_reset", 0)
        await _zone_reset(master).tick(master, 4.0)
        assert _drones(bridge) == []               # no pop on top of a player
        assert float(master.db.get("last_reset")) == 0   # not bumped; will retry

    async def test_repop_command_is_owner_only_and_queues_a_reset(self, sim):
        builder = await build(sim, 147)
        bridge = room(sim, "Derelict Bridge")
        master = obj(sim, "Bridge Systems")
        intruder = sim.player("Intruder", location=bridge)

        await sim.do(intruder, "repop")
        assert "Command authority required." in text(sim, intruder)

        await sim.do(builder, "repop")             # owner, standing in the bridge
        assert "Reset queued" in text(sim, builder)
        assert float(master.db.get("last_reset")) == 0

        # While anyone remains aboard, the gate defers.
        await sim.do(builder, "out")
        await _zone_reset(master).tick(master, 4.0)
        assert _drones(bridge) == []               # intruder still watching

        # It fires the instant the bridge clears.
        await sim.do(intruder, "out")
        await _zone_reset(master).tick(master, 4.0)
        assert len(_drones(bridge)) == 2


# --- 148. Delayed actions -------------------------------------------------------


class TestDelayedActions:

    async def test_wait_chain_rings_three_peals_in_order(self, sim):
        builder = await build(sim, 148)
        chamber = room(sim, "Ritual Chamber")
        bell = obj(sim, "ceremony bell")
        pip = sim.player("Pip", location=chamber)
        # Zero the pause so the deferred waits are due on each tick_waits()
        # pump (the same trick 056 uses with interval:0 — virtual clock).
        await sim.do(builder, "@set ceremony bell/gap = 0")

        await sim.do(pip, "ring bell")
        assert "The bell rings once." in text(sim, pip)
        assert bell.db.get("pending")

        await sim.engine.tick_waits()
        assert "The bell rings twice." in text(sim, pip)
        await sim.engine.tick_waits()
        assert "The bell rings a third and final time." in text(sim, pip)
        assert bell.db.get("pending") is None   # chain finished

    async def test_a_running_ceremony_refuses_a_second(self, sim):
        await build(sim, 148)
        chamber = room(sim, "Ritual Chamber")
        pip = sim.player("Pip", location=chamber)

        await sim.do(pip, "ring bell")
        sim.seen(pip)
        await sim.do(pip, "ring bell")
        assert "A ceremony is already underway." in text(sim, pip)

    async def test_silence_cancels_the_pending_timer(self, sim):
        await build(sim, 148)
        chamber = room(sim, "Ritual Chamber")
        bell = obj(sim, "ceremony bell")
        pip = sim.player("Pip", location=chamber)

        await sim.do(pip, "ring bell")
        await sim.do(pip, "silence bell")
        assert "The bell is stilled mid-peal." in text(sim, pip)
        assert bell.db.get("pending") is None

        # The cancelled chain never rings again.
        sim.seen(pip)
        await sim.engine.tick_waits()
        assert "rings twice" not in text(sim, pip)

        # And with nothing pending, silence reports the dead panel.
        await sim.do(pip, "silence bell")
        assert "Nothing is ringing." in text(sim, pip)


# --- 149. Maintenance sweeper ---------------------------------------------------


class TestMaintenanceSweeper:

    async def test_dry_run_previews_then_confirm_commits(self, sim):
        await build(sim, 149)
        prom = room(sim, "Promenade")
        janitor = sim.player("Custodian", location=prom)

        await sim.do(janitor, "sweep")
        out = text(sim, janitor)
        assert "DRY RUN -- would remove 2:" in out
        assert "discarded wrapper" in out and "broken bottle" in out
        # Preview changed nothing.
        assert objs(sim, "discarded wrapper") and objs(sim, "broken bottle")

        await sim.do(janitor, "sweep confirm")
        assert "collecting 2 items" in text(sim, janitor)
        assert objs(sim, "discarded wrapper") == []
        assert objs(sim, "broken bottle") == []
        assert objs(sim, "janitor bot")         # untagged: never in danger

        await sim.do(janitor, "sweep")
        assert "The promenade is spotless." in text(sim, janitor)


# --- 150. Global countdown events -----------------------------------------------


class TestGlobalCountdown:

    async def test_countdown_broadcasts_server_wide_then_fires(self, sim):
        builder = await build(sim, 150)
        plaza = room(sim, "Plaza")
        docks = room(sim, "Docks")
        herald = obj(sim, "Event Herald")
        at_plaza = sim.player("Ada", location=plaza)
        at_docks = sim.player("Dex", location=docks)
        await sim.do(builder, "@set Event Herald/gap = 0")   # virtual-clock pumps

        await sim.do(builder, "countdown 3 for the Convergence")
        assert "STATION ANNOUNCEMENT: the Convergence in 3 minutes." in text(sim, at_plaza)
        assert "the Convergence in 3 minutes." in text(sim, at_docks)
        assert herald.db.get("pending")

        await sim.engine.tick_waits()
        assert "the Convergence in 2 minutes." in text(sim, at_docks)
        await sim.engine.tick_waits()
        assert "the Convergence in 1 minutes." in text(sim, at_docks)
        await sim.engine.tick_waits()
        assert "the Convergence begins NOW!" in text(sim, at_plaza)
        assert "the Convergence begins NOW!" in text(sim, at_docks)
        assert herald.db.get("pending") is None

    async def test_non_owner_is_refused_and_scrub_calls_it_off(self, sim):
        builder = await build(sim, 150)
        docks = room(sim, "Docks")
        herald = obj(sim, "Event Herald")
        mara = sim.player("Mara", location=docks)

        await sim.do(mara, "countdown 2 for Trouble")
        assert "Command authority required." in text(sim, mara)
        assert herald.db.get("pending") is None

        await sim.do(builder, "countdown 5 for the Eclipse")
        assert herald.db.get("pending")
        await sim.do(builder, "scrub countdown")
        assert "the Eclipse has been called off." in text(sim, mara)
        assert herald.db.get("pending") is None

        # Nothing fires after a scrub.
        sim.seen(mara)
        await sim.engine.tick_waits()
        assert "begins NOW" not in text(sim, mara)


# --- 151. Business hours --------------------------------------------------------


class TestBusinessHours:

    async def test_terminal_opens_and_closes_on_the_clock(self, sim):
        await build(sim, 151)
        annex = room(sim, "Trade Annex")
        clock = obj(sim, "market clock")
        terminal = obj(sim, "trade terminal")
        shopper = sim.player("Shopper", location=annex)

        # 08:00, seeded closed.
        await sim.do(shopper, "access terminal")
        assert "The screen is dark. Trade hours are 9:00 to 17:00." in text(sim, shopper)

        # Roll to opening (08->09) and let the terminal re-read.
        await tick(clock)
        await tick(terminal)
        assert terminal.db.get("open") == 1
        await sim.do(shopper, "access terminal")
        assert "ACCESS GRANTED. The markets are live" in text(sim, shopper)

        # Roll to close (09->17): the next terminal tick shuts it.
        await tick(clock, 8)
        await tick(terminal)
        assert terminal.db.get("open") == 0
        await sim.do(shopper, "access terminal")
        assert "The screen is dark." in text(sim, shopper)

    async def test_desc_reads_the_stamped_flag(self, sim):
        await build(sim, 151)
        annex = room(sim, "Trade Annex")
        clock = obj(sim, "market clock")
        terminal = obj(sim, "trade terminal")
        shopper = sim.player("Shopper", location=annex)

        await sim.do(shopper, "look trade terminal")
        assert "A red CLOSED light glows" in text(sim, shopper)

        await tick(clock)
        await tick(terminal)
        sim.seen(shopper)
        await sim.do(shopper, "look trade terminal")
        assert "A green OPEN light glows steadily." in text(sim, shopper)


# --- 152. Reboot-surviving timers -----------------------------------------------


class TestPersistentTimers:

    async def test_expire_timer_rings_survives_and_is_reusable(self, sim):
        await build(sim, 152)
        galley = room(sim, "Galley")
        egg = obj(sim, "egg timer")
        cook = sim.player("Rue", location=galley)

        await sim.do(cook, "set timer 5")
        assert "The timer winds up with a ratchet" in text(sim, cook)
        # Both clocks are persisted attributes on the object.
        assert egg.db.get("expires_at")
        assert egg.db.get("rings_at")

        await sim.do(cook, "check timer")
        out = text(sim, cook)
        assert ("300 seconds remain." in out or "299 seconds remain." in out)

        # Forge the clock past the deadline: the housekeeping task rings it.
        reaped = await reap_expired(sim.store, now=time.time() + 301)
        assert "BRRRING! The egg timer goes off" in text(sim, cook)
        # It cleared its own deadline, so the reaper did NOT destroy it.
        assert reaped == 0
        assert objs(sim, "egg timer")
        assert egg.db.get("expires_at") is None
        assert egg.db.get("rings_at") is None

        await sim.do(cook, "check timer")
        assert "The timer is not set." in text(sim, cook)

        # ...and it winds again — reusable.
        await sim.do(cook, "set timer 5")
        assert egg.db.get("expires_at")

    async def test_non_numeric_input_is_refused(self, sim):
        await build(sim, 152)
        galley = room(sim, "Galley")
        egg = obj(sim, "egg timer")
        cook = sim.player("Rue", location=galley)

        await sim.do(cook, "set timer soon")
        assert "Give it whole minutes." in text(sim, cook)
        assert egg.db.get("expires_at") is None


# --- 153. Time scaling ----------------------------------------------------------


class TestTimeScaling:

    async def test_rate_dial_scales_game_time_advance(self, sim):
        await build(sim, 153)
        lab = room(sim, "Chronometry Lab")
        chrono = obj(sim, "master chronometer")
        tim = sim.player("Tim", location=lab)

        # Default rate: one tick is half a game-hour.
        await tick(chrono)
        assert chrono.db.get("game_min") == 30
        await sim.do(tim, "clock")
        assert "Day 1, 00:30" in text(sim, tim)

        # Turn the dial up 4x: the same tick covers two game-hours.
        await sim.do(tim, "set rate 120")
        assert "Time now advances 120 game-minutes per world tick." in text(sim, tim)
        assert chrono.db.get("step") == 120
        await tick(chrono)
        assert chrono.db.get("game_min") == 150
        await sim.do(tim, "clock")
        assert "Day 1, 02:30" in text(sim, tim)

    async def test_rate_zero_freezes_the_calendar(self, sim):
        await build(sim, 153)
        lab = room(sim, "Chronometry Lab")
        chrono = obj(sim, "master chronometer")
        tim = sim.player("Tim", location=lab)

        await sim.do(tim, "set rate 0")
        await tick(chrono, 3)
        assert chrono.db.get("game_min") == 0   # paused, server still running
