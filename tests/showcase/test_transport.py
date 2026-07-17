"""
Showcase verification — Movement & Transportation (items 154-164, minus
160 which the heist arc owns).

Items: 154 elevator, 155 drivable vehicle, 156 scheduled shuttle,
157 teleporter pads, 158 mounts, 159 group travel, 161 travel time,
162 tracking, 163 vehicle fuel, 164 small spaceship (capstone).

Every "Build it" command line is read straight out of the tutorial's
markdown (docs/showcase/NNN_*.md) and driven through the real dispatcher
by a builder — so the tests exercise *exactly* what the docs tell you to
type, and a doc edit that breaks the build breaks the suite. The plays
then walk the "Try it" flows and assert outcomes.

Time is virtual: script_ticker heartbeats and wait() sweeps are driven by
hand (run_object_script), and expire() decay by reap_expired — the same
determinism conventions as the other showcase suites.

Dice are removed via the pluggable check resolver (as in
tests/showcase/test_doors_exits.py): a check succeeds iff effective skill
>= 10.
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

DOC_FILES = {
    154: "154_elevator.md",
    155: "155_drivable_vehicle.md",
    156: "156_scheduled_shuttle.md",
    157: "157_teleporter_pads.md",
    158: "158_mounts.md",
    159: "159_group_travel.md",
    161: "161_travel_time.md",
    162: "162_tracking.md",
    163: "163_vehicle_fuel.md",
    164: "164_small_spaceship.md",
}


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
    "Eval error", "No permission", "Permission denied", "Bad parameter",
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


async def build(sim, item: int):
    """Run a tutorial's build transcript as a fresh builder, red-flag scanned."""
    doc_name = DOC_FILES[item]
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


def objs(sim, name):
    return sim.store.find_cached(name=name)


def exit_in(room_obj, name):
    matches = [e for e in room_obj.contents if e.has_tag("exit") and e.name == name]
    assert matches, f"no exit {name!r} in {room_obj.name}"
    return matches[0]


def text(sim, player):
    return "\n".join(sim.seen(player))


# --- doc <-> test sync ---------------------------------------------------------


class TestDocsPresentAndFormatted:
    """Every item in this category has a tutorial with the required sections
    and a non-empty Build it that this suite actually runs."""

    @pytest.mark.parametrize("item,doc", sorted(DOC_FILES.items()))
    def test_doc_has_required_sections(self, item, doc):
        body = (DOCS / doc).read_text()
        for heading in ("## How it works", "## Build it", "## Try it",
                        "## Going further"):
            assert heading in body, f"{doc} missing {heading}"
        assert f"item {item}" in body.lower() or f"item {item} " in body, \
            f"{doc} missing checklist item marker"
        assert build_lines(doc), f"{doc} has no runnable Build it lines"


# --- 154. Elevator -------------------------------------------------------------


class TestElevator:

    async def test_press_relinks_and_call_summons(self, sim):
        await build(sim, 154)
        lobby = room(sim, "The Lobby")
        mez = room(sim, "The Mezzanine")
        car = room(sim, "The Elevator Car")
        doors = exit_in(car, "doors")
        lob_ex = exit_in(lobby, "elevator")
        mez_ex = exit_in(mez, "elevator")

        # Built parked at the Lobby: lobby open, mezzanine sealed.
        assert doors.db.get("destination") == lobby.id
        assert not lob_ex.has_tag("closed")
        assert mez_ex.has_tag("closed")

        pat = sim.player("Pat", location=lobby)
        await sim.do(pat, "elevator")
        assert pat.location is car
        sim.seen(pat)

        await sim.do(pat, "press 2")
        assert "glides to a stop" in text(sim, pat)
        assert doors.db.get("destination") == mez.id       # relinked
        assert not mez_ex.has_tag("closed")                # mezz now open
        assert lob_ex.has_tag("closed")                    # lobby sealed
        await sim.do(pat, "doors")
        assert pat.location is mez

    async def test_call_button_brings_the_car(self, sim):
        await build(sim, 154)
        lobby = room(sim, "The Lobby")
        mez = room(sim, "The Mezzanine")
        car = room(sim, "The Elevator Car")
        # Send the car up first.
        rider = sim.player("Rider", location=lobby)
        await sim.do(rider, "elevator")
        await sim.do(rider, "press 2")
        await sim.do(rider, "doors")
        assert rider.location is mez

        # A latecomer in the lobby: the shaft is sealed until they call.
        quinn = sim.player("Quinn", location=lobby)
        await sim.do(quinn, "elevator")
        assert quinn.location is lobby
        assert "closed" in text(sim, quinn)
        sim.seen(quinn)
        await sim.do(quinn, "call")
        assert "doors part" in text(sim, quinn)
        await sim.do(quinn, "elevator")
        assert quinn.location is car


