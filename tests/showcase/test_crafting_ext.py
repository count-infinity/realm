"""
Showcase "Crafting & Resources" — checklist items 121-131.

Verifies the standalone tutorials in docs/showcase/ (121_gathering_nodes.md,
122_recipe_crafting.md, 123_refining_chain.md, 124_salvage.md,
125_quality_tiers.md, 126_blueprints.md, 127_crafting_stations.md,
128_farming.md, 129_cooking_buffs.md, 130_fishing.md,
131_chemistry_poisons.md) by driving a real in-process world —
realm.testing.Simulator wires the same store/propagation/scripting/
dispatcher stack a live GameServer does — with the tutorials' EXACT
command lines (raw input in, session output out).

Every command line in each tutorial's "Build it" section is read
straight out of its markdown and driven through the real dispatcher, so
the tests execute what the docs actually say — a doc edit that breaks a
build breaks this suite, and there is nothing left to drift.
Time and dice are deterministic: script_ticker scripts fire via
`@tr <obj>/on_tick`, wait() chains via engine.tick_waits() after
zeroing the lull/window attributes (the music-box trick), beat-driven
effects via deliver_beat(), and every die roll is pinned by
monkeypatching the two random sources (realm.core.dice for
roll()/skill_check, realm.scripting.functions for rand()).
"""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import realm.behaviors  # noqa: F401 — registers script_ticker + effects
from realm.core.beats import deliver_beat
from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript —
# catches typos, permission problems, and validation failures in any
# tutorial line.
BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
)

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


@pytest.fixture
def sim():
    s = Simulator()
    # prompt()/session plumbing, wired exactly as the other suites do.
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def pinned_dice(monkeypatch):
    """Pin the resolution dice: every die in roll('3d6') / skill_check
    comes up holder['value'] (clamped to the die's range)."""
    holder = {"value": 3}

    def fake_randint(low, high):
        return max(low, min(holder["value"], high))

    monkeypatch.setattr("realm.core.dice.random.randint", fake_randint)
    return holder


def workshop_and_builder(sim):
    """The standing start of every tutorial: a room and a builder in it."""
    room = sim.room("The Workshop")
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    return room, bilda


def workshop_and_admin(sim):
    """126/131 build as an ADMIN — their masters write player sheets."""
    room = sim.room("The Workshop")
    vala = sim.player("Vala", location=room)
    vala.add_tag("admin")
    return room, vala


async def build(sim, player, lines):
    """Run a Build-it transcript; fail loudly if any line misfires."""
    for line in lines:
        await sim.do(player, line)
        out = "\n".join(sim.seen(player))
        for marker in BUILD_FAILURE_MARKERS:
            assert marker not in out, f"build line {line!r} failed: {out!r}"


async def do(sim, player, line):
    """Run one command and return everything the player saw."""
    await sim.do(player, line)
    return sim.seen(player)


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


def find_all(sim, name):
    return sim.store.find_cached(name=name)


def text(out):
    return "\n".join(out)


# =========================================================================
# 121. Gathering nodes — docs/showcase/121_gathering_nodes.md
# =========================================================================

BUILD_121 = build_lines("121_gathering_nodes.md")


