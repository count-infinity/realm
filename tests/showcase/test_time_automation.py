"""
Showcase verification — Time, Scheduling & Automation (items 144-153).

Items: 144 game calendar & clock, 145 scheduled world events, 146 item
decay (batch sweeper), 147 zone repop, 148 delayed actions, 149
maintenance sweeper, 150 global countdown events, 151 business hours,
152 reboot-surviving timers, 153 time scaling.

Every command line in each tutorial's "Build it" section is driven
through the real dispatcher (raw input in -> session output out) by a
builder player, exactly as typed in the docs; the plays then exercise
the tutorials' "Try it" flows and assert outcomes.

Time is virtual throughout: script_ticker heartbeats are advanced by
hand (one tick() call fires an interval:1 on_tick once), wait() fuses
fire on tick_waits() pumps (the Simulator defers waits to a virtual
clock), expire() lifetimes are reaped with a forged clock, and the
zone_reset behavior is driven directly like tests/test_zone_reset.py.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401  (registers zone_reset / script_ticker)
from realm.core.events import reap_expired
from realm.testing import Simulator


# --- Build transcripts (the tutorials' exact "Build it" lines) -----------------

# docs/showcase/144_game_calendar.md
BUILD_144 = [
    "@dig Observation Deck = obdeck, out",
    "obdeck",
    "@create ship chronometer",
    "drop ship chronometer",
    "@set ship chronometer/game_min = 0",
    "@set ship chronometer/step = 30",
    "@set ship chronometer/epoch_year = 812",
    '@set ship chronometer/months = ["Ignis", "Ventus", "Terra", "Aqua", "Lumen", "Umbra", "Ferro", "Nix", "Sol", "Void"]',
    "@set ship chronometer/on_tick = incr('game_min', V('step', 30))",
    "@behavior ship chronometer = script_ticker, interval:1",
    """@set ship chronometer/cmd_date = $date: m = V('game_min', 0); mo = V('months', []); minute = m % 60; hour = (m // 60) % 20; day = (m // 1200) % 30 + 1; month = (m // 36000) % 10; year = V('epoch_year', 0) + m // 360000; pemit(enactor, f'CS {year}.{right("0" + str(month + 1), 2)}.{right("0" + str(day), 2)} // {right("0" + str(hour), 2)}:{right("0" + str(minute), 2)} -- month of {mo[month] if mo else "?"}.')""",
]

# docs/showcase/145_scheduled_events.md
BUILD_145 = [
    "@dig Command Deck = deck, out",
    "deck",
    "@zone here = colony",
    "@dig Hydro Bay = hydro, deck",
    "hydro",
    "@zone here = colony",
    "deck",
    "@create colony clock",
    "drop colony clock",
    "@set colony clock/hour = 5",
    "@set colony clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)",
    "@behavior colony clock = script_ticker, interval:1",
    "@create Colony AI",
    "drop Colony AI",
    "@zone/master Colony AI = colony",
    '@set Colony AI/schedule = [{"hour": 6, "msg": "A dawn klaxon echoes through the colony. Day cycle begins."}, {"hour": 12, "msg": "Midday rations are served in the mess."}, {"hour": 18, "msg": "Dusk. The corridor lights fade to amber."}]',
    "@set Colony AI/on_tick = h = get_attr('colony clock', 'hour', 0); [(act(me, e['msg'], targeting='zone'), set_attr(me, 'fired_' + str(i), h)) for i, e in enumerate(V('schedule', [])) if e['hour'] == h and V('fired_' + str(i), -1) != h]",
    "@behavior Colony AI = script_ticker, interval:1",
]

# docs/showcase/146_item_decay.md
BUILD_146 = [
    "@dig Cargo Hold = hold, out",
    "hold",
    "@create crate of rations",
    "@tag crate of rations = perishable",
    "@set crate of rations/shelf = 3",
    "drop crate of rations",
    "@create field medkit",
    "@tag field medkit = perishable",
    "@set field medkit/shelf = 5",
    "drop field medkit",
    "@create pantry sweeper",
    "drop pantry sweeper",
    "@set pantry sweeper/sweep = [(set_attr(o, 'shelf', get_attr(o, 'shelf', 0) - 1), (remit(loc(o), 'The ' + name(o) + ' has spoiled into reeking sludge.'), create_obj('a puddle of sludge', ['thing'], loc(o)), destroy_obj(o)) if get_attr(o, 'shelf', 0) <= 0 else None) for o in search_world(tag='perishable')]",
    "@set pantry sweeper/on_tick = eval_attr(me, 'sweep')",
    "@behavior pantry sweeper = script_ticker, interval:1",
]