# --- 155. Drivable vehicle -----------------------------------------------------


class TestDrivableVehicle:

    async def test_board_drive_and_step_out(self, sim):
        await build(sim, 155)
        pool = room(sim, "The Motor Pool")
        flats = room(sim, "The Dust Flats")
        rim = room(sim, "The Canyon Rim")
        cab = room(sim, "The Rover Cab")
        board = [o for o in objs(sim, "board") if o.has_tag("exit")][0]
        assert board.location is pool               # gangway parked at the pool

        pat = sim.player("Pat", location=pool)
        await sim.do(pat, "board")
        assert pat.location is cab
        sim.seen(pat)

        await sim.do(pat, "drive north")
        assert "lurches north" in text(sim, pat)
        assert board.location is flats              # gangway travelled
        assert cab.db.get("parked_at") == flats.id
        await sim.do(pat, "hatch")
        assert pat.location is flats                # hatch relinked

        # A second hop, deeper into the map.
        await sim.do(pat, "board")
        await sim.do(pat, "drive north")
        assert board.location is rim
        await sim.do(pat, "hatch")
        assert pat.location is rim

    async def test_outside_view_is_push_on_change(self, sim):
        await build(sim, 155)
        pool = room(sim, "The Motor Pool")
        watcher = sim.player("Watcher", location=pool)
        await sim.do(watcher, "look board")
        assert "rover" in text(sim, watcher).lower()   # the [[...]] sitrep renders

    async def test_cannot_drive_a_dead_direction(self, sim):
        await build(sim, 155)
        pool = room(sim, "The Motor Pool")
        cab = room(sim, "The Rover Cab")
        pat = sim.player("Pat", location=pool)
        await sim.do(pat, "board")
        sim.seen(pat)
        await sim.do(pat, "drive west")            # the pool has no west exit
        assert "cannot roll west" in text(sim, pat)
        assert cab.db.get("parked_at") == pool.id


# --- 156. Scheduled shuttle ----------------------------------------------------


class TestScheduledShuttle:

    async def test_route_loops_and_carries_riders(self, sim):
        await build(sim, 156)
        p1 = room(sim, "Platform One")
        p2 = room(sim, "Platform Two")
        p3 = room(sim, "Platform Three")
        cab = room(sim, "The Shuttle Cabin")
        board = [o for o in objs(sim, "shuttle") if o.has_tag("exit")][0]
        assert board.location is p1

        # Board during the boarding window.
        pat = sim.player("Pat", location=p1)
        await sim.do(pat, "shuttle")
        assert pat.location is cab
        sim.seen(pat)

        # One beat: depart P1, arrive P2, carrying the rider.
        await sim.engine.run_object_script(cab, "on_tick")
        assert board.location is p2
        assert "changes track" in text(sim, pat)
        await sim.do(pat, "hatch")
        assert pat.location is p2                   # rider rode to P2

        # The loop keeps going and wraps.
        await sim.engine.run_object_script(cab, "on_tick")
        assert board.location is p3
        await sim.engine.run_object_script(cab, "on_tick")
        assert board.location is p1

    async def test_boarding_window_shuts_when_it_departs(self, sim):
        await build(sim, 156)
        p1 = room(sim, "Platform One")
        cab = room(sim, "The Shuttle Cabin")
        board = [o for o in objs(sim, "shuttle") if o.has_tag("exit")][0]

        # It departs P1 on the tick -> the gangway there seals behind it.
        await sim.engine.run_object_script(cab, "on_tick")
        assert board.location is not p1
        late = sim.player("Late", location=p1)
        await sim.do(late, "shuttle")
        assert late.location is p1                  # no boarding once it's gone