class TestGatheringNodes:

    async def test_margin_yield_depletion_and_regrowth(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_121)
        await build(sim, bilda, ["@set me/skill_prospecting = 12"])
        vein = find_one(sim, "balthite vein")

        # Margin 6 (roll 6 vs 12): yield 1 + 6//3 = 3 chunks.
        pinned_dice["value"] = 2
        out = await do(sim, bilda, "mine vein")
        assert "3 chunk(s) of balthite clatter free." in text(out)
        assert len(find_all(sim, "a chunk of balthite ore")) == 3
        assert vein.db.get("ore_left") == 1

        # A blown roll quotes the dice and takes nothing.
        pinned_dice["value"] = 6
        out = await do(sim, bilda, "mine vein")
        assert "Sparks, dust, no ore. (rolled 18 vs prospecting 12)" in text(out)
        assert vein.db.get("ore_left") == 1

        # The last chunk comes loose and the seam goes dark.
        pinned_dice["value"] = 2
        out = await do(sim, bilda, "mine vein")
        assert "1 chunk(s) of balthite clatter free." in text(out)
        assert "The seam splits and goes dark, spent." in text(out)
        assert vein.db.get("ore_left") == 0
        assert vein.db.get("regrow_left") == 3

        # Bare rock refuses, and look reads the gauge.
        out = await do(sim, bilda, "mine vein")
        assert ("The vein is hacked bare. Rock heals on its own clock; "
                "come back later." in text(out))
        out = await do(sim, bilda, "look balthite vein")
        assert "hacked bare" in text(out)

        # Three regrowth ticks refill from ore_cap.
        await do(sim, bilda, "@tr balthite vein/on_tick")
        await do(sim, bilda, "@tr balthite vein/on_tick")
        assert vein.db.get("ore_left") == 0
        out = await do(sim, bilda, "@tr balthite vein/on_tick")
        assert ("Fresh balthite creeps glittering back across the rock "
                "face." in text(out))
        assert vein.db.get("ore_left") == 4
        out = await do(sim, bilda, "look balthite vein")
        assert "It glitters, thick with ore." in text(out)


# =========================================================================
# 122. Recipe crafting — docs/showcase/122_recipe_crafting.md
# =========================================================================

BUILD_122 = build_lines("122_recipe_crafting.md")

STOCK_122 = [
    "@set me/skill_machining = 11",
    "@eval (create_obj('a duralloy ingot', ['thing', 'ingot'], me), create_obj('a silicone gasket', ['thing', 'gasket'], me))",
]


class TestRecipeCrafting:

    async def test_jobs_craft_and_consume(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_122)
        await build(sim, bilda, STOCK_122)

        out = await do(sim, bilda, "jobs")
        assert ("valve -> a machined pressure valve (needs: 1x ingot, "
                "1x gasket)" in text(out))

        pinned_dice["value"] = 3   # roll 9 vs 11: margin +2
        out = await do(sim, bilda, "craft valve")
        assert ("works the bench -- a machined pressure valve drops into "
                "the tray. (margin +2)" in text(out))
        assert find_all(sim, "a machined pressure valve")
        assert not find_all(sim, "a duralloy ingot")       # consumed
        assert not find_all(sim, "a silicone gasket")

    async def test_guards_and_costly_failure(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_122)

        out = await do(sim, bilda, "craft widget")
        assert "The job card lists no such assembly. Try jobs." in text(out)
        out = await do(sim, bilda, "craft valve")
        assert "Short of materials: 1x ingot, 1x gasket." in text(out)

        await build(sim, bilda, STOCK_122)
        pinned_dice["value"] = 6   # roll 18 vs 11: botch
        out = await do(sim, bilda, "craft valve")
        assert ("botches the assembly -- ruined scrap hits the tray. "
                "(rolled 18 vs machining 11)" in text(out))
        assert find_all(sim, "a lump of ruined scrap")
        assert not find_all(sim, "a duralloy ingot")       # burned anyway
        assert not find_all(sim, "a machined pressure valve")


# =========================================================================
# 123. Refining chain — docs/showcase/123_refining_chain.md
# =========================================================================

BUILD_123 = build_lines("123_refining_chain.md")


