"""
Showcase verification — the Heist arc (docs/showcase/arc_heist.md).

Items: 27 secret door, 16 combination safe, 49 landmine, 54 security
camera & monitor, 48 gas bomb, 160 sneaking.

Every command line in each tutorial's "Build it" section is read
straight out of its markdown (docs/showcase/NNN_*.md) and driven
through the real dispatcher (raw input in -> session output out) by a
builder player — so a doc edit that breaks the build breaks this suite.
The plays then exercise the tutorials' "Try it" flows and assert
outcomes.

Dice are removed via the pluggable check resolver (same convention as
tests/test_infiltration.py): a check succeeds iff effective skill >= 10,
margin = effective - 10, so contests go to the higher skill. The @reload
line inside the gas-bomb build re-installs the GURPS resolver, so the
line runner re-pins the deterministic resolver after every command.
"""

from __future__ import annotations

from pathlib import Path
import re
import time
from types import SimpleNamespace

import pytest

from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.events import reap_expired
from realm.core.perception import stealth_observer
from realm.core.propagation import get_engine as get_propagation_engine
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


# --- Build transcripts, read from the tutorials --------------------------------

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_FOR = {
    27: "027_secret_door.md",
    16: "016_combination_safe.md",
    49: "049_landmine.md",
    54: "054_security_camera.md",
    48: "048_gas_bomb.md",
    160: "160_sneaking.md",
}
ARC_ORDER = [27, 16, 49, 54, 48, 160]


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks.

    The suite executes what the doc SAYS to type. There is nothing to
    keep in sync — a build that regresses here regressed in the tutorial.
    """
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
    "can't", "don't", "No permission",
)


# --- Harness -------------------------------------------------------------------


@pytest.fixture
def sim():
    simulator = Simulator()
    set_check_resolver(level_resolver)
    # GameServer registers these at startup; the Simulator leaves wiring
    # to the test (same seams, same objects).
    get_propagation_engine().add_observer(stealth_observer)
    simulator.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(simulator._sessions.values()))
    yield simulator
    set_check_resolver(None)
    simulator.close()


async def run_lines(sim, player, lines):
    """Drive raw command lines through the dispatcher, keeping the
    deterministic resolver pinned (the build's @reload re-installs the
    GURPS dice resolver)."""
    for line in lines:
        await sim.do(player, line)
        set_check_resolver(level_resolver)


async def build_heist(sim, upto=160):
    """Run the arc's build transcripts, in tutorial order, as a builder."""
    limbo = sim.room("Limbo")
    builder = sim.player("Bob", location=limbo)
    builder.add_tag("builder")
    for item in ARC_ORDER:
        await run_lines(sim, builder, build_lines(DOC_FOR[item]))
        out = "\n".join(sim.seen(builder))
        for flag in BUILD_RED_FLAGS:
            assert flag not in out, (
                f"build stage {item} tripped {flag!r}:\n{out}")
        if item == upto:
            break
    return builder


