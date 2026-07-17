"""
Showcase verification — Puzzles & Mechanisms (checklist items 209-218).

Verifies the standalone tutorials in docs/showcase/ (209_lever_combination.md
through 218_puzzle_reset.md) by driving a real in-process world —
realm.testing.Simulator wires the same store / propagation / scripting /
dispatcher stack a live GameServer does — with each tutorial's EXACT
command lines (raw input in, session output out).

The build transcripts are not duplicated here: ``build_lines()`` reads every
command line straight out of the tutorial's "Build it" fenced blocks and
``build()`` drives those through the dispatcher. The tests therefore execute
*what the doc says* — drift between doc and test is impossible rather than
merely detectable, so no sync test is needed.

Determinism:
- Checks (the `search` command in 216/217) run through a pluggable resolver
  that succeeds iff effective skill >= 10, margin = effective - 10 — the
  same convention as tests/test_heist.py / test_traps_devices.py. So a
  searcher at Observation 13 clears conceal_difficulty <= 3 and no more.
- `wait()` chains (the Simon flashes, the escape-room countdown) run on the
  Simulator's virtual clock: the builds set the beat/interval to 0 so a
  pumped `tick_waits()` fires the due waits immediately.
- `on_tick` (the shifting maze) is driven by `run_object_script(warden,
  'on_tick')` — exactly what the `script_ticker` behavior calls, run as the
  warden, deterministically.
- `prompt()` wizards (keypad, riddle-via-prompt, Simon, escape keypad)
  answer through the session's captured input handler.
- `ON_RESET` (218) is fired with `fire_event`, the event the `zone_reset`
  behavior raises when a zone is due and empty.
"""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker / zone_reset
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import fire_event
from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


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


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer wires the session manager at startup; the Simulator leaves
    # it to the test (prompt() needs it to find player sessions).
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


# --- Harness -------------------------------------------------------------------


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, re-pinning the
    deterministic resolver after each (a build's @reload would re-install
    the game's dice resolver — none of these builds do, but it's cheap
    insurance and matches the sibling suites)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build(sim, doc_name, **builder_attrs):
    """Run one tutorial's Build-it transcript — read live from its doc — as
    a builder standing in Limbo."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo, **builder_attrs)
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


async def answer(sim, player, line):
    """Answer a pending prompt() wizard with the player's next line."""
    session = sim.session(player)
    handler = session.input_handler
    assert handler is not None, "no prompt() is pending for this player"
    await handler(session, line)
    return text(sim, player)


async def drain_waits(sim, times=10):
    """Pump the virtual clock: fire every wait already due (beat/interval
    are zeroed in the tests that use this, so due == immediately)."""
    for _ in range(times):
        await sim.engine.tick_waits()


# --- 209. Lever combination ----------------------------------------------------


class TestLeverCombination:

    async def test_wrong_order_resets_right_order_opens(self, sim):
        await build(sim, "209_lever_combination.md")
        assert obj(sim, "vault gate").has_tag("closed")
        zeke = sim.player("Zeke", location=room(sim, "Reliquary Hall"))

        # The gate resists the obvious approach.
        await sim.do(zeke, "open vault gate")
        assert "no handle" in text(sim, zeke)

        # Wrong order buzzes and clears all progress.
        await sim.do(zeke, "pull crimson lever")
        await sim.do(zeke, "pull emerald lever")
        sim.seen(zeke)
        await sim.do(zeke, "pull azure lever")
        assert "buzzer blares" in text(sim, zeke)
        assert obj(sim, "vault gate").has_tag("closed")

        # crimson, azure, emerald opens it.
        await sim.do(zeke, "pull crimson lever")
        await sim.do(zeke, "pull azure lever")
        sim.seen(zeke)
        await sim.do(zeke, "pull emerald lever")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "vault gate").has_tag("closed")
        await sim.do(zeke, "vault gate")
        assert zeke.location is room(sim, "Inner Vault")

    async def test_decoy_and_unknown_levers(self, sim):
        await build(sim, "209_lever_combination.md")
        zeke = sim.player("Zeke", location=room(sim, "Reliquary Hall"))

        await sim.do(zeke, "pull ghost lever")
        assert "no such lever" in text(sim, zeke)

        # The amber decoy is never in a valid sequence.
        await sim.do(zeke, "pull crimson lever")
        await sim.do(zeke, "pull azure lever")
        sim.seen(zeke)
        await sim.do(zeke, "pull amber lever")
        assert "buzzer blares" in text(sim, zeke)
        assert obj(sim, "vault gate").has_tag("closed")


