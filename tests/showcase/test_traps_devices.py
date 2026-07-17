"""
Showcase verification — Traps, Hazards & Devices (standalone tutorials).

Items: 50 tripwire alarm, 51 pit trap, 52 poison dart trap, 53 snare,
55 motion sensor log, 56 self-destruct sequence, 57 EMP charge,
58 spreading fire, 59 tranquilizer mechanics.

Every command line in each tutorial's "Build it" section is driven
through the real dispatcher (raw input in -> session output out) by a
builder player, exactly as typed in the docs; the plays then exercise
the tutorials' "Try it" flows and assert outcomes.

Dice are removed via the pluggable check resolver (same convention as
tests/test_infiltration.py and test_heist.py): a check succeeds iff
effective skill >= 10, margin = effective - 10, so contests go to the
higher skill. Several builds run @reload (skill_def registration),
which re-installs the GURPS dice resolver — the line runner re-pins
the deterministic resolver after every command.

Time is virtual throughout: wait() fuses fire on tick_waits() pumps,
beat-driven effects (poison, sedation) advance via deliver_beat(),
script_ticker heartbeats are ticked by hand, and expire() lifetimes
are reaped with a forged clock.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from realm.core.beats import deliver_beat
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
from realm.testing import Simulator


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(
        success=effective >= 10,
        margin=effective - 10,
        roll=10,
        effective=effective,
        skill=skill,
    )


BUILD_RED_FLAGS = (
    "Unknown command", "Usage:", "not found", "Script error",
    "can't", "don't", "No permission",
)

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks.

    The build transcript is read out of the markdown rather than mirrored
    here as a literal, so these tests execute *what the doc actually says*
    — a doc edit that breaks the build breaks this suite, and there is no
    second copy to drift from. (Fences in this family are ```text; the
    NPC tutorials use a bare ```, so the language tag is optional.)
    """
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines: list[str] = []
    for block in re.findall(r"```[a-z]*\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer wires the session manager at startup; the Simulator
    # leaves it to the test (needed by prompt()).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, keeping the
    deterministic resolver pinned (a build's @reload re-installs the
    GURPS dice resolver)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, doc_name):
    """Run one tutorial's build transcript, read live out of its
    markdown, as a builder from Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    await run_lines(sim, builder, build_lines(doc_name))
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


async def pulse(fire):
    """Advance a script_ticker (interval:2) by exactly one on_tick run:
    from a zeroed countdown, the first tick fires and re-arms to 1, the
    second decrements back to 0 without firing."""
    for behavior in list(fire.get_behaviors()):
        await behavior.tick(fire, 4.0)
    for behavior in list(fire.get_behaviors()):
        await behavior.tick(fire, 4.0)


# --- 50. Tripwire alarm ---------------------------------------------------------


class TestTripwireAlarm:

    async def test_silent_alert_reaches_owner_and_not_the_intruder(self, sim):
        builder = await build(sim, "050_tripwire_alarm.md")
        assert builder.location is room(sim, "The Curio Shop")
        zeke = sim.player("Zeke", location=room(sim, "The Curio Shop"))

        await sim.do(zeke, "stockroom")
        assert "[tripwire] Zeke crossed The Stockroom." in text(sim, builder)
        out = text(sim, zeke)
        assert "[tripwire]" not in out          # silent to the walker
        assert "tripwire" not in out            # hidden from the room display
        assert obj(sim, "tripwire").db.get("trips") == 1

        # Every crossing pages; the counter remembers.
        await sim.do(zeke, "shop")
        sim.seen(builder)
        await sim.do(zeke, "stockroom")
        assert "[tripwire] Zeke crossed The Stockroom." in text(sim, builder)
        assert obj(sim, "tripwire").db.get("trips") == 2  # back in again

    async def test_search_reveals_and_a_seen_wire_reports_nothing(self, sim):
        builder = await build(sim, "050_tripwire_alarm.md")
        raven = sim.player("Raven", location=room(sim, "The Stockroom"),
                           skill_observation=12)
        sim.seen(builder)
        trips_before = obj(sim, "tripwire").db.get("trips") or 0

        await sim.do(raven, "search")
        # Deliberate search rolls at -conceal_difficulty: 12 - 2 = 10.
        assert "A glint at ankle height" in text(sim, raven)
        assert not obj(sim, "tripwire").has_tag("invisible")

        await sim.do(raven, "shop")
        sim.seen(raven)
        sim.seen(builder)
        await sim.do(raven, "stockroom")
        assert "You step over the exposed tripwire." in text(sim, raven)
        assert "[tripwire]" not in text(sim, builder)     # no alert once seen
        assert (obj(sim, "tripwire").db.get("trips") or 0) == trips_before

    async def test_owner_never_pages_themselves(self, sim):
        builder = await build(sim, "050_tripwire_alarm.md")
        sim.seen(builder)
        await sim.do(builder, "stockroom")
        assert "[tripwire]" not in text(sim, builder)
        assert (obj(sim, "tripwire").db.get("trips") or 0) == 0


# --- 51. Pit trap ---------------------------------------------------------------


class TestPitTrap:

    async def test_sharp_eyes_sidestep_dull_eyes_drop(self, sim):
        builder = await build(sim, "051_pit_trap.md")
        limbo = room(sim, "Limbo")
        scout = sim.player("Scout", location=limbo, skill_observation=13,
                           hp=13, max_hp=13)
        mook = sim.player("Mook", location=limbo, skill_observation=6,
                          hp=13, max_hp=13)

        await sim.do(scout, "gallery")
        # observation 13 - 3 = 10: sidestep (and the plate stays armed).
        assert "you step around it just in time" in text(sim, scout)
        assert scout.location is room(sim, "The Dusty Gallery")
        assert obj(sim, "rigged flagstone").db.get("armed") == 1

        await sim.do(mook, "gallery")
        out = text(sim, mook)
        assert "The floor drops away beneath you!" in out
        assert "You land hard on cold stone, far below." in out
        assert mook.location is room(sim, "The Oubliette")
        # The gallery watched it happen, and the fall sprang the doors.
        assert "Mook vanishes through the floor with a crash!" in text(sim, scout)
        assert obj(sim, "rigged flagstone").db.get("armed") == 0

    async def test_climb_out_is_a_skill_gated_exit(self, sim):
        builder = await build(sim, "051_pit_trap.md")
        limbo = room(sim, "Limbo")
        mook = sim.player("Mook", location=limbo, skill_observation=6,
                          hp=13, max_hp=13)
        sly = sim.player("Sly", location=limbo, skill_observation=6,
                         skill_climbing=12, hp=13, max_hp=13)

        await sim.do(mook, "gallery")
        assert mook.location is room(sim, "The Oubliette")
        # The fall sprang the doors -- re-arm for the next victim.
        await run_lines(sim, builder, ["@set rigged flagstone/armed = 1"])
        await sim.do(sly, "gallery")
        assert sly.location is room(sim, "The Oubliette")
        sim.seen(mook)
        sim.seen(sly)

        # Untrained climbing defaults to DX-5 = 5; 5 - 2 = 3: slide back.
        await sim.do(mook, "climb")
        assert "slide back down" in text(sim, mook)
        assert mook.location is room(sim, "The Oubliette")

        # Climbing 12 - 2 = 10: out -- and the surfacing is safe, because
        # the climber's own fall left the trapdoor hanging open.
        await sim.do(sly, "climb")
        assert sly.location is room(sim, "The Dusty Gallery")
        assert "floor drops away" not in text(sim, sly)

    async def test_owner_walks_their_own_gallery_safely(self, sim):
        builder = await build(sim, "051_pit_trap.md")
        sim.seen(builder)
        await sim.do(builder, "out")
        await sim.do(builder, "gallery")
        assert builder.location is room(sim, "The Dusty Gallery")
        assert "floor drops away" not in text(sim, builder)


# --- 52. Poison dart trap -------------------------------------------------------


class TestPoisonDartTrap:

    async def test_touch_resisted_and_unresisted_with_ticking_venom(self, sim):
        builder = await build(sim, "052_poison_dart_trap.md")
        reliquary = room(sim, "The Reliquary")
        raven = sim.player("Raven", location=reliquary,
                           hp=13, max_hp=13, health=13)   # fortitude 13-2=11
        zeke = sim.player("Zeke", location=reliquary,
                          hp=13, max_hp=13, health=8)     # fortitude 8-2=6

        await sim.do(raven, "touch idol")
        out = text(sim, raven)
        assert "A hidden nozzle spits a needle-thin dart!" in out
        assert "Only a scratch." in out
        assert 11 <= raven.db.get("hp") <= 12              # 1d2 dart
        assert not raven.has_tag("poison")

        await sim.do(zeke, "touch idol")
        assert "A cold numbness spreads from the scratch." in text(sim, zeke)
        assert zeke.has_tag("poison")
        hp0 = zeke.db.get("hp")

        # The venom is a beat-driven engine effect.
        sim.seen(raven)
        for _ in range(3):
            await deliver_beat(zeke)
        assert zeke.db.get("hp") == hp0 - 3
        assert "Venom burns through your veins!" in text(sim, zeke)
        assert "Zeke shivers, grey-faced and sweating." in text(sim, raven)

        # ...and it expires on its own (5 pulses across 6 beats).
        for _ in range(3):
            await deliver_beat(zeke)
        assert not zeke.has_tag("poison")
        assert "The fever finally breaks." in text(sim, zeke)
        assert zeke.db.get("hp") == hp0 - 5

    async def test_grabbing_the_idol_also_darts_you(self, sim):
        builder = await build(sim, "052_poison_dart_trap.md")
        reliquary = room(sim, "The Reliquary")
        hawk = sim.player("Hawk", location=reliquary,
                          hp=13, max_hp=13, health=13)

        await sim.do(hawk, "get jade idol")
        out = text(sim, hawk)
        assert "A hidden nozzle spits a needle-thin dart!" in out
        assert hawk.db.get("hp") < 13
        assert obj(sim, "jade idol").location is hawk      # the grab succeeded

    async def test_antidote_cures_and_spends_itself(self, sim):
        builder = await build(sim, "052_poison_dart_trap.md")
        reliquary = room(sim, "The Reliquary")
        raven = sim.player("Raven", location=reliquary,
                           hp=13, max_hp=13, health=13)
        zeke = sim.player("Zeke", location=reliquary,
                          hp=13, max_hp=13, health=8)

        await sim.do(raven, "drink antidote")
        assert "You are not poisoned. Save it." in text(sim, raven)
        assert objs(sim, "antidote vial")                  # unspent

        await sim.do(zeke, "touch idol")
        assert zeke.has_tag("poison")
        await sim.do(zeke, "drink antidote")
        assert "Bitter warmth washes the numbness out of your blood." in text(sim, zeke)
        assert not zeke.has_tag("poison")
        assert objs(sim, "antidote vial") == []            # spent

        hp_after_cure = zeke.db.get("hp")
        for _ in range(3):
            await deliver_beat(zeke)
        assert zeke.db.get("hp") == hp_after_cure          # ticking stopped


# --- 53. Snare ------------------------------------------------------------------


class TestSnare:

    async def test_snare_holds_movement_until_strength_wins(self, sim):
        builder = await build(sim, "053_snare.md")
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo, strength=12,
                          hp=13, max_hp=13)

        await sim.do(zeke, "trail")
        out = text(sim, zeke)
        assert "The world jerks sideways -- you are caught fast!" in out
        assert zeke.has_tag("snared")
        assert obj(sim, "hunting snare").db.get("armed") == 0
        assert "A wire loop snaps tight around Zeke's ankle!" in text(sim, builder)

        # The ward vetoes every departure while the tag holds.
        await sim.do(zeke, "out")
        assert "The snare around your ankle jerks taut!" in text(sim, zeke)
        assert zeke.location is room(sim, "The Game Trail")

        # ST 12 vs hold 12: tie, and ties go to the snare -- which loosens.
        await sim.do(zeke, "struggle")
        assert "It gives a little -- and holds." in text(sim, zeke)
        assert obj(sim, "hunting snare").db.get("skill_hold") == 11
        assert zeke.has_tag("snared")

        # ST 12 vs hold 11: free.
        await sim.do(zeke, "struggle")
        assert "Zeke tears free of the snare!" in text(sim, zeke)
        assert not zeke.has_tag("snared")

        await sim.do(zeke, "out")
        assert zeke.location is limbo

    async def test_sprung_snare_ignores_the_next_walker(self, sim):
        builder = await build(sim, "053_snare.md")
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo, strength=12,
                          hp=13, max_hp=13)
        mook = sim.player("Mook", location=limbo, strength=10,
                          hp=13, max_hp=13)

        await sim.do(zeke, "trail")                        # springs it
        assert zeke.has_tag("snared")
        await sim.do(mook, "trail")
        assert not mook.has_tag("snared")                  # armed = 0

        await sim.do(mook, "struggle")
        assert "You are not caught in anything." in text(sim, mook)
        await sim.do(mook, "out")
        assert mook.location is limbo                      # free to go


# --- 55. Motion sensor log ------------------------------------------------------


class TestMotionSensorLog:

    async def test_log_records_walkers_and_review_plays_back(self, sim):
        builder = await build(sim, "055_motion_sensor.md")
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo)

        await sim.do(zeke, "vault")
        await sim.do(zeke, "out")
        await sim.do(builder, "review")
        out = text(sim, builder)
        assert "Zeke entered." in out
        assert "Zeke left." in out
        assert out.index("Zeke entered.") < out.index("Zeke left.")
        assert "s ago]" in out

    async def test_teleport_skips_the_departure_event(self, sim):
        builder = await build(sim, "055_motion_sensor.md")
        zeke = sim.player("Zeke", location=room(sim, "The Server Vault"))

        await run_lines(sim, builder, ["@teleport me = Limbo"])
        await run_lines(sim, builder, ["@teleport me = The Server Vault"])
        sim.seen(builder)
        await sim.do(builder, "review")
        out = text(sim, builder)
        assert "Bob entered." in out       # teleport arrivals fire on_enter
        assert "Bob left." not in out      # teleport departures are unseen

    async def test_log_is_capped_at_twenty_records(self, sim):
        builder = await build(sim, "055_motion_sensor.md")
        limbo = room(sim, "Limbo")
        zeke = sim.player("Zeke", location=limbo)

        for _ in range(12):                # 24 records, capped to 20
            await sim.do(zeke, "vault")
            await sim.do(zeke, "out")
        log = obj(sim, "motion sensor").db.get("log")
        assert len(log) == 20
        assert log[-1][1] == "left"        # newest survives the slice


# --- 56. Self-destruct sequence -------------------------------------------------


class TestSelfDestruct:

    async def test_authority_idle_abort_and_double_arm(self, sim):
        builder = await build(sim, "056_self_destruct.md")
        raven = sim.player("Raven", location=room(sim, "Cargo Bay"),
                           hp=20, max_hp=20)

        await sim.do(raven, "self destruct")
        assert "The console demands command authority." in text(sim, raven)

        await sim.do(raven, "abort")
        assert "The self-destruct is not armed." in text(sim, raven)

        await run_lines(sim, builder, ["@set Station Brain/interval = 0"])
        sim.seen(builder)
        await sim.do(builder, "self destruct")
        assert "SELF-DESTRUCT SEQUENCE INITIATED" in text(sim, builder)
        await sim.do(builder, "self destruct")
        assert "The countdown is already running." in text(sim, builder)

    async def test_zone_wide_klaxons_and_coded_abort_from_another_room(self, sim):
        builder = await build(sim, "056_self_destruct.md")
        raven = sim.player("Raven", location=room(sim, "Cargo Bay"),
                           hp=20, max_hp=20)
        await run_lines(sim, builder, ["@set Station Brain/interval = 0"])
        brain = obj(sim, "Station Brain")

        await sim.do(builder, "self destruct")
        # The klaxon is zone-wide: Raven hears it a room away.
        assert "SELF-DESTRUCT SEQUENCE INITIATED" in text(sim, raven)
        assert brain.db.get("pending")

        await sim.engine.tick_waits()      # one chain stage
        assert "SELF-DESTRUCT IN" in text(sim, raven)
        assert brain.db.get("count") == 4

        # Wrong code first -- the countdown keeps its nerve.
        await sim.do(raven, "abort")
        assert "Enter the abort code:" in text(sim, raven)
        handler = sim.session(raven).input_handler
        assert handler is not None, "prompt() should capture the next line"
        await handler(sim.session(raven), "WOMBAT")
        assert "INVALID CODE. The countdown continues." in text(sim, raven)
        assert brain.db.get("pending")

        # Right code, from the Cargo Bay -- the zone master hears it there.
        sim.seen(builder)
        await sim.do(raven, "abort")
        handler = sim.session(raven).input_handler
        await handler(sim.session(raven), "ZEBRA-9")
        assert "SELF-DESTRUCT ABORTED. Authorization: Raven." in text(sim, builder)
        assert brain.db.get("pending") is None
        assert brain.db.get("count") is None

        # The cancelled wait never fires; nothing burns.
        await sim.engine.tick_waits()
        assert objs(sim, "a sheet of roaring flame") == []

        # The code itself is engine-secret to strangers, readable to the owner.
        stolen, _err = await sim.eval(
            raven, "result = get_attr(get('Station Brain'), 'code')")
        assert stolen is None
        own, _err = await sim.eval(
            builder, "result = get_attr(get('Station Brain'), 'code')")
        assert own == "ZEBRA-9"

    async def test_zero_hour_burns_every_compartment(self, sim):
        builder = await build(sim, "056_self_destruct.md")
        raven = sim.player("Raven", location=room(sim, "Cargo Bay"),
                           hp=20, max_hp=20)
        await run_lines(sim, builder, ["@set Station Brain/interval = 0"])

        await sim.do(builder, "self destruct")
        for _ in range(5):                 # stages 4, 3, 2, 1, boom
            await sim.engine.tick_waits()

        assert "Fire tears through every compartment!" in text(sim, raven)
        flames = objs(sim, "a sheet of roaring flame")
        assert {f.location for f in flames} == {
            room(sim, "Reactor Core"), room(sim, "Cargo Bay")}
        brain = obj(sim, "Station Brain")
        assert brain.db.get("pending") is None

        # The flames are proximity hazards on their own heartbeat.
        for flame in flames:
            for behavior in list(flame.get_behaviors()):
                await behavior.tick(flame, 1.0)
        assert "Fire roars over you!" in text(sim, raven)
        assert raven.db.get("hp") < 20

        # ...and they gutter out on their expire() fuel.
        reaped = await reap_expired(sim.store, now=time.time() + 120)
        assert reaped == 2
        assert objs(sim, "a sheet of roaring flame") == []


# --- 57. EMP charge -------------------------------------------------------------


class TestEmpCharge:

    async def test_pulse_disables_and_expiry_restores(self, sim):
        builder = await build(sim, "057_emp_charge.md")
        lab = room(sim, "The Drone Lab")
        raven = sim.player("Raven", location=lab)

        # Baseline: both gadgets answer.
        await sim.do(raven, "ping drone")
        assert "ALL SYSTEMS NOMINAL." in text(sim, raven)
        await sim.do(raven, "login")
        assert "ACCESS GRANTED." in text(sim, raven)

        # Refuses to fire in hand.
        await sim.do(builder, "get EMP charge")
        sim.seen(builder)
        await sim.do(builder, "arm emp")
        assert "Set it down first." in text(sim, builder)
        await sim.do(builder, "drop EMP charge")

        # The pulse: sweep, remember, go dark.
        await sim.do(raven, "arm emp")
        assert "A soundless white PULSE." in text(sim, raven)
        drone = obj(sim, "sweeper drone")
        terminal = obj(sim, "wall terminal")
        charge = obj(sim, "EMP charge")
        assert drone.has_tag("disabled")
        assert terminal.has_tag("disabled")
        assert len(charge.db.get("hit")) == 2
        assert charge.db.get("expires_at")

        await sim.do(raven, "ping drone")
        assert "The drone lies inert, rotors still." in text(sim, raven)
        await sim.do(raven, "login")
        assert "The screen is dead glass." in text(sim, raven)

        # The restore rides ON_EXPIRE; the casing dies with the effect.
        reaped = await reap_expired(sim.store, now=time.time() + 60)
        assert reaped == 1
        assert not drone.has_tag("disabled")
        assert not terminal.has_tag("disabled")
        assert objs(sim, "EMP charge") == []
        assert "status lights flicker back to life" in text(sim, raven)

        await sim.do(raven, "ping drone")
        assert "ALL SYSTEMS NOMINAL." in text(sim, raven)


# --- 58. Spreading fire ---------------------------------------------------------


def fires_in(sim, where):
    return [f for f in objs(sim, "a hungry fire") if f.location is where]


class TestSpreadingFire:

    async def test_growth_spread_doors_and_extinguisher(self, sim):
        builder = await build(sim, "058_spreading_fire.md")
        hayloft = room(sim, "The Hayloft")
        stable = room(sim, "The Stable")
        tack = room(sim, "The Tack Room")
        limbo = room(sim, "Limbo")
        assert builder.location is hayloft
        mook = sim.player("Mook", location=hayloft, hp=20, max_hp=20)
        groom = sim.player("Groom", location=stable, hp=20, max_hp=20)

        await sim.do(builder, "light fire")
        assert "drops a lit match into the straw. Flames catch!" in text(sim, mook)
        fire = fires_in(sim, hayloft)[0]

        # Stage 1: smolder, narration only.
        await pulse(fire)
        assert "Smoke thickens. Flames crawl wider." in text(sim, mook)
        assert mook.db.get("hp") == 20
        assert fire.db.get("stage") == 2

        # Stage 2: it burns whoever stands in it.
        await pulse(fire)
        assert "The blaze sears you!" in text(sim, mook)
        assert mook.db.get("hp") < 20
        assert fire.db.get("stage") == 3

        # Stage 3: inferno -- and it jumps the open ladderway.
        sim.seen(groom)
        await pulse(fire)
        assert "Fire licks through the doorway -- it catches!" in text(sim, groom)
        assert len(fires_in(sim, stable)) == 1
        assert fires_in(sim, tack) == []       # the shut tack door held
        assert fires_in(sim, limbo) == []      # so did the shut yard door
        assert fire.db.get("stage") == 3       # capped

        # Counterplay, stage by stage.
        sim.seen(builder)
        await sim.do(builder, "spray fire")
        assert "drives the fire back with a jet of foam!" in text(sim, builder)
        assert fire.db.get("stage") == 2
        await sim.do(builder, "spray fire")
        assert fire.db.get("stage") == 1
        await sim.do(builder, "spray fire")
        assert "smothers the last flames in a white cloud." in text(sim, builder)
        assert fires_in(sim, hayloft) == []

        # The stable fire is its own cell -- kill it before it rages.
        await sim.do(builder, "ladder")
        sim.seen(builder)
        await sim.do(builder, "spray fire")    # stage-1 fire dies to one spray
        assert "smothers the last flames" in text(sim, builder)
        assert objs(sim, "a hungry fire") == []

        await sim.do(builder, "spray fire")
        assert "Nothing here is burning." in text(sim, builder)


# --- 59. Tranquilizer mechanics -------------------------------------------------


class TestTranquilizer:

    async def test_knockout_engine_lockout_and_natural_wakeup(self, sim):
        builder = await build(sim, "059_tranquilizer.md")
        medbay = room(sim, "The Med Bay")
        brick = sim.player("Brick", location=medbay,
                           hp=13, max_hp=13, health=13)   # fortitude 13-3=10
        zeke = sim.player("Zeke", location=medbay,
                          hp=13, max_hp=13, health=8)     # fortitude 8-3=5

        await sim.do(builder, "shoot Brick")
        assert "Your vision swims... then steadies." in text(sim, brick)
        assert not brick.has_tag("unconscious")

        await sim.do(builder, "shoot Zeke")
        assert "The room smears sideways. Then nothing." in text(sim, zeke)
        assert "Zeke crumples bonelessly to the floor." in text(sim, brick)
        assert zeke.has_tag("unconscious")
        assert zeke.db.get("hp") == 13         # no HP damage: a knockout

        # The engine's own gates close: no walking, no fighting.
        await sim.do(zeke, "out")
        assert "You are unconscious." in text(sim, zeke)
        assert zeke.location is medbay
        await sim.do(zeke, "attack Brick")
        assert "You are unconscious." in text(sim, zeke)

        # Six beats of sedation, then the effect expires itself.
        for _ in range(6):
            await deliver_beat(zeke)
        assert not zeke.has_tag("unconscious")
        assert "You come to, cheek on the cold deck." in text(sim, zeke)
        await sim.do(zeke, "out")
        assert zeke.location is room(sim, "Limbo")

    async def test_stim_injector_wakes_early_and_misses_gracefully(self, sim):
        builder = await build(sim, "059_tranquilizer.md")
        medbay = room(sim, "The Med Bay")
        brick = sim.player("Brick", location=medbay,
                           hp=13, max_hp=13, health=13)
        zeke = sim.player("Zeke", location=medbay,
                          hp=13, max_hp=13, health=8)

        await sim.do(builder, "jab Brick")
        assert "They are not sedated." in text(sim, builder)

        await sim.do(builder, "shoot Zeke")
        assert zeke.has_tag("unconscious")
        await sim.do(builder, "jab Zeke")
        assert "They jolt awake." in text(sim, builder)
        assert not zeke.has_tag("unconscious")
        await sim.do(zeke, "out")
        assert zeke.location is room(sim, "Limbo")

    async def test_missing_target_is_a_clean_miss(self, sim):
        builder = await build(sim, "059_tranquilizer.md")
        sim.seen(builder)
        await sim.do(builder, "shoot Nobody")
        assert "No sign of them in reach." in text(sim, builder)