# docs/showcase/147_zone_repop.md
BUILD_147 = [
    "@dig Derelict Bridge = bridge, out",
    "bridge",
    "@zone here = derelict",
    "@tag here = dronebay",
    "@create Bridge Systems",
    "drop Bridge Systems",
    "@zone/master Bridge Systems = derelict",
    "@set Bridge Systems/reset_interval = 300",
    '@set Bridge Systems/reset_spec = [{"prototype": {"name": "a maintenance drone", "tags": ["npc"]}, "room": "dronebay", "count": 2}]',
    "@set Bridge Systems/on_reset = incr('cycles'); remit('Derelict Bridge', 'Dormant systems cycle: consoles relight, the drone bay reseeds.')",
    "@behavior Bridge Systems = zone_reset",
    "@set Bridge Systems/cmd_repop = $repop: pemit(enactor, 'Command authority required.') if enactor != owner(me) else (set_attr(me, 'last_reset', 0), pemit(enactor, 'Reset queued -- it fires the instant the bridge is clear.'))",
]

# docs/showcase/148_delayed_actions.md
BUILD_148 = [
    "@dig Ritual Chamber = ritual, out",
    "ritual",
    "@create ceremony bell",
    "drop ceremony bell",
    "@desc ceremony bell = A tall bronze bell on a rope. RING BELL begins the rite; SILENCE BELL stops it.",
    "@set ceremony bell/gap = 2",
    "@set ceremony bell/step_1 = remit(loc(me), 'The bell rings once. A hush falls over the chamber.'); set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/step_2'))",
    "@set ceremony bell/step_2 = remit(loc(me), 'The bell rings twice. The candles gutter.'); set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/step_3'))",
    "@set ceremony bell/step_3 = remit(loc(me), 'The bell rings a third and final time. It is done.'); del_attr(me, 'pending')",
    "@set ceremony bell/cmd_begin = $ring bell: pemit(enactor, 'A ceremony is already underway.') if V('pending') else eval_attr(me, 'step_1')",
    "@set ceremony bell/cmd_silence = $silence bell: (cancel_wait(V('pending')), del_attr(me, 'pending'), remit(loc(me), 'The bell is stilled mid-peal.')) if V('pending') else pemit(enactor, 'Nothing is ringing.')",
]

# docs/showcase/149_maintenance_sweeper.md
BUILD_149 = [
    "@dig Promenade = prom, out",
    "prom",
    "@create discarded wrapper",
    "@tag discarded wrapper = litter",
    "drop discarded wrapper",
    "@create broken bottle",
    "@tag broken bottle = litter",
    "drop broken bottle",
    "@create janitor bot",
    "drop janitor bot",
    "@desc janitor bot = A squat cleaning drone, brushes folded. SWEEP to preview a cleanup, SWEEP CONFIRM to run it.",
    "@set janitor bot/cmd_sweep = $sweep: junk = search_world(tag='litter'); pemit(enactor, 'The promenade is spotless.') if not junk else pemit(enactor, 'DRY RUN -- would remove ' + str(len(junk)) + ': ' + ', '.join([name(o) for o in junk]) + '. Type SWEEP CONFIRM to run it.')",
    "@set janitor bot/cmd_sweep_confirm = $sweep confirm: junk = search_world(tag='litter'); (pemit(enactor, 'Nothing to sweep.') if not junk else ([destroy_obj(o) for o in junk], remit(loc(me), 'The janitor bot hums through, collecting ' + str(len(junk)) + ' items, and trundles off.')))",
]

# docs/showcase/150_countdown_events.md
BUILD_150 = [
    "@dig Plaza = plaza, out",
    "plaza",
    "@zone here = world",
    "@dig Docks = docks, plaza",
    "docks",
    "@zone here = world",
    "plaza",
    "@create Event Herald",
    "drop Event Herald",
    "@zone/master Event Herald = world",
    "@set Event Herald/banner = STATION ANNOUNCEMENT",
    "@set Event Herald/gap = 2",
    "@set Event Herald/announce = [remit(r, V('banner', 'ATTENTION') + ': ' + V('label', 'an event') + ' in ' + str(V('remaining', 0)) + ' minutes.') for r in search_world(tag='room')]",
    "@set Event Herald/tick = n = V('remaining', 0); (eval_attr(me, 'fire') if n <= 0 else (eval_attr(me, 'announce'), decr('remaining'), set_attr(me, 'pending', wait(V('gap', 2), 'trigger me/tick'))))",
    "@set Event Herald/fire = del_attr(me, 'pending'); del_attr(me, 'remaining'); [remit(r, V('label', 'the event') + ' begins NOW!') for r in search_world(tag='room')]",
    "@set Event Herald/cmd_countdown = $countdown * for *: pemit(enactor, 'Command authority required.') if enactor != owner(me) else (pemit(enactor, 'A countdown is already running.') if V('pending') else (set_attr(me, 'label', arg1), set_attr(me, 'remaining', int(arg0)), eval_attr(me, 'tick')))",
    "@set Event Herald/cmd_scrub = $scrub countdown: (cancel_wait(V('pending')), del_attr(me, 'pending'), del_attr(me, 'remaining'), [remit(r, V('label', 'the event') + ' has been called off.') for r in search_world(tag='room')]) if V('pending') else pemit(enactor, 'No countdown is running.')",
]