# --- 210. Keypad code ----------------------------------------------------------


class TestKeypadCode:

    async def test_code_gates_the_door(self, sim):
        await build(sim, "210_keypad_code.md")
        zeke = sim.player("Zeke", location=room(sim, "Fabrication Lab"))

        await sim.do(zeke, "open clean gate")
        assert "ENTER CODE" in text(sim, zeke)

        await sim.do(zeke, "enter code")
        assert "Enter access code:" in text(sim, zeke)
        out = await answer(sim, zeke, "0000")
        assert "ACCESS DENIED" in out
        assert obj(sim, "clean gate").has_tag("closed")

        await sim.do(zeke, "enter code")
        out = await answer(sim, zeke, "4815")
        assert "slides open" in out
        assert not obj(sim, "clean gate").has_tag("closed")
        await sim.do(zeke, "clean gate")
        assert zeke.location is room(sim, "The Cleanroom")

    async def test_code_is_secret_to_strangers(self, sim):
        await build(sim, "210_keypad_code.md")
        zeke = sim.player("Zeke", location=room(sim, "Fabrication Lab"))
        stolen, _err = await sim.eval(
            zeke, "result = get_attr(get('keypad'), 'code')")
        assert stolen is None


# --- 211. Riddle door ----------------------------------------------------------


class TestRiddleDoor:

    async def test_wrong_answer_stays_shut_fuzzy_answer_opens(self, sim):
        await build(sim, "211_riddle_door.md")
        zeke = sim.player("Zeke", location=room(sim, "The Sphinx Landing"))

        await sim.do(zeke, "answer a mountain")
        assert "unmoved" in text(sim, zeke)
        assert obj(sim, "sphinx arch").has_tag("closed")

        await sim.do(zeke, "answer An Echo!")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "sphinx arch").has_tag("closed")
        await sim.do(zeke, "sphinx arch")
        assert zeke.location is room(sim, "The Hidden Shrine")

    @pytest.mark.parametrize("phrasing", ["the echo", "ECHO", "voice"])
    async def test_phrasing_variants_all_pass(self, sim, phrasing):
        await build(sim, "211_riddle_door.md")
        zeke = sim.player("Zeke", location=room(sim, "The Sphinx Landing"))
        await sim.do(zeke, f"answer {phrasing}")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "sphinx arch").has_tag("closed")


# --- 212. Weight-plate puzzle --------------------------------------------------


class TestWeightPlate:

    async def test_both_plates_open_and_unload_recloses(self, sim):
        await build(sim, "212_weight_plate.md")
        chamber = room(sim, "The Trial Chamber")
        zeke = sim.player("Zeke", location=chamber)
        await sim.do(zeke, "get iron ingot")
        await sim.do(zeke, "get dried feather")

        await sim.do(zeke, "load iron ingot onto pressure plate")
        sim.seen(zeke)
        assert obj(sim, "prize gate").has_tag("closed")   # one plate isn't enough

        await sim.do(zeke, "load dried feather onto feather plate")
        assert "swings open" in text(sim, zeke)
        assert not obj(sim, "prize gate").has_tag("closed")
        await sim.do(zeke, "prize gate")
        assert zeke.location is room(sim, "The Prize Room")

        await sim.do(zeke, "chamber")
        sim.seen(zeke)
        await sim.do(zeke, "unload iron ingot from pressure plate")
        assert "slams shut" in text(sim, zeke)
        assert obj(sim, "prize gate").has_tag("closed")

    async def test_decoy_object_does_not_satisfy(self, sim):
        await build(sim, "212_weight_plate.md")
        chamber = room(sim, "The Trial Chamber")
        zeke = sim.player("Zeke", location=chamber)
        await sim.do(zeke, "get clay shard")
        await sim.do(zeke, "get dried feather")

        await sim.do(zeke, "load clay shard onto pressure plate")
        await sim.do(zeke, "load dried feather onto feather plate")
        sim.seen(zeke)
        assert obj(sim, "prize gate").has_tag("closed")   # shard is not heavy

        await sim.do(zeke, "get iron ingot")
        await sim.do(zeke, "load iron ingot onto pressure plate")
        assert "swings open" in text(sim, zeke)


# --- 213. Power routing puzzle -------------------------------------------------