class TestRefiningChain:

    async def test_ore_to_ingot_to_parts(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_123)
        smeltery = find_one(sim, "The Smeltery")
        assert bilda.location is smeltery

        await build(sim, bilda, [
            "@eval [create_obj('a chunk of balthite ore', ['thing', 'ore'], me) for i in range(2)]",
        ])

        out = await do(sim, bilda, "refine")
        assert ("The smelter roars; slag hisses off the pour, and 1x a "
                "duralloy ingot land(s) in the tray." in text(out))
        assert not find_all(sim, "a chunk of balthite ore")

        await do(sim, bilda, "get duralloy ingot")
        assert find_one(sim, "a duralloy ingot").location is bilda

        await do(sim, bilda, "shopway")
        assert bilda.location is find_one(sim, "The Machine Shop")
        out = await do(sim, bilda, "refine")
        assert ("The mill shrieks through the billet, and 2x a precision "
                "servo part land(s) in the tray." in text(out))
        assert len(find_all(sim, "a precision servo part")) == 2
        assert not find_all(sim, "a duralloy ingot")

        # The mill counts what it eats and refuses everything else.
        out = await do(sim, bilda, "refine")
        assert "The hopper wants 1x ingot; you carry 0." in text(out)


# =========================================================================
# 124. Salvage & disassembly — docs/showcase/124_salvage.md
# =========================================================================

BUILD_124 = build_lines("124_salvage.md")


class TestSalvage:

    async def test_full_recovery_on_a_made_roll(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_124)
        await do(sim, bilda, "get busted med-scanner")

        pinned_dice["value"] = 2   # roll 6 vs untrained IQ-2 = 8: success
        out = await do(sim, bilda, "salvage med-scanner")
        assert ("strips busted med-scanner down to: 2x a coil of copper "
                "wire, 1x an intact microcell." in text(out))
        assert len(find_all(sim, "a coil of copper wire")) == 2
        assert len(find_all(sim, "an intact microcell")) == 1
        assert not find_all(sim, "busted med-scanner")

        # Untabled items refuse cleanly; so do absent ones.
        await do(sim, bilda, "get coil of copper wire")
        out = await do(sim, bilda, "salvage copper wire")
        assert ("The scanner shrugs: nothing recoverable in a coil of "
                "copper wire." in text(out))
        out = await do(sim, bilda, "salvage teapot")
        assert "You carry nothing called teapot." in text(out)

    async def test_clumsy_teardown_keeps_only_the_sturdy_row(
            self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_124)
        await do(sim, bilda, "get busted med-scanner")

        pinned_dice["value"] = 5   # roll 15 vs 8: failure
        out = await do(sim, bilda, "salvage med-scanner")
        joined = text(out)
        assert "down to: 2x a coil of copper wire." in joined
        assert "(clumsy teardown -- the delicate parts are mangled)" in joined
        assert "microcell" not in joined
        assert len(find_all(sim, "a coil of copper wire")) == 2
        assert not find_all(sim, "an intact microcell")
        assert not find_all(sim, "busted med-scanner")


# =========================================================================
# 125. Quality tiers — docs/showcase/125_quality_tiers.md
# =========================================================================

BUILD_125 = build_lines("125_quality_tiers.md")

STOCK_125 = [
    "@set me/skill_smithing = 12",
    "@eval [create_obj('a duralloy ingot', ['thing', 'ingot'], me) for i in range(3)]",
]


class TestQualityTiers:

    async def test_margin_grades_fine_good_shoddy(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_125)
        await build(sim, bilda, STOCK_125)

        pinned_dice["value"] = 2   # roll 6 vs 12: margin 6 -> fine
        out = await do(sim, bilda, "forge blade")
        assert "draws a fine vibro-blade off the lathe. (margin 6)" in text(out)
        out = await do(sim, bilda, "look duralloy vibro-blade")
        assert "The maker-stamp grades it FINE." in text(out)
        assert "Edge integrity: 18. Trade value: 150 cr." in text(out)

        pinned_dice["value"] = 4   # roll 12 vs 12: margin 0 -> good
        out = await do(sim, bilda, "forge blade")
        assert "draws a good vibro-blade off the lathe. (margin 0)" in text(out)

        pinned_dice["value"] = 6   # roll 18 vs 12: margin -6 -> shoddy
        out = await do(sim, bilda, "forge blade")
        assert ("draws a shoddy vibro-blade off the lathe. (margin -6)"
                in text(out))

        blades = find_all(sim, "a duralloy vibro-blade")
        assert len(blades) == 3
        stamps = sorted((b.db.get("quality"), b.db.get("value"),
                         b.db.get("durability")) for b in blades)
        assert stamps == [("fine", 150, 18), ("good", 50, 12),
                          ("shoddy", 20, 6)]

        # Out of stock: refused before any dice.
        out = await do(sim, bilda, "forge blade")
        assert "The chuck is empty: bring a duralloy ingot." in text(out)