# docs/showcase/151_business_hours.md
BUILD_151 = [
    "@dig Trade Annex = annex, out",
    "annex",
    "@create market clock",
    "drop market clock",
    "@set market clock/hour = 8",
    "@set market clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)",
    "@behavior market clock = script_ticker, interval:1",
    "@create trade terminal",
    "drop trade terminal",
    "@set trade terminal/open_hour = 9",
    "@set trade terminal/close_hour = 17",
    "@set trade terminal/open = 0",
    "@set trade terminal/refresh = h = get_attr('market clock', 'hour', 12); set_attr(me, 'open', 1 if V('open_hour', 9) <= h < V('close_hour', 17) else 0)",
    "@set trade terminal/on_tick = eval_attr(me, 'refresh')",
    "@behavior trade terminal = script_ticker, interval:1",
    "@desc trade terminal = A wall-mounted trade console. [[result = 'A green OPEN light glows steadily.' if V('open', 0) else 'A red CLOSED light glows; the screen is dark.']]",
    "@set trade terminal/cmd_access = $access terminal: pemit(enactor, 'ACCESS GRANTED. The markets are live -- place your orders.') if V('open', 0) else pemit(enactor, 'The screen is dark. Trade hours are ' + str(V('open_hour', 9)) + ':00 to ' + str(V('close_hour', 17)) + ':00.')",
]

# docs/showcase/152_persistent_timers.md
BUILD_152 = [
    "@dig Galley = galley, out",
    "galley",
    "@create egg timer",
    "drop egg timer",
    "@desc egg timer = A brass mechanical timer. SET TIMER <minutes> winds it; CHECK TIMER reads the dial.",
    "@set egg timer/cmd_set = $set timer *: (pemit(enactor, 'Give it whole minutes.') if not trim(arg0).isdigit() else (set_attr(me, 'rings_at', now() + int(arg0) * 60), expire(me, int(arg0) * 60), pemit(enactor, 'The timer winds up with a ratchet and begins ticking.')))",
    "@set egg timer/cmd_check = $check timer: pemit(enactor, 'The timer is not set.') if not V('rings_at') else pemit(enactor, str(max(0, V('rings_at', 0) - now())) + ' seconds remain.')",
    "@set egg timer/on_expire = del_attr(me, 'expires_at'); del_attr(me, 'rings_at'); remit(loc(me), 'BRRRING! The egg timer goes off, rattling on the counter.')",
]

# docs/showcase/153_time_scaling.md
BUILD_153 = [
    "@dig Chronometry Lab = chronlab, out",
    "chronlab",
    "@create master chronometer",
    "drop master chronometer",
    "@set master chronometer/game_min = 0",
    "@set master chronometer/step = 30",
    "@set master chronometer/on_tick = incr('game_min', V('step', 30))",
    "@behavior master chronometer = script_ticker, interval:1",
    "@set master chronometer/cmd_rate = $set rate *: (set_attr(me, 'step', int(arg0)), pemit(enactor, 'Time now advances ' + arg0 + ' game-minutes per world tick.')) if trim(arg0).isdigit() else pemit(enactor, 'Whole minutes only.')",
    "@set master chronometer/cmd_clock = $clock: m = V('game_min', 0); pemit(enactor, 'Day ' + str(m // 1440 + 1) + ', ' + right('0' + str((m // 60) % 24), 2) + ':' + right('0' + str(m % 60), 2))",
]

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