# --- 157. Teleporter pads ------------------------------------------------------


class TestTeleporterPads:

    async def test_dial_across_the_network(self, sim):
        await build(sim, 157)
        alpha = room(sim, "Alpha Station")
        gamma = room(sim, "Gamma Relay")

        pat = sim.player("Pat", location=alpha)
        await sim.do(pat, "pads")
        listing = text(sim, pat)
        assert "Alpha" in listing and "Beta" in listing and "Gamma" in listing
        sim.seen(pat)

        witness = sim.player("Witness", location=alpha)
        await sim.do(pat, "dial Gamma")
        assert pat.location is gamma
        assert "you are elsewhere" in text(sim, pat)
        assert "column of light" in text(sim, witness)   # oemit to those left behind

    async def test_dialing_an_unknown_pad(self, sim):
        await build(sim, 157)
        alpha = room(sim, "Alpha Station")
        pat = sim.player("Pat", location=alpha)
        await sim.do(pat, "dial Nowhere")
        assert "No pad answers" in text(sim, pat)
        assert pat.location is alpha

    async def test_registry_is_search_not_wiring(self, sim):
        await build(sim, 157)
        # The template pad was destroyed; exactly three live pads remain,
        # each found only by its tag.
        pads = [p for p in sim.store.all_cached() if p.has_tag("teleport_pad")]
        assert sorted(p.db.get("pad_name") for p in pads) == ["Alpha", "Beta", "Gamma"]


# --- 158. Mounts ---------------------------------------------------------------


class TestMounts:

    async def test_mount_ride_and_dismount(self, sim):
        await build(sim, 158)
        paddock = room(sim, "The Paddock")
        trail = room(sim, "The Trail")
        rusty = objs(sim, "Rusty")[0]

        pat = sim.player("Pat", location=paddock)
        await sim.do(pat, "mount Rusty")
        assert pat.location is rusty                # containment: you're aboard
        assert rusty.db.get("rider") == "#" + pat.id
        sim.seen(pat)

        await sim.do(pat, "ride trail")
        assert rusty.location is trail
        assert pat.location is rusty                # carried inside
        assert "bears you into The Trail" in text(sim, pat)   # ON_ARRIVE relay

        await sim.do(pat, "dismount")
        assert pat.location is trail
        assert rusty.db.get("rider") is None

    async def test_only_one_rider(self, sim):
        await build(sim, 158)
        paddock = room(sim, "The Paddock")
        rusty = objs(sim, "Rusty")[0]
        pat = sim.player("Pat", location=paddock)
        poacher = sim.player("Poacher", location=paddock)
        await sim.do(pat, "mount Rusty")
        await sim.do(poacher, "mount Rusty")
        assert "already astride" in text(sim, poacher)
        assert poacher.location is paddock


# --- 159. Group travel ---------------------------------------------------------