# =========================================================================
# 126. Blueprint items — docs/showcase/126_blueprints.md
# =========================================================================

BUILD_126 = build_lines("126_blueprints.md")

# A mortal-built copy: the authority rule made visible (not in the doc's
# Build-it; the doc explains the refusal in prose).
BOOTLEG_126 = [
    "@create bootleg slate",
    "drop bootleg slate",
    "@set bootleg slate/recipe = vector_coil",
    "@set bootleg slate/teach = r = V('recipe'); k = get_attr(enactor, 'known_recipes', []); pemit(enactor, 'You already hold the ' + r + ' pattern.') if r in k else (pemit(enactor, 'The slate flickers: WRITE REFUSED. Only a licensed slate may sign your pattern library.') if not set_attr(enactor, 'known_recipes', k + [r]) else (pemit(enactor, 'The schematic unfolds behind your eyes: the ' + r + ' pattern is yours.'), remit(here, 'The slate chirps once, wipes itself, and crumbles into grey flakes.'), destroy_obj(me)))",
    "@set bootleg slate/cmd_study = $study bootleg: eval_attr(me, 'teach')",
]


class TestBlueprints:

    async def test_study_unlocks_the_fabricator(self, sim):
        room, vala = workshop_and_admin(sim)
        await build(sim, vala, BUILD_126)
        kess = sim.player("Kess", location=room)
        await build(sim, vala, [
            "@eval create_obj('a precision servo part', ['thing', 'component'], get('Kess'))",
        ])
        sim.seen(kess)

        # Unlicensed: the machine refuses before counting materials.
        out = await do(sim, kess, "fab vector_coil")
        assert ("The fabricator blinks: UNLICENSED PATTERN vector_coil. "
                "Study its schematic first." in text(out))

        # Studying writes the player's sheet and spends the slate.
        out = await do(sim, kess, "study schematic")
        assert ("The schematic unfolds behind your eyes: the vector_coil "
                "pattern is yours." in text(out))
        assert kess.db.get("known_recipes") == ["vector_coil"]
        assert not find_all(sim, "coil schematic")

        # Licensed: ordinary recipe crafting.
        out = await do(sim, kess, "fab vector_coil")
        assert ("The fabricator sings through the vector_coil pattern; a "
                "vector coil rolls into the tray." in text(out))
        assert find_all(sim, "a humming vector coil")
        assert not find_all(sim, "a precision servo part")

    async def test_the_use_builtin_teaches_too(self, sim):
        # The schematic's ON_USE shares the $study payload, so the engine's
        # `use` command teaches the same pattern (enactor bound in the hook).
        room, vala = workshop_and_admin(sim)
        await build(sim, vala, BUILD_126)
        kess = sim.player("Kess", location=room)
        sim.seen(kess)

        out = await do(sim, kess, "use coil schematic")
        assert ("The schematic unfolds behind your eyes: the vector_coil "
                "pattern is yours." in text(out))
        assert kess.db.get("known_recipes") == ["vector_coil"]
        assert not find_all(sim, "coil schematic")

    async def test_a_mortal_built_slate_cannot_sign_sheets(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BOOTLEG_126)
        kess = sim.player("Kess", location=room)

        out = await do(sim, kess, "study bootleg")
        assert ("The slate flickers: WRITE REFUSED. Only a licensed slate "
                "may sign your pattern library." in text(out))
        assert kess.db.get("known_recipes") is None
        assert find_all(sim, "bootleg slate")   # not spent