def room(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no room named {name!r}"
    return matches[0]


def obj(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r}"
    return matches[0]


def text(sim, player):
    return "\n".join(sim.seen(player))


async def sweep_mine(sim, builder):
    """Play convenience: the crew swept the antechamber mine earlier."""
    await run_lines(sim, builder, ["@set anti-personnel mine/armed = 0"])
    sim.seen(builder)


# --- 27. Secret door -------------------------------------------------------------


class TestSecretDoor:

    async def test_search_reveals_and_grate_is_walkable(self, sim):
        builder = await build_heist(sim, upto=27)
        office = room(sim, "The Security Office")
        raven = sim.player("Raven", location=office,
                           skill_observation=13, skill_stealth=12,
                           hp=13, max_hp=13, health=12)

        await sim.do(raven, "east")
        out = text(sim, raven)
        # Passive glance is at -4: obs 13 -> 9, no reveal on entry.
        assert "crawlway yawns" not in out
        assert "loose grate" not in out          # hidden from the room display

        await sim.do(raven, "search")
        out = text(sim, raven)
        # Deliberate search rolls at -conceal_difficulty (-2): 11 >= 10.
        assert "One grate sits loose in its frame" in out
        assert not obj(sim, "loose grate").has_tag("invisible")

        # Revealed, the grate shows up in the exits line...
        await sim.do(raven, "look")
        assert "loose grate" in text(sim, raven)

        # ...and walks like any exit.
        await sim.do(raven, "loose grate")
        assert raven.location is room(sim, "Vault Antechamber")
        await sim.do(raven, "duct")
        assert raven.location is room(sim, "Maintenance Corridor")

    async def test_sharp_eyes_spot_it_passively_on_entry(self, sim):
        builder = await build_heist(sim, upto=27)
        office = room(sim, "The Security Office")
        hawk = sim.player("Hawk", location=office, skill_observation=14)

        await sim.do(hawk, "east")
        # The corridor's on_enter check: obs 14 - 4 = 10 -> revealed.
        assert "One grate sits loose in its frame" in text(sim, hawk)
        assert not obj(sim, "loose grate").has_tag("invisible")

    async def test_hidden_exit_traversable_by_name_for_those_in_the_know(self, sim):
        builder = await build_heist(sim, upto=27)
        corridor = room(sim, "Maintenance Corridor")
        mook = sim.player("Mook", location=corridor)  # no skills at all

        assert obj(sim, "loose grate").has_tag("invisible")
        await sim.do(mook, "loose grate")
        assert mook.location is room(sim, "Vault Antechamber")


# --- 16. Combination safe ----------------------------------------------------------


class TestCombinationSafe:

    async def test_dial_wrong_then_right_and_loot(self, sim):
        builder = await build_heist(sim, upto=16)
        vault = room(sim, "Nexagen Vault")
        raven = sim.player("Raven", location=vault)

        await sim.do(raven, "open wall safe")
        assert "doesn't budge" in text(sim, raven)

        # A wrong full sequence resets silently -- no digit-by-digit oracle.
        for line in ("dial 1", "dial 2"):
            await sim.do(raven, line)
        assert text(sim, raven).count("Click.") == 2
        await sim.do(raven, "dial 3")
        assert "spins back to zero" in text(sim, raven)
        assert obj(sim, "wall safe").has_tag("locked")

        for line in ("dial 17", "dial 4"):
            await sim.do(raven, line)
        sim.seen(raven)
        await sim.do(raven, "dial 33")
        assert "the wall safe unlocks" in text(sim, raven)
        assert not obj(sim, "wall safe").has_tag("locked")

        await sim.do(raven, "open wall safe")
        await sim.do(raven, "get prototype schematics from wall safe")
        assert obj(sim, "prototype schematics").location is raven

    async def test_lockpicking_is_a_valid_alternate_route(self, sim):
        builder = await build_heist(sim, upto=16)
        vault = room(sim, "Nexagen Vault")
        sly = sim.player("Sly", location=vault, skill_lockpicking=14)

        # Improvised (no lockpicks): 14 - 4 - 5 = 5 < 10.
        await sim.do(sly, "pick wall safe")
        assert "resists" in text(sim, sly)
        assert obj(sim, "wall safe").has_tag("locked")

        # With tools: 14 - 4 = 10.
        sim.obj("lockpick set", location=sly, tags=["thing", "lockpicks"])
        await sim.do(sly, "pick wall safe")
        assert "defeat the lock" in text(sim, sly)
        assert not obj(sim, "wall safe").has_tag("locked")

    async def test_owner_resets_code_via_prompt_and_secret_flag_hides_it(self, sim):
        builder = await build_heist(sim, upto=16)
        vault = room(sim, "Nexagen Vault")
        raven = sim.player("Raven", location=vault)
        safe = obj(sim, "wall safe")

        # Not the owner: refused outright.
        await sim.do(raven, "setcode")
        assert "Only the owner may reset the dial." in text(sim, raven)

        # The owner, but through a closed door: refused.
        await sim.do(builder, "@teleport me = Nexagen Vault")
        sim.seen(builder)
        await sim.do(builder, "setcode")
        assert "Open the safe first" in text(sim, builder)

        # Open it (dial the code), then the prompt wizard fires.
        for line in ("dial 17", "dial 4", "dial 33", "open wall safe"):
            await sim.do(builder, line)
        sim.seen(builder)
        await sim.do(builder, "setcode")
        assert "New combination" in text(sim, builder)
        handler = sim.session(builder).input_handler
        assert handler is not None, "prompt() should capture the next line"
        await handler(sim.session(builder), "5 25 45")
        assert "New combination: 5 25 45" in text(sim, builder)

        # Old code is dead; the new one opens it.
        await run_lines(sim, builder, ["close wall safe",
                                       "@tag wall safe = locked"])
        for line in ("dial 17", "dial 4", "dial 33"):
            await sim.do(raven, line)
        assert obj(sim, "wall safe").has_tag("locked")
        for line in ("dial 5", "dial 25", "dial 45"):
            await sim.do(raven, line)
        assert not obj(sim, "wall safe").has_tag("locked")

        # The secret attr flag: a stranger's softcode reads nothing,
        # the safe's owner still reads it.
        stolen, _err = await sim.eval(raven, "result = get_attr(get('wall safe'), 'code')")
        assert stolen is None
        own, _err = await sim.eval(builder, "result = get_attr(get('wall safe'), 'code')")
        assert own == "5 25 45"


# --- 49. Landmine -------------------------------------------------------------------


class TestLandmine:

    async def test_sharp_eyes_freeze_midstep_and_ward_blocks_pickup(self, sim):
        builder = await build_heist(sim, upto=49)
        corridor = room(sim, "Maintenance Corridor")
        hawk = sim.player("Hawk", location=corridor,
                          skill_observation=14, hp=13, max_hp=13)

        await sim.do(hawk, "loose grate")   # hidden exits walk by name
        out = text(sim, hawk)
        # contest: obs 14 (margin 4) beats concealment 13 (margin 3).
        assert "You freeze mid-step" in out
        assert hawk.db.get("hp") == 13
        mine = obj(sim, "anti-personnel mine")
        assert not mine.has_tag("invisible")
        assert mine.db.get("armed") == 1

        # Spotted is not safe to pocket: the on_check ward vetoes the get.
        await sim.do(hawk, "get anti-personnel mine")
        assert "wedged into the floor" in text(sim, hawk)
        assert mine.location is room(sim, "Vault Antechamber")

        # Known mines are walked around.
        await sim.do(hawk, "duct")
        sim.seen(hawk)
        await sim.do(hawk, "loose grate")
        assert "You step around the exposed mine." in text(sim, hawk)

    async def test_dull_eyes_detonate_it(self, sim):
        builder = await build_heist(sim, upto=49)
        corridor = room(sim, "Maintenance Corridor")
        mook = sim.player("Mook", location=corridor,
                          skill_observation=6, hp=13, max_hp=13)
        witness = sim.player("Witness", location=room(sim, "Vault Antechamber"),
                             skill_observation=14, hp=13, max_hp=13)
        sim.seen(witness)

        await sim.do(mook, "loose grate")
        out = text(sim, mook)
        assert "KA-WHUMP!" in out
        assert mook.db.get("hp") < 13                      # 2d6 landed
        assert "Mook sets off a buried mine!" in text(sim, witness)
        mine = obj(sim, "anti-personnel mine")
        assert mine.db.get("armed") == 0                   # spent
        assert not mine.has_tag("invisible")               # and exposed

    async def test_search_finds_it_before_you_step_on_it(self, sim):
        builder = await build_heist(sim, upto=49)
        antechamber = room(sim, "Vault Antechamber")
        raven = sim.player("Raven", location=antechamber, skill_observation=13)

        await sim.do(raven, "search")
        # Flat observation vs conceal_difficulty 3: 13 - 3 = 10.
        assert "a pressure plate, wired and live!" in text(sim, raven)
        assert not obj(sim, "anti-personnel mine").has_tag("invisible")


# --- 54. Security camera & monitor ---------------------------------------------------


class TestSecurityCamera:

    async def test_watch_relays_speech_and_movement_until_unwatch(self, sim):
        builder = await build_heist(sim, upto=54)
        await sweep_mine(sim, builder)
        office = room(sim, "The Security Office")
        antechamber = room(sim, "Vault Antechamber")
        raven = sim.player("Raven", location=office)
        zeke = sim.player("Zeke", location=antechamber)

        await sim.do(raven, "watch")
        assert "You settle in at the console" in text(sim, raven)

        await sim.do(zeke, "say psst")
        assert '[security camera] Zeke says, "psst"' in text(sim, raven)

        await sim.do(zeke, "duct")
        out = text(sim, raven)
        assert out.count("[security camera] Zeke leaves.") == 1
        await sim.do(zeke, "loose grate")
        out = text(sim, raven)
        assert out.count("[security camera] Zeke arrives.") == 1

        await sim.do(raven, "unwatch")
        sim.seen(raven)
        await sim.do(zeke, "say anyone there?")
        assert "[security camera]" not in text(sim, raven)

    async def test_walking_away_prunes_and_cutting_kills_the_feed(self, sim):
        builder = await build_heist(sim, upto=54)
        await sweep_mine(sim, builder)
        office = room(sim, "The Security Office")
        antechamber = room(sim, "Vault Antechamber")
        raven = sim.player("Raven", location=office)
        sly = sim.player("Sly", location=antechamber, skill_electronics=12)

        await sim.do(raven, "watch")
        # Wander off: the next relay only reaches watchers still at the
        # console, and the stale subscription is pruned.
        await sim.do(raven, "east")
        sim.seen(raven)
        await sim.do(sly, "say all clear")
        assert "[security camera]" not in text(sim, raven)
        assert obj(sim, "security monitor").db.get("watchers") == []

        # Sabotage: electronics 12 - 2 = 10 cuts the power.
        await sim.do(sly, "cut camera")
        assert "the camera light dies" in text(sim, sly)
        assert obj(sim, "security camera").db.get("powered") == 0

        # Even a fresh watcher gets nothing from a dead camera.
        await sim.do(raven, "west")
        await sim.do(raven, "watch")
        sim.seen(raven)
        await sim.do(sly, "say still watching?")
        assert "[security camera]" not in text(sim, raven)


# --- 48. Gas bomb --------------------------------------------------------------------


class TestGasBomb:

    async def test_arm_spread_resist_linger_and_dissipate(self, sim):
        builder = await build_heist(sim, upto=48)
        await sweep_mine(sim, builder)
        # Stage the demo: vault door shut (closed doors hold gas back),
        # and a zero-second fuse so the test needn't sleep.
        await run_lines(sim, builder, [
            "@teleport me = Vault Antechamber",
            "close vault door",
            "@set gas bomb/fuse = 0",
        ])

        corridor = room(sim, "Maintenance Corridor")
        antechamber = room(sim, "Vault Antechamber")
        office = room(sim, "The Security Office")
        vault = room(sim, "Nexagen Vault")

        raven = sim.player("Raven", location=corridor,
                           hp=13, max_hp=13, health=12)   # fortitude 12-1=11: resists
        mook = sim.player("Mook", location=antechamber,
                          hp=13, max_hp=13, health=8)     # fortitude 8-1=7: chokes

        # Arming it in your hands is refused.
        await sim.do(raven, "get gas bomb")
        await sim.do(raven, "arm bomb")
        assert "Set it down first" in text(sim, raven)

        # Carry it downstairs, set it, arm it, run.
        await sim.do(raven, "loose grate")
        await sim.do(raven, "drop gas bomb")
        sim.seen(raven)
        sim.seen(mook)
        await sim.do(raven, "arm bomb")
        assert "twists the fuse cap" in text(sim, mook)
        await sim.do(raven, "duct")
        await sim.do(raven, "west")
        assert raven.location is office

        # The fuse is a wait(): fire it.
        await sim.engine.tick_waits()

        clouds = sim.store.find_cached(name="a cloud of stinging gas")
        cloud_rooms = {c.location for c in clouds}
        assert antechamber in cloud_rooms          # ground zero
        assert corridor in cloud_rooms             # up the open duct
        assert vault not in cloud_rooms            # closed door holds it
        assert office not in cloud_rooms           # not adjacent
        assert len(clouds) == 2
        assert sim.store.find_cached(name="gas bomb") == [], \
            "the bomb should be destroyed"
        assert "A thick bank of stinging gas billows in!" in text(sim, mook)

        # Exposure runs on the cloud's ticker: HT-based fortitude roll.
        for cloud in clouds:
            for behavior in cloud.get_behaviors():
                await behavior.tick(cloud, 4.0)
        assert "The gas sears your lungs!" in text(sim, mook)
        assert mook.db.get("hp") < 13
        assert raven.db.get("hp") == 13            # safe in the office

        # A latecomer wading in is warned by the cloud's ON_ENTER.
        await sim.do(raven, "east")
        assert "Stinging yellow gas fills this room!" in text(sim, raven)

        # Dissipation is expire(): the world tick reaps the clouds.
        reaped = await reap_expired(sim.store, now=time.time() + 120)
        assert reaped == 2
        assert sim.store.find_cached(name="a cloud of stinging gas") == []


# --- 160. Sneaking -------------------------------------------------------------------


class TestSneaking:

    async def test_visible_arrivals_are_challenged(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        antechamber = room(sim, "Vault Antechamber")
        hawk = sim.player("Hawk", location=antechamber, skill_observation=16)

        await sim.do(hawk, "vault door")
        assert 'Vault Sentry says, "This wing is off limits."' in text(sim, hawk)

    async def test_creaky_floor_alerts_the_sentry_who_then_spots_you(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        antechamber = room(sim, "Vault Antechamber")
        vault = room(sim, "Nexagen Vault")
        sentry = obj(sim, "Vault Sentry")
        hawk = sim.player("Hawk", location=vault, skill_observation=16)
        shade = sim.player("Shade", location=antechamber, skill_stealth=12)
        sim.seen(hawk)

        await sim.do(shade, "hide")
        assert "You slip out of sight." in text(sim, shade)

        # First pass: stealth 12 ties the sentry's observation 12 -- ties
        # go to the hider -- but the floorboard check at -3 fails: creak.
        await sim.do(shade, "vault door")
        assert shade.has_tag("hidden")
        out = text(sim, hawk)
        assert "Someone arrives." in out           # who, not that, is hidden
        assert "A floorboard creaks sharply!" in out
        assert 'Vault Sentry says, "Who goes there?"' in out
        assert int(sentry.db.get("alert_level") or 0) == 1

        # Second pass: the alerted sentry (obs 12 + 1) wins the contest.
        await sim.do(shade, "antechamber")
        sim.seen(shade)
        await sim.do(shade, "vault door")
        assert not shade.has_tag("hidden")
        out = text(sim, shade)
        assert "Vault Sentry spots you!" in out
        assert int(sentry.db.get("alert_level") or 0) == 2

    async def test_master_sneak_slips_in_but_speaking_gives_you_away(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        antechamber = room(sim, "Vault Antechamber")
        vault = room(sim, "Nexagen Vault")
        hawk = sim.player("Hawk", location=vault, skill_observation=16)
        wraith = sim.player("Wraith", location=antechamber, skill_stealth=15)

        await sim.do(wraith, "hide")
        sim.seen(hawk)
        await sim.do(wraith, "vault door")
        out = text(sim, wraith)
        assert wraith.has_tag("hidden")            # sentry misses margin 5
        assert "You cross the boards without a sound." in out
        assert "spots you" not in out
        # Hidden actors are unnamed in what bystanders see.
        assert "Wraith" not in text(sim, hawk)

        # Loud actions break stealth (the engine's stealth observer).
        await sim.do(wraith, "say the vault is ours")
        assert "Your action gives you away!" in text(sim, wraith)
        assert not wraith.has_tag("hidden")

    async def test_search_contests_a_hiders_stealth(self, sim):
        builder = await build_heist(sim, upto=160)
        await sweep_mine(sim, builder)
        vault = room(sim, "Nexagen Vault")
        hawk = sim.player("Hawk", location=vault, skill_observation=16)
        wraith = sim.player("Wraith", location=vault, skill_stealth=15)

        await sim.do(wraith, "hide")
        assert wraith.has_tag("hidden")
        sim.seen(wraith)

        await sim.do(hawk, "search")               # obs 16 vs stealth 15
        assert not wraith.has_tag("hidden")
        assert "Hawk spots you!" in text(sim, wraith)