class TestPowerRouting:

    async def test_route_to_solution_opens_and_break_reseals(self, sim):
        await build(sim, "213_power_routing.md")
        reactor = room(sim, "Reactor Control")
        zeke = sim.player("Zeke", location=reactor)

        await sim.do(zeke, "grid")
        assert "FAULT" in text(sim, zeke)

        await sim.do(zeke, "route 1 to backup")
        await sim.do(zeke, "route 3 to backup")
        assert "blast shield retracts" in text(sim, zeke)
        assert not obj(sim, "blast shield").has_tag("closed")
        await sim.do(zeke, "blast shield")
        assert zeke.location is room(sim, "The Core Bay")

        await sim.do(zeke, "reactor")
        sim.seen(zeke)
        await sim.do(zeke, "route 2 to backup")
        assert "blast shield drops" in text(sim, zeke)
        assert obj(sim, "blast shield").has_tag("closed")

    async def test_grid_readout_reflects_state(self, sim):
        await build(sim, "213_power_routing.md")
        zeke = sim.player("Zeke", location=room(sim, "Reactor Control"))
        await sim.do(zeke, "route 1 to backup")
        sim.seen(zeke)
        await sim.do(zeke, "grid")
        out = text(sim, zeke)
        assert "Junction 1: BACKUP bus" in out
        assert "Junction 2: MAIN bus" in out
        assert "GRID STATUS: FAULT" in out


# --- 214. Simon sequence -------------------------------------------------------


class TestSimon:

    async def test_full_sequence_opens_hatch(self, sim):
        builder = await build(sim, "214_simon.md")
        await run_lines(sim, builder, ["@set simon panel/beat = 0"])
        zeke = sim.player("Zeke", location=room(sim, "The Signal Chamber"))

        await sim.do(zeke, "play simon")
        await drain_waits(sim)
        assert "The panel flashes RED." in text(sim, zeke)

        await answer(sim, zeke, "red")
        await drain_waits(sim)
        await answer(sim, zeke, "red green")
        await drain_waits(sim)
        await answer(sim, zeke, "red green blue")
        await drain_waits(sim)
        out = await answer(sim, zeke, "red green blue amber")
        assert "vault hatch clicks open" in out
        assert not obj(sim, "vault hatch").has_tag("closed")
        await sim.do(zeke, "vault hatch")
        assert zeke.location is room(sim, "The Sealed Cache")

    async def test_wrong_echo_ends_the_run(self, sim):
        builder = await build(sim, "214_simon.md")
        await run_lines(sim, builder, ["@set simon panel/beat = 0"])
        zeke = sim.player("Zeke", location=room(sim, "The Signal Chamber"))

        await sim.do(zeke, "play simon")
        await drain_waits(sim)
        out = await answer(sim, zeke, "green")
        assert "goes dark" in out
        assert obj(sim, "vault hatch").has_tag("closed")
        assert not obj(sim, "simon panel").db.get("busy")


# --- 215. Shifting maze --------------------------------------------------------


class TestShiftingMaze:

    async def test_arch_cycles_through_the_pool(self, sim):
        await build(sim, "215_shifting_maze.md")
        warden = obj(sim, "maze warden")
        arch = obj(sim, "shifting arch")
        echoes = room(sim, "Chamber of Echoes")
        dust = room(sim, "Chamber of Dust")
        wayout = room(sim, "The Way Out")

        assert arch.db.get("destination") == echoes.id
        await sim.engine.run_object_script(warden, "on_tick")
        assert arch.db.get("destination") == dust.id
        await sim.engine.run_object_script(warden, "on_tick")
        assert arch.db.get("destination") == wayout.id    # the goal is in the pool
        await sim.engine.run_object_script(warden, "on_tick")
        assert arch.db.get("destination") == echoes.id    # and it wraps

    async def test_traversal_back_exits_and_escape(self, sim):
        await build(sim, "215_shifting_maze.md")
        entrance = room(sim, "Maze Entrance")
        warden = obj(sim, "maze warden")
        zeke = sim.player("Zeke", location=entrance)

        await sim.do(zeke, "shifting arch")
        assert zeke.location is room(sim, "Chamber of Echoes")
        await sim.do(zeke, "back")
        assert zeke.location is entrance         # no dead ends

        # Aim the arch at the exit and walk out — always reachable.
        await sim.engine.run_object_script(warden, "on_tick")   # -> Dust
        await sim.engine.run_object_script(warden, "on_tick")   # -> The Way Out
        await sim.do(zeke, "shifting arch")
        assert zeke.location is room(sim, "The Way Out")
        await sim.do(zeke, "leave")
        assert zeke.location is room(sim, "Limbo")


# --- 216. Escape room ----------------------------------------------------------


ZERO_THE_CLOCK = [
    "@teleport me = Holding Cell",
    "@set here/beat = 0",
    "@teleport me = Escape Lobby",
]