# =========================================================================
# 127. Crafting stations — docs/showcase/127_crafting_stations.md
# =========================================================================

BUILD_127 = build_lines("127_crafting_stations.md")


class TestCraftingStations:

    async def test_tool_presence_gates_the_job(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_127)
        # Two components in hand: one for the successful job, one to
        # prove missing tools burn nothing.
        await build(sim, bilda, [
            "@eval [create_obj('a precision servo part', ['thing', 'component'], me) for i in range(2)]",
            "@dig The Corridor = hall, back",
        ])

        # Everything present (welder on the floor, vice in hand — both
        # count as "at the work site").
        out = await do(sim, bilda, "tune gyro")
        assert ("clamps, welds, and spins a gyro assembly true on the "
                "bench." in text(out))
        assert find_all(sim, "a balanced gyro assembly")
        assert len(find_all(sim, "a precision servo part")) == 1  # one burned
        assert find_all(sim, "arc welder")                   # tools survive
        assert find_all(sim, "micro vice")

        # Send the welder away: the tool check enumerates, burns nothing.
        await build(sim, bilda, ["@teleport arc welder = The Corridor"])
        out = await do(sim, bilda, "tune gyro")
        assert ("Tool check -- arc_welder (MISSING), micro_vice (ready): "
                "1 of 2 present." in text(out))
        assert len(find_all(sim, "a precision servo part")) == 1

        # Unknown job guard.
        out = await do(sim, bilda, "tune flux")
        assert "No such job is chalked on this bench." in text(out)

        # Welder back: the job runs again; then empty pockets refuse.
        await build(sim, bilda, ["@teleport arc welder = here"])
        out = await do(sim, bilda, "tune gyro")
        assert ("clamps, welds, and spins a gyro assembly true on the "
                "bench." in text(out))
        assert not find_all(sim, "a precision servo part")
        out = await do(sim, bilda, "tune gyro")
        assert "The jig wants 1x component; you carry 0." in text(out)


# =========================================================================
# 128. Hydroponics farming — docs/showcase/128_farming.md
# =========================================================================

BUILD_128 = build_lines("128_farming.md")


class TestFarming:

    async def test_plant_water_grow_harvest(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_128)
        tray = find_one(sim, "hydro tray")

        out = await do(sim, bilda, "plant seeds")
        assert ("beds a seed into the growth foam; the lamps hum up to "
                "full." in text(out))
        assert not find_all(sim, "packet of helio-tomato seeds")
        out = await do(sim, bilda, "look hydro tray")
        assert "Nutrient gauge: 2/3." in text(out)
        assert "Pale threads spider through the growth foam." in text(out)

        out = await do(sim, bilda, "harvest crop")
        assert "Not yet -- the crop is still germinating." in text(out)

        # Two growth ticks: germination completes, blossoms appear,
        # and the gauge runs dry.
        await do(sim, bilda, "@tr hydro tray/on_tick")
        out = await do(sim, bilda, "@tr hydro tray/on_tick")
        assert ("In the hydro tray: White blossoms nod under the "
                "grow-lamps." in text(out))
        assert tray.db.get("water") == 0

        # Dry: growth pauses until someone waters.
        out = await do(sim, bilda, "@tr hydro tray/on_tick")
        assert "The hydro tray blinks a dry amber warning." in text(out)
        assert tray.db.get("stage") == 1
        out = await do(sim, bilda, "water tray")
        assert "Nutrient mist hisses through the drip lines." in text(out)

        await do(sim, bilda, "@tr hydro tray/on_tick")
        out = await do(sim, bilda, "@tr hydro tray/on_tick")
        assert ("In the hydro tray: Fat helio-tomatoes hang glowing "
                "faintly orange." in text(out))

        out = await do(sim, bilda, "harvest crop")
        assert ("gathers 3 glowing helio-tomatoes; the lamps dim to "
                "standby." in text(out))
        assert len(find_all(sim, "a glowing helio-tomato")) == 3
        assert tray.db.get("stage") is None
        out = await do(sim, bilda, "look hydro tray")
        assert "Its growth bed sits empty, lamps dimmed to standby." in text(out)

        out = await do(sim, bilda, "harvest crop")
        assert "Nothing is planted." in text(out)
        out = await do(sim, bilda, "plant seeds")
        assert "You carry no seed stock." in text(out)