class TestGroupTravel:

    async def test_column_crosses_as_one(self, sim):
        await build(sim, 159)
        camp = room(sim, "The Camp")
        bridge = room(sim, "The Old Bridge")

        alice = sim.player("Alice", location=camp)
        bobby = sim.player("Bobby", location=camp)
        await sim.do(bobby, "follow Alice")
        assert bobby.db.get("following") == alice.id

        # The guide agrees to fall in via her $-command.
        await sim.do(alice, "escort")
        wend = objs(sim, "Wend the guide")[0]
        assert wend.db.get("following") == alice.id

        await sim.do(alice, "party")
        listing = text(sim, alice)
        assert "Bobby" in listing and "Wend the guide" in listing

        await sim.do(alice, "north")
        assert alice.location is bridge
        assert bobby.location is bridge             # cascade
        assert wend.location is bridge

    async def test_halt_is_owner_gated_and_loop_is_safe(self, sim):
        await build(sim, 159)
        camp = room(sim, "The Camp")
        alice = sim.player("Alice", location=camp)
        stranger = sim.player("Stranger", location=camp)
        await sim.do(alice, "escort")
        wend = objs(sim, "Wend the guide")[0]

        # Only Alice, who leads her, may halt her.
        await sim.do(stranger, "halt wend")
        assert "not yours to command" in text(sim, stranger)
        assert wend.db.get("following") == alice.id
        await sim.do(alice, "halt wend")
        assert wend.db.get("following") is None

        # A mutual follow loop resolves in one pass instead of recursing.
        from realm.core.party import set_following
        bobby = sim.player("Bobby", location=camp)
        set_following(bobby, alice)
        set_following(alice, bobby)
        bridge = room(sim, "The Old Bridge")
        await sim.do(alice, "north")
        assert alice.location is bridge and bobby.location is bridge


# --- 161. Travel time ----------------------------------------------------------


class TestTravelTime:

    async def test_journey_progresses_then_arrives(self, sim):
        await build(sim, 161)
        trailhead = room(sim, "The Trailhead")
        road = room(sim, "The Long Road")
        fort = room(sim, "The Hillfort")
        road_exit = exit_in(trailhead, "road")

        pat = sim.player("Pat", location=trailhead)
        await sim.do(pat, "road")
        assert pat.location is road                 # dead-end ON_FAIL caught you
        tokens = [o for o in road.contents if o.has_tag("journeying")]
        assert len(tokens) == 1
        assert "set out" in text(sim, pat)
        sim.seen(pat)

        # A sweep while the eta is still in the future: progress, no arrival.
        await sim.engine.run_object_script(road_exit, "sweep")
        assert pat.location is road
        assert "road unrolls" in text(sim, pat)
        sim.seen(pat)

        # Age the token's eta into the past and sweep again: arrival.
        tokens[0].db.set("eta", 1)
        await sim.engine.run_object_script(road_exit, "sweep")
        assert pat.location is fort
        assert "you have arrived" in text(sim, pat)
        assert not [o for o in road.contents if o.has_tag("journeying")]

    async def test_turn_back_interrupts(self, sim):
        await build(sim, 161)
        trailhead = room(sim, "The Trailhead")
        road = room(sim, "The Long Road")
        pat = sim.player("Pat", location=trailhead)
        await sim.do(pat, "road")
        assert pat.location is road
        sim.seen(pat)
        await sim.do(pat, "turn back")
        assert pat.location is trailhead
        assert not [o for o in road.contents if o.has_tag("journeying")]


# --- 162. Tracking -------------------------------------------------------------


class TestTracking:

    async def test_footprints_read_by_skill_and_decay(self, sim):
        await build(sim, 162)
        clearing = room(sim, "The Clearing")
        thicket = room(sim, "The Thicket")

        vera = sim.player("Vera", location=clearing)
        await sim.do(vera, "thicket")
        assert vera.location is thicket
        prints = [o for o in clearing.contents if o.has_tag("footprint")]
        assert len(prints) == 1
        assert prints[0].db.get("quarry_name") == "Vera"

        skilled = sim.player("Ranger", location=clearing, skill_tracking=14)
        await sim.do(skilled, "track")
        assert "Vera passed" in text(sim, skilled)

        novice = sim.player("Novice", location=clearing, skill_tracking=6)
        await sim.do(novice, "track")
        assert "mean nothing to you" in text(sim, novice)

        # The trail fades: expire() destroys the print on the world tick.
        reaped = await reap_expired(sim.store, now=time.time() + 400)
        assert reaped >= 1
        assert not [o for o in clearing.contents if o.has_tag("footprint")]
        after = sim.player("Later", location=clearing, skill_tracking=14)
        await sim.do(after, "track")
        assert "unmarked" in text(sim, after)

    async def test_only_players_leave_tracks(self, sim):
        await build(sim, 162)
        clearing = room(sim, "The Clearing")
        thicket = room(sim, "The Thicket")
        # An NPC padding through leaves nothing (the master filters on player).
        from realm.core.movement import move_through_exit
        critter = sim.obj("a fox", location=clearing, tags=["npc"])
        await move_through_exit(critter, thicket, exit_obj=exit_in(clearing, "thicket"))
        assert not [o for o in clearing.contents if o.has_tag("footprint")]