class TestEscapeRoom:

    async def test_search_then_code_then_escape(self, sim):
        builder = await build(sim, "216_escape_room.md")
        await run_lines(sim, builder, ZERO_THE_CLOCK)
        lobby = room(sim, "Escape Lobby")
        alice = sim.player("Alice", location=lobby, skill_observation=14)

        await sim.do(alice, "cell door")
        assert alice.location.has_tag("instance_entry")
        assert "klaxon wails" in text(sim, alice)

        await sim.do(alice, "search")
        assert "7291" in text(sim, alice)

        await sim.do(alice, "punch")
        out = await answer(sim, alice, "0000")
        assert "flashes red" in out

        await sim.do(alice, "punch")
        out = await answer(sim, alice, "7291")
        assert "escape hatch unbolts" in out
        await sim.do(alice, "escape hatch")
        assert alice.location is lobby

    async def test_private_copies_and_the_flood(self, sim):
        builder = await build(sim, "216_escape_room.md")
        await run_lines(sim, builder, ZERO_THE_CLOCK)
        lobby = room(sim, "Escape Lobby")
        alice = sim.player("Alice", location=lobby, skill_observation=14)
        cass = sim.player("Cass", location=lobby, skill_observation=14)

        await sim.do(alice, "cell door")
        await sim.do(cass, "cell door")
        # Each party gets a private copy — reset by construction.
        assert alice.location is not cass.location
        assert alice.location.has_tag(f"instance:cell:{alice.id}")
        assert cass.location.has_tag(f"instance:cell:{cass.id}")

        # The countdown floods the cell on its own timer.
        sim.seen(cass)
        await drain_waits(sim)
        assert "TIME UP" in text(sim, cass)


# --- 217. Hidden object search -------------------------------------------------


class TestHiddenObjectSearch:

    async def test_layered_finds_by_skill(self, sim):
        await build(sim, "217_hidden_object_search.md")
        study = room(sim, "The Study")
        scout = sim.player("Scout", location=study, skill_observation=13)

        await sim.do(scout, "search")
        out = text(sim, scout)
        assert "brass key" in out
        assert "leather ledger" in out
        assert not obj(sim, "brass key").has_tag("invisible")
        assert not obj(sim, "leather ledger").has_tag("invisible")
        # The master-concealed cache is beyond Observation 13.
        assert obj(sim, "wall cache").has_tag("invisible")

    async def test_expert_clears_the_room_and_finds_are_real(self, sim):
        await build(sim, "217_hidden_object_search.md")
        study = room(sim, "The Study")
        expert = sim.player("Ada", location=study, skill_observation=16)

        await sim.do(expert, "search")
        assert not obj(sim, "wall cache").has_tag("invisible")
        await sim.do(expert, "get wall cache")
        assert obj(sim, "wall cache").location is expert


# --- 218. Puzzle reset engineering ---------------------------------------------


class TestPuzzleReset:

    async def test_solve_manual_reset_and_stuck_recovery(self, sim):
        await build(sim, "218_puzzle_reset.md")
        trial = room(sim, "The Trial Room")
        zeke = sim.player("Zeke", location=trial)

        await sim.do(zeke, "crank")
        assert "grinds open" in text(sim, zeke)
        assert not obj(sim, "trial gate").has_tag("closed")

        await sim.do(zeke, "reset puzzle")
        assert "re-seals" in text(sim, zeke)
        assert obj(sim, "trial gate").has_tag("closed")
        assert obj(sim, "puzzle console").db.get("progress") is None

        # Stuck state: someone walks off with the crank.
        await sim.do(zeke, "get brass crank")
        cass = sim.player("Cass", location=trial)
        await sim.do(cass, "crank")
        assert "no crank here" in text(sim, cass)

        # Reset re-creates the missing prop — the puzzle can't be bricked.
        await sim.do(cass, "reset puzzle")
        cranks = [o for o in trial.contents if o.has_tag("crank")]
        assert len(cranks) == 1
        await sim.do(cass, "crank")
        assert "grinds open" in text(sim, cass)

    async def test_on_reset_restores_the_puzzle(self, sim):
        await build(sim, "218_puzzle_reset.md")
        trial = room(sim, "The Trial Room")
        console = obj(sim, "puzzle console")
        zeke = sim.player("Zeke", location=trial)

        await sim.do(zeke, "crank")
        assert not obj(sim, "trial gate").has_tag("closed")

        # zone_reset fires this ON_RESET when the zone is due and empty.
        await fire_event(None, console, "event:on_reset")
        assert obj(sim, "trial gate").has_tag("closed")
        assert console.db.get("progress") is None