# =========================================================================
# 129. Cooking with buffs — docs/showcase/129_cooking_buffs.md
# =========================================================================

BUILD_129 = build_lines("129_cooking_buffs.md")


class TestCookingBuffs:

    async def test_meal_buff_flips_a_check(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_129)
        await build(sim, bilda, [
            "@set me/skill_throwing = 9",
            "@eval [create_obj('a glowing helio-tomato', ['thing', 'produce'], me) for i in range(2)]",
        ])

        # Cold arm: roll 12 vs 9 misses.
        pinned_dice["value"] = 4
        out = await do(sim, bilda, "throw knife")
        assert "throws wide; the knife skitters off the plating." in text(out)

        out = await do(sim, bilda, "cook stew")
        assert ("The range flares; a bowl of ember-root stew ladles out "
                "onto the counter." in text(out))
        assert not find_all(sim, "a glowing helio-tomato")   # fixings burned

        # The bowl spawns set down (in the room), so eating just works.
        out = await do(sim, bilda, "eat stew")
        assert ("Warmth spreads from your belly: hearty (+3 throwing "
                "while it lasts)." in text(out))
        assert bilda.has_tag("hearty")
        assert bilda.db.get("check_mods") == {"hearty": {"throwing": 3}}
        assert not find_all(sim, "a bowl of ember-root stew")

        # Same pinned roll, now 12 vs 9+3: THOCK.
        out = await do(sim, bilda, "throw knife")
        assert "snaps a knife dead into the painted ring. THOCK." in text(out)

    async def test_spoilage_and_food_poisoning(self, sim, pinned_dice):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_129)
        await build(sim, bilda, [
            "@set me/hp = 13",
            "@set me/max_hp = 13",
            "@eval [create_obj('a glowing helio-tomato', ['thing', 'produce'], me) for i in range(2)]",
        ])
        await do(sim, bilda, "cook stew")
        meal = find_one(sim, "a bowl of ember-root stew")

        # In your hands, the meal asks for a table.
        await do(sim, bilda, "get bowl of ember-root stew")
        out = await do(sim, bilda, "eat stew")
        assert ("Both hands and a flat spot: set a bowl of ember-root "
                "stew down somewhere first." in text(out))
        await do(sim, bilda, "drop bowl of ember-root stew")

        # Four freshness ticks: rank.
        for _ in range(3):
            await do(sim, bilda, "@tr a bowl of ember-root stew/on_tick")
        assert not meal.has_tag("spoiled")
        out = await do(sim, bilda, "@tr a bowl of ember-root stew/on_tick")
        assert ("A bowl of ember-root stew films over and goes rank."
                in text(out))
        assert meal.has_tag("spoiled")

        # Eating it now is a slow mistake.
        out = await do(sim, bilda, "eat stew")
        assert "One sniff says no -- but hunger wins." in text(out)
        assert bilda.has_tag("food_poisoning")
        await deliver_beat(bilda)
        assert "Your stomach knots and cramps." in text(sim.seen(bilda))
        assert bilda.db.get("hp") == 12

        # Guard sweep: no fixings, no such dish.
        out = await do(sim, bilda, "cook stew")
        assert "Short of fixings: 2x produce." in text(out)
        out = await do(sim, bilda, "cook flambe")
        assert "The menu card lists no such dish." in text(out)