# --- 163. Vehicle fuel ---------------------------------------------------------


class TestVehicleFuel:

    async def test_burns_fuel_warns_and_runs_dry(self, sim):
        await build(sim, 163)
        depot = room(sim, "The Depot")
        flats = room(sim, "The Flats")
        cab = room(sim, "The Rover")
        assert cab.db.get("fuel") == 2

        pat = sim.player("Pat", location=depot, credits=100)
        await sim.do(pat, "board")
        sim.seen(pat)

        await sim.do(pat, "drive north")           # 2 -> 1, low light
        out = text(sim, pat)
        assert "reads 1" in out
        assert "LOW FUEL" in out
        assert cab.db.get("fuel") == 1
        sim.seen(pat)

        await sim.do(pat, "drive south")           # 1 -> 0, back at depot
        assert cab.db.get("fuel") == 0
        assert cab.db.get("parked_at") == depot.id
        sim.seen(pat)

        await sim.do(pat, "drive north")           # dry: refused
        assert "tank is dry" in text(sim, pat)
        assert cab.db.get("parked_at") == depot.id

    async def test_refuel_by_payment_with_change(self, sim):
        await build(sim, 163)
        depot = room(sim, "The Depot")
        cab = room(sim, "The Rover")
        pump = objs(sim, "fuel pump")[0]
        pat = sim.player("Pat", location=depot, credits=100)

        # Drain the tank to zero (parked at depot the whole time here).
        await sim.do(pat, "board")
        await sim.do(pat, "drive north")
        await sim.do(pat, "drive south")
        await sim.do(pat, "hatch")
        assert pat.location is depot
        sim.seen(pat)

        await sim.do(pat, "pay 20 to fuel pump")   # 5 cr/unit -> 4 units
        assert "4 units aboard" in text(sim, pat)
        assert cab.db.get("fuel") == 4
        assert pat.db.get("credits") == 80

    async def test_overpaying_past_the_cap_refunds_the_difference(self, sim):
        """The pump reads the sum off the event (adata('amount')) and gives
        back what the tank had no room for."""
        await build(sim, 163)
        depot = room(sim, "The Depot")
        cab = room(sim, "The Rover")
        pat = sim.player("Pat", location=depot, credits=100)

        assert cab.db.get("fuel") == 2 and cab.db.get("fuel_max") == 6
        await sim.do(pat, "pay 50 to fuel pump")   # room for 4 units = 20 cr
        out = text(sim, pat)
        assert "4 units aboard, tank now 6." in out
        assert "Change: 30 cr." in out
        assert cab.db.get("fuel") == 6             # capped, not overfilled
        assert pat.db.get("credits") == 80         # 100 - 50 paid + 30 change

    async def test_pump_ignores_a_payment_made_to_something_else(self, sim):
        """ON_PAYMENT fires on every object in the room, not just the till
        that was paid — `target is me` is what tells them apart. Without the
        guard the pump would read the vending machine's amount and hand out
        free fuel."""
        await build(sim, 163)
        depot = room(sim, "The Depot")
        cab = room(sim, "The Rover")
        sim.obj("vending machine", location=depot)
        pat = sim.player("Pat", location=depot, credits=100)

        await sim.do(pat, "pay 50 to vending machine")
        assert cab.db.get("fuel") == 2             # tank untouched
        assert pat.db.get("credits") == 50         # and no change came back
        assert "units aboard" not in text(sim, pat)

    async def test_pump_refuses_when_rover_absent(self, sim):
        await build(sim, 163)
        depot = room(sim, "The Depot")
        flats = room(sim, "The Flats")
        cab = room(sim, "The Rover")
        # Drive the rover away, then a bystander pays the pump.
        pat = sim.player("Pat", location=depot, credits=100)
        await sim.do(pat, "board")
        await sim.do(pat, "drive north")
        assert cab.db.get("parked_at") == flats.id
        bystander = sim.player("By", location=depot, credits=50)
        await sim.do(bystander, "pay 10 to fuel pump")
        assert "not parked at the pump" in text(sim, bystander)
        assert bystander.db.get("credits") == 50   # credits returned