async def build(sim, lines):
    """Run one tutorial's build transcript as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    for line in lines:
        await sim.do(builder, line)
    out = "\n".join(sim.seen(builder))
    for flag in BUILD_RED_FLAGS:
        assert flag not in out, f"build tripped {flag!r}:\n{out}"
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
        await build(sim, BUILD_144)
        deck = room(sim, "Observation Deck")
        chrono = obj(sim, "ship chronometer")
        zara = sim.player("Zara", location=deck)

        assert chrono.db.get("game_min") == 0
        await tick(chrono)                      # +step (30)
        assert chrono.db.get("game_min") == 30

        await sim.do(zara, "date")
        assert "CS 812.01.01 // 00:30 -- month of Ignis." in text(sim, zara)

    async def test_derived_fields_divide_out_of_one_counter(self, sim):
        builder = await build(sim, BUILD_144)
        deck = room(sim, "Observation Deck")
        zara = sim.player("Zara", location=deck)

        # 2 months + 13 days + 17h + 42m past year zero.
        await sim.do(builder, "@set ship chronometer/game_min = 88662")
        await sim.do(zara, "date")
        assert "CS 812.03.14 // 17:42 -- month of Terra." in text(sim, zara)


# --- 145. Scheduled world events ------------------------------------------------


class TestScheduledEvents:

    async def test_daily_timetable_fires_once_per_hour_zone_wide(self, sim):
        await build(sim, BUILD_145)
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
        await build(sim, BUILD_145)
        clock = obj(sim, "colony clock")
        ai = obj(sim, "Colony AI")
        outsider = sim.player("Outsider", location=room(sim, "Limbo"))

        await tick(clock)     # -> hour 6
        await tick(ai)
        assert "klaxon" not in text(sim, outsider)


# --- 146. Item decay (batch sweeper) --------------------------------------------


class TestItemDecay:

    async def test_one_sweeper_rots_many_items_on_a_shared_clock(self, sim):
        await build(sim, BUILD_146)
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
        await build(sim, BUILD_146)
        crate = obj(sim, "crate of rations")
        assert crate.get_behaviors() == []      # pure data; the sweeper owns the clock


# --- 147. Zone repop ------------------------------------------------------------


def _drones(bridge):
    return [o for o in bridge.contents if o.name == "a maintenance drone"]


def _zone_reset(master):
    return [b for b in master.get_behaviors() if b.behavior_id == "zone_reset"][0]


class TestZoneRepop:

    async def test_repops_the_empty_zone_and_fires_on_reset(self, sim):
        builder = await build(sim, BUILD_147)
        bridge = room(sim, "Derelict Bridge")
        master = obj(sim, "Bridge Systems")
        await sim.do(builder, "out")            # clear the zone

        master.db.set("last_reset", 0)          # long overdue
        await _zone_reset(master).tick(master, 4.0)
        assert len(_drones(bridge)) == 2
        assert master.db.get("cycles") == 1     # ON_RESET ran

    async def test_presence_gate_defers_while_a_player_is_aboard(self, sim):
        builder = await build(sim, BUILD_147)
        bridge = room(sim, "Derelict Bridge")
        master = obj(sim, "Bridge Systems")
        sim.player("Straggler", location=bridge)   # someone's watching

        master.db.set("last_reset", 0)
        await _zone_reset(master).tick(master, 4.0)
        assert _drones(bridge) == []               # no pop on top of a player
        assert float(master.db.get("last_reset")) == 0   # not bumped; will retry

    async def test_repop_command_is_owner_only_and_queues_a_reset(self, sim):
        builder = await build(sim, BUILD_147)
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
        builder = await build(sim, BUILD_148)
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
        await build(sim, BUILD_148)
        chamber = room(sim, "Ritual Chamber")
        pip = sim.player("Pip", location=chamber)

        await sim.do(pip, "ring bell")
        sim.seen(pip)
        await sim.do(pip, "ring bell")
        assert "A ceremony is already underway." in text(sim, pip)

    async def test_silence_cancels_the_pending_timer(self, sim):
        await build(sim, BUILD_148)
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
        await build(sim, BUILD_149)
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
        builder = await build(sim, BUILD_150)
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
        builder = await build(sim, BUILD_150)
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
        await build(sim, BUILD_151)
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
        await build(sim, BUILD_151)
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
        await build(sim, BUILD_152)
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
        await build(sim, BUILD_152)
        galley = room(sim, "Galley")
        egg = obj(sim, "egg timer")
        cook = sim.player("Rue", location=galley)

        await sim.do(cook, "set timer soon")
        assert "Give it whole minutes." in text(sim, cook)
        assert egg.db.get("expires_at") is None


# --- 153. Time scaling ----------------------------------------------------------


class TestTimeScaling:

    async def test_rate_dial_scales_game_time_advance(self, sim):
        await build(sim, BUILD_153)
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
        await build(sim, BUILD_153)
        lab = room(sim, "Chronometry Lab")
        chrono = obj(sim, "master chronometer")
        tim = sim.player("Tim", location=lab)

        await sim.do(tim, "set rate 0")
        await tick(chrono, 3)
        assert chrono.db.get("game_min") == 0   # paused, server still running


# =========================================================================
# Doc <-> test sync: every tested Build-it line appears verbatim in its doc.
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "144_game_calendar.md": BUILD_144,
    "145_scheduled_events.md": BUILD_145,
    "146_item_decay.md": BUILD_146,
    "147_zone_repop.md": BUILD_147,
    "148_delayed_actions.md": BUILD_148,
    "149_maintenance_sweeper.md": BUILD_149,
    "150_countdown_events.md": BUILD_150,
    "151_business_hours.md": BUILD_151,
    "152_persistent_timers.md": BUILD_152,
    "153_time_scaling.md": BUILD_153,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