# =========================================================================
# 130. Fishing — docs/showcase/130_fishing.md
# =========================================================================

BUILD_130 = build_lines("130_fishing.md")

# Test-only: collapse the real-time lull/window so tick_waits() drives
# the bite chain deterministically (the music-box tempo trick).
FAST_WATER = [
    "@set scum pond/lull = 0",
    "@set scum pond/window = 0",
]


@pytest.fixture
def pinned_water(monkeypatch):
    """Both roll('3d6') (the hook check) and rand(1, 100) (the catch
    draw) funnel through the single global random.randint, so one
    range-routed fake pins them independently: a small-sided call
    (high <= 6) is the skill die, a d100 call is the catch draw."""
    dice = {"value": 3}
    draw = {"value": 1}

    def fake_randint(low, high):
        holder = dice if high <= 6 else draw
        return max(low, min(holder["value"], high))

    monkeypatch.setattr("realm.core.dice.random.randint", fake_randint)
    return SimpleNamespace(dice=dice, draw=draw)


class TestFishing:

    async def test_cast_bite_hook_lands_a_catch(self, sim, pinned_water):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_130)
        await build(sim, bilda, FAST_WATER)
        pond = find_one(sim, "scum pond")

        out = await do(sim, bilda, "cast line")
        assert "casts a line out over the scum." in text(out)
        out = await do(sim, bilda, "cast line")
        assert ("A line is already out. Watch the float; hook when it "
                "dips." in text(out))

        await sim.engine.tick_waits()
        assert "The float dips hard -- something is on!" in text(sim.seen(bilda))

        pinned_water.dice["value"] = 2    # roll 6 vs 9: margin +3
        pinned_water.draw["value"] = 50   # 50 <= 55: the mudskipper row
        out = await do(sim, bilda, "hook")
        assert ("hooks it clean -- a mottled mudskipper lands flopping on "
                "the dock! (margin +3)" in text(out))
        fish = find_one(sim, "a mottled mudskipper")
        assert fish.has_tag("fish")
        assert pond.db.get("line_out") is None

        # The stale window-closer finds the state gone and stays silent.
        await sim.engine.tick_waits()
        assert ("The water stills." not in text(sim.seen(bilda)))

    async def test_windows_misses_and_guards(self, sim, pinned_water):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BUILD_130)
        await build(sim, bilda, FAST_WATER)
        pond = find_one(sim, "scum pond")

        # Hook with no line out.
        out = await do(sim, bilda, "hook")
        assert "No line in the water. cast line first." in text(out)

        # Hook before the dip scares everything off and wastes the cast.
        await do(sim, bilda, "cast line")
        out = await do(sim, bilda, "hook")
        assert ("You yank at still water; anything under the scum is "
                "long warned off." in text(out))
        await sim.engine.tick_waits()   # stale bite: line_out gone, silent
        assert "The float dips" not in text(sim.seen(bilda))

        # Miss the window entirely: the pond closes it.
        await do(sim, bilda, "cast line")
        await sim.engine.tick_waits()   # bite
        sim.seen(bilda)
        await sim.engine.tick_waits()   # slack
        assert ("The water stills. The line drifts back slack, bait gone."
                in text(sim.seen(bilda)))
        assert pond.db.get("bite_open") is None

        # Blow the roll: the dice go on the record.
        await do(sim, bilda, "cast line")
        await sim.engine.tick_waits()
        pinned_water.dice["value"] = 6    # roll 18 vs 9
        out = await do(sim, bilda, "hook")
        assert ("It spits the hook and is gone. (rolled 18 vs angling 9)"
                in text(out))
        assert not find_all(sim, "a waterlogged boot")


# =========================================================================
# 131. Chemistry & poisons — docs/showcase/131_chemistry_poisons.md
# =========================================================================

BUILD_131 = build_lines("131_chemistry_poisons.md")