# --- 164. Small spaceship (capstone) -------------------------------------------


class TestSmallSpaceship:

    async def _built(self, sim):
        await build(sim, 164)
        return (room(sim, "Docking Bay Alpha"), room(sim, "Docking Bay Beta"),
                room(sim, "The Cockpit"), room(sim, "The Airlock"))

    def _faces(self, sim, air):
        cache = sim.store.get_cached
        inner = [cache(str(f).lstrip("#")) for f in air.db.get("inner_faces")]
        outer = [cache(str(f).lstrip("#")) for f in air.db.get("outer_faces")]
        return inner, outer

    async def test_build_starts_docked_boarding(self, sim):
        alpha, beta, cock, air = await self._built(sim)
        inner, outer = self._faces(sim, air)
        # Docked at Alpha, ready to board: inner sealed, outer open.
        assert all(f.has_tag("closed") for f in inner)
        assert all(not f.has_tag("closed") for f in outer)
        assert cock.db.get("state") == "docked"

    async def test_board_launch_fly_and_disembark(self, sim):
        alpha, beta, cock, air = await self._built(sim)

        pilot = sim.player("Pilot", location=alpha)
        # Board: outer ramp is open, cycle in to reach the cockpit.
        await sim.do(pilot, "ramp")
        assert pilot.location is air
        await sim.do(pilot, "cycle in")
        await sim.do(pilot, "hatch")
        assert pilot.location is cock
        sim.seen(pilot)

        await sim.do(pilot, "launch")
        assert "climbs into the black" in text(sim, pilot)
        assert cock.db.get("state") == "flying"
        sim.seen(pilot)

        await sim.do(pilot, "fly Docking Bay Beta")
        assert cock.db.get("state") == "docked"
        assert cock.db.get("site") == beta.id
        assert cock.db.get("fuel") == 2                 # a unit spent
        # The gangway travelled to the new berth.
        assert [o for o in objs(sim, "ramp")
                if o.has_tag("exit") and o.location is beta]

        # Disembark onto the new world.
        await sim.do(pilot, "hatch")
        assert pilot.location is air
        await sim.do(pilot, "cycle out")
        await sim.do(pilot, "ramp")
        assert pilot.location is beta

    async def test_cycle_never_opens_both_doors(self, sim):
        alpha, beta, cock, air = await self._built(sim)
        inner, outer = self._faces(sim, air)
        pilot = sim.player("Pilot", location=alpha)
        await sim.do(pilot, "ramp")

        await sim.do(pilot, "cycle in")
        assert all(not f.has_tag("closed") for f in inner)   # inner open
        assert all(f.has_tag("closed") for f in outer)       # outer sealed
        await sim.do(pilot, "cycle out")
        assert all(f.has_tag("closed") for f in inner)       # inner sealed
        assert all(not f.has_tag("closed") for f in outer)   # outer open
        # At no cycle instant are both doors open.

    async def test_launch_refused_with_an_outer_door_open(self, sim):
        alpha, beta, cock, air = await self._built(sim)
        pilot = sim.player("Pilot", location=alpha)
        # Reach the cockpit normally.
        await sim.do(pilot, "ramp")
        await sim.do(pilot, "cycle in")
        await sim.do(pilot, "hatch")
        assert pilot.location is cock
        # Simulate a stuck outer door and confirm launch's own seal-check bites.
        inner, outer = self._faces(sim, air)
        outer[0].remove_tag("closed")
        sim.seen(pilot)
        await sim.do(pilot, "launch")
        assert "outer door is open" in text(sim, pilot)
        assert cock.db.get("state") == "docked"