class TestChemistry:

    async def _lab(self, sim):
        room, vala = workshop_and_admin(sim)
        await build(sim, vala, BUILD_131)
        kess = sim.player("Kess", location=room, hp=13, max_hp=13)
        # Three batches of reagents for mend (1 biomass + 1 solvent each).
        await build(sim, vala, [
            "@eval [create_obj('a clot of vat biomass', ['thing', 'biomass'], get('Kess')) for i in range(3)]",
            "@eval [create_obj('a canister of solvent', ['thing', 'solvent'], get('Kess')) for i in range(3)]",
        ])
        sim.seen(kess)
        return room, vala, kess

    async def test_gates_then_banded_outcomes(self, sim, pinned_dice):
        _room, vala, kess = await self._lab(sim)

        out = await do(sim, kess, "formulas")
        joined = text(out)
        assert ("mend -> a vial of mendicine gel (CHEM-10; needs: "
                "1x biomass, 1x solvent)" in joined)
        assert ("etch -> a flask of kryl etchant (CHEM-12; needs: "
                "2x solvent)" in joined)

        # Gate 1: no pathway.
        out = await do(sim, kess, "mix mend")
        assert ("The rig refuses: no verified pathway for mend in your "
                "neural index." in text(out))

        out = await do(sim, kess, "memorize chip")
        assert ("Cold data blooms behind your eyes: the mend pathway is "
                "yours." in text(out))
        assert kess.db.get("known_formulas") == ["mend"]
        out = await do(sim, kess, "memorize chip")
        assert "You already hold the mend pathway." in text(out)

        # Gate 2: certification floor.
        out = await do(sim, kess, "mix mend")
        assert ("The rig refuses: certification CHEM-10 required (your "
                "chemistry: 0)." in text(out))
        await build(sim, vala, ["@set Kess/skill_chemistry = 12"])

        # Knowledge is per-formula: etch still refuses.
        out = await do(sim, kess, "mix etch")
        assert ("The rig refuses: no verified pathway for etch in your "
                "neural index." in text(out))

        # Success band: margin +3.
        pinned_dice["value"] = 3
        out = await do(sim, kess, "mix mend")
        assert ("The rig cycles green; a vial of mendicine gel fills in "
                "the cradle. (margin +3)" in text(out))
        vial = find_one(sim, "a vial of mendicine gel")
        assert vial.db.get("value") == 40
        assert vial.db.get("cmd_apply")
        assert len(find_all(sim, "a clot of vat biomass")) == 2

        # Sludge band: miss by 3.
        pinned_dice["value"] = 5
        out = await do(sim, kess, "mix mend")
        assert ("The mix curdles into inert sludge. (rolled 15 vs "
                "chemistry 12)" in text(out))
        assert len(find_all(sim, "a clot of vat biomass")) == 1

        # Fumble band: miss by 6 -> spray + ticking burn.
        pinned_dice["value"] = 6
        out = await do(sim, kess, "mix mend")
        assert ("The rig shrieks -- the mix flashes back in a caustic "
                "spray!" in text(out))
        assert kess.has_tag("chem_burn")
        assert kess.db.get("hp") == 11          # 1d2 pinned to 2
        assert not find_all(sim, "a clot of vat biomass")

        # The medicine is the counterplay (the vial spawned set down).
        out = await do(sim, kess, "apply gel")
        assert "The gel knits skin cold and quick; the burning stops." in text(out)
        assert not kess.has_tag("chem_burn")
        assert kess.db.get("hp") == 13
        assert not find_all(sim, "a vial of mendicine gel")

        # Unknown formula guard, then reagent arithmetic.
        out = await do(sim, kess, "mix fizz")
        assert "The rig lists no such formula. Try formulas." in text(out)
        out = await do(sim, kess, "mix mend")
        assert "Reagents short: 1x biomass, 1x solvent." in text(out)
