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

The build transcripts below are copied verbatim from the docs' "Build
it" sections; the sync test at the bottom keeps them from drifting.
Time and dice are deterministic: script_ticker scripts fire via
`@tr <obj>/on_tick`, wait() chains via engine.tick_waits() after
zeroing the lull/window attributes (the music-box trick), beat-driven
effects via deliver_beat(), and every die roll is pinned by
monkeypatching the two random sources (realm.core.dice for
roll()/skill_check, realm.scripting.functions for rand()).
"""

from __future__ import annotations

from pathlib import Path
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

BUILD_121 = [
    "@create balthite vein",
    "drop balthite vein",
    "@desc balthite vein = A seam of blue-green balthite crystal veining the rock face. [[left = get_attr(me, 'ore_left', 0); result = 'It glitters, thick with ore.' if left > 2 else ('Only pale traces remain in the cut.' if left > 0 else 'It is hacked bare -- nothing but scarred rock.')]]",
    "@set balthite vein/ore_cap = 4",
    "@set balthite vein/ore_left = 4",
    "@set balthite vein/regrow_ticks = 3",
    "@set balthite vein/cmd_mine = $mine vein: left = get_attr(me, 'ore_left', 0); res = margin_under(roll('3d6'), get_attr(enactor, 'skill_prospecting', 8)); take = min(left, 1 + max(0, res.margin) // 3); pemit(enactor, 'The vein is hacked bare. Rock heals on its own clock; come back later.') if left < 1 else None; pemit(enactor, 'Sparks, dust, no ore. (rolled ' + str(res.roll) + ' vs prospecting ' + str(res.effective) + ')') if left > 0 and not res.success else None; (set_attr(me, 'ore_left', left - take), [create_obj('a chunk of balthite ore', ['thing', 'ore'], here) for i in range(take)], remit(here, name(enactor) + ' swings at the vein -- ' + str(take) + ' chunk(s) of balthite clatter free.'), (set_attr(me, 'regrow_left', get_attr(me, 'regrow_ticks', 3)), remit(here, 'The seam splits and goes dark, spent.')) if left - take < 1 else None) if left > 0 and res.success else None",
    "@set balthite vein/on_tick = left = get_attr(me, 'ore_left', 0); r = get_attr(me, 'regrow_left', 0); (set_attr(me, 'regrow_left', r - 1) if r > 1 else (set_attr(me, 'ore_left', get_attr(me, 'ore_cap', 4)), del_attr(me, 'regrow_left'), remit(here, 'Fresh balthite creeps glittering back across the rock face.'))) if left < 1 else None",
    "@behavior balthite vein = script_ticker, interval:30",
]


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

BUILD_122 = [
    "@create assembly bench",
    "drop assembly bench",
    "@desc assembly bench = A scarred steel bench under a rack of torque drivers. A job card is chained to one leg.",
    "@set assembly bench/menu = [\"valve\"]",
    "@set assembly bench/recipe_valve = {\"output\": \"a machined pressure valve\", \"tags\": [\"thing\", \"component\"], \"skill\": \"machining\", \"mod\": 0, \"needs\": {\"ingot\": 1, \"gasket\": 1}}",
    "@set assembly bench/cmd_jobs = $jobs: [pemit(enactor, '  ' + s + ' -> ' + get_attr(me, 'recipe_' + s)['output'] + ' (needs: ' + ', '.join(str(n) + 'x ' + t for t, n in get_attr(me, 'recipe_' + s)['needs'].items()) + ')') for s in get_attr(me, 'menu', [])]",
    "@set assembly bench/cmd_craft = $craft *: sel = trim(arg0).lower(); r = get_attr(me, 'recipe_' + sel); carried = contents(enactor) if r else []; short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in (r['needs'].items() if r else []) if len([o for o in carried if has_tag(o, t)]) < n]; pemit(enactor, 'The job card lists no such assembly. Try jobs.') if not r else None; pemit(enactor, 'Short of materials: ' + ', '.join(short) + '.') if r and short else None; res = margin_under(roll('3d6'), get_attr(enactor, 'skill_' + r['skill'], 8) + r['mod']) if r and not short else None; ([destroy_obj(o) for t, n in r['needs'].items() for o in [x for x in carried if has_tag(x, t)][:n]], (create_obj(r['output'], r['tags'], here), remit(here, name(enactor) + ' works the bench -- ' + r['output'] + ' drops into the tray. (margin +' + str(res.margin) + ')')) if res.success else (create_obj('a lump of ruined scrap', ['thing', 'scrap'], here), remit(here, name(enactor) + ' botches the assembly -- ruined scrap hits the tray. (rolled ' + str(res.roll) + ' vs ' + r['skill'] + ' ' + str(res.effective) + ')'))) if r and not short else None",
]

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

BUILD_123 = [
    "@dig The Smeltery = smeltway, yard",
    "smeltway",
    "@create arc smelter",
    "drop arc smelter",
    "@desc arc smelter = A squat induction furnace, crucible glowing the color of a dying sun. Its hopper gapes for raw ore.",
    "@set arc smelter/eats = ore",
    "@set arc smelter/eats_count = 2",
    "@set arc smelter/makes = a duralloy ingot",
    "@set arc smelter/makes_tags = [\"thing\", \"ingot\"]",
    "@set arc smelter/makes_count = 1",
    "@set arc smelter/work_msg = The smelter roars; slag hisses off the pour, and",
    "@set arc smelter/cmd_refine = $refine: t = get_attr(me, 'eats'); n = get_attr(me, 'eats_count', 1); stock = [o for o in contents(enactor) if has_tag(o, t)]; k = get_attr(me, 'makes_count', 1); pemit(enactor, 'The hopper wants ' + str(n) + 'x ' + t + '; you carry ' + str(len(stock)) + '.') if len(stock) < n else ([destroy_obj(o) for o in stock[:n]], [create_obj(get_attr(me, 'makes'), get_attr(me, 'makes_tags', ['thing']), here) for i in range(k)], remit(here, get_attr(me, 'work_msg', 'The station cycles, and') + ' ' + str(k) + 'x ' + get_attr(me, 'makes') + ' land(s) in the tray.'))",
    "@dig The Machine Shop = shopway, smeltway",
    "shopway",
    "@create parts mill",
    "drop parts mill",
    "@desc parts mill = A gantry mill sleeved in coolant mist. A feed clamp waits for ingot stock.",
    "@set parts mill/eats = ingot",
    "@set parts mill/eats_count = 1",
    "@set parts mill/makes = a precision servo part",
    "@set parts mill/makes_tags = [\"thing\", \"component\"]",
    "@set parts mill/makes_count = 2",
    "@set parts mill/work_msg = The mill shrieks through the billet, and",
    "@set parts mill/cmd_refine = $refine: t = get_attr(me, 'eats'); n = get_attr(me, 'eats_count', 1); stock = [o for o in contents(enactor) if has_tag(o, t)]; k = get_attr(me, 'makes_count', 1); pemit(enactor, 'The hopper wants ' + str(n) + 'x ' + t + '; you carry ' + str(len(stock)) + '.') if len(stock) < n else ([destroy_obj(o) for o in stock[:n]], [create_obj(get_attr(me, 'makes'), get_attr(me, 'makes_tags', ['thing']), here) for i in range(k)], remit(here, get_attr(me, 'work_msg', 'The station cycles, and') + ' ' + str(k) + 'x ' + get_attr(me, 'makes') + ' land(s) in the tray.'))",
    "smeltway",
]


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

BUILD_124 = [
    "@create salvage",
    "@tag salvage = skill_def",
    "@set salvage/stat = intelligence",
    "@set salvage/penalty = -2",
    "@reload",
    "@create breaker bench",
    "drop breaker bench",
    "@desc breaker bench = A waist-high teardown bench: magnetic bit rack, spudgers, a parts tray scarred by ten thousand screws.",
    "@set breaker bench/parts_gadget = [[\"a coil of copper wire\", 2, [\"thing\", \"wire\"]], [\"an intact microcell\", 1, [\"thing\", \"cell\"]]]",
    "@set breaker bench/parts_scrap = [[\"a chunk of balthite ore\", 1, [\"thing\", \"ore\"]]]",
    "@set breaker bench/cmd_salvage = $salvage *: q = trim(arg0).lower(); tgt = ([o for o in contents(enactor) if q in name(o).lower()] + [None])[0]; tabs = [t for t in tags(tgt) if has_attr(me, 'parts_' + t)] if tgt else []; pemit(enactor, 'You carry nothing called ' + q + '.') if not tgt else None; pemit(enactor, 'The scanner shrugs: nothing recoverable in ' + name(tgt) + '.') if tgt and not tabs else None; ok = skill_check(enactor, 'salvage') if tabs else False; tab = get_attr(me, 'parts_' + tabs[0], []) if tabs else []; keep = tab if ok else tab[:1]; (destroy_obj(tgt), [create_obj(row[0], row[2], here) for row in keep for i in range(row[1])], remit(here, name(enactor) + ' strips ' + name(tgt) + ' down to: ' + ', '.join(str(row[1]) + 'x ' + row[0] for row in keep) + '.' + ('' if ok else ' (clumsy teardown -- the delicate parts are mangled)'))) if tabs else None",
    "@create busted med-scanner",
    "@tag busted med-scanner = gadget",
    "drop busted med-scanner",
]


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

BUILD_125 = [
    "@create finishing lathe",
    "drop finishing lathe",
    "@desc finishing lathe = A precision lathe behind a spotless splash guard. A brass plaque grades every blade it releases.",
    "@set finishing lathe/base_value = 50",
    "@set finishing lathe/tiers = [[4, \"fine\", 3.0, 18], [0, \"good\", 1.0, 12], [-99, \"shoddy\", 0.4, 6]]",
    "@set finishing lathe/cmd_forge = $forge blade: stock = [o for o in contents(enactor) if has_tag(o, 'ingot')]; pemit(enactor, 'The chuck is empty: bring a duralloy ingot.') if not stock else None; res = margin_under(roll('3d6'), get_attr(enactor, 'skill_smithing', 8)) if stock else None; tier = [row for row in get_attr(me, 'tiers', []) if res.margin >= row[0]][0] if stock else None; (destroy_obj(stock[0]), [(set_attr(b, 'quality', tier[1]), set_attr(b, 'value', int(get_attr(me, 'base_value', 50) * tier[2])), set_attr(b, 'durability', tier[3]), set_attr(b, 'desc_extras', [['', 'A slender vibro-blade. The maker-stamp grades it ' + tier[1].upper() + '.'], ['', 'Edge integrity: ' + str(tier[3]) + '. Trade value: ' + str(int(get_attr(me, 'base_value', 50) * tier[2])) + ' cr.']]), remit(here, name(enactor) + ' draws a ' + tier[1] + ' vibro-blade off the lathe. (margin ' + str(res.margin) + ')')) for b in [create_obj('a duralloy vibro-blade', ['thing', 'blade'], here)]]) if stock else None",
]

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

BUILD_126 = [
    "@create coil schematic",
    "drop coil schematic",
    "@desc coil schematic = A mil-spec data-slate, screen crawling with exploded diagrams of a field coil. STUDY it -- once.",
    "@set coil schematic/recipe = vector_coil",
    "@set coil schematic/teach = r = get_attr(me, 'recipe'); k = get_attr(enactor, 'known_recipes', []); pemit(enactor, 'You already hold the ' + r + ' pattern.') if r in k else (pemit(enactor, 'The slate flickers: WRITE REFUSED. Only a licensed slate may sign your pattern library.') if not set_attr(enactor, 'known_recipes', k + [r]) else (pemit(enactor, 'The schematic unfolds behind your eyes: the ' + r + ' pattern is yours.'), remit(here, 'The slate chirps once, wipes itself, and crumbles into grey flakes.'), destroy_obj(me)))",
    "@set coil schematic/cmd_study = $study schematic: eval_attr(me, 'teach')",
    "@set coil schematic/ON_USE = eval_attr(me, 'teach')",
    "@create coil fabricator",
    "drop coil fabricator",
    "@desc coil fabricator = A sealed lathe-printer. Its status ring idles amber: AWAITING LICENSED PATTERN.",
    "@set coil fabricator/cmd_fab = $fab *: sel = trim(arg0).lower(); known = get_attr(enactor, 'known_recipes', []); comps = [o for o in contents(enactor) if has_tag(o, 'component')]; pemit(enactor, 'The fabricator blinks: UNLICENSED PATTERN ' + sel + '. Study its schematic first.') if sel not in known else (pemit(enactor, 'The ' + sel + ' pattern calls for 1x component; you carry 0.') if not comps else (destroy_obj(comps[0]), create_obj('a humming vector coil', ['thing', 'coil'], here), remit(here, 'The fabricator sings through the ' + sel + ' pattern; a vector coil rolls into the tray.')))",
]

# A mortal-built copy: the authority rule made visible (not in the doc's
# Build-it; the doc explains the refusal in prose).
BOOTLEG_126 = [
    "@create bootleg slate",
    "drop bootleg slate",
    "@set bootleg slate/recipe = vector_coil",
    "@set bootleg slate/teach = r = get_attr(me, 'recipe'); k = get_attr(enactor, 'known_recipes', []); pemit(enactor, 'You already hold the ' + r + ' pattern.') if r in k else (pemit(enactor, 'The slate flickers: WRITE REFUSED. Only a licensed slate may sign your pattern library.') if not set_attr(enactor, 'known_recipes', k + [r]) else (pemit(enactor, 'The schematic unfolds behind your eyes: the ' + r + ' pattern is yours.'), remit(here, 'The slate chirps once, wipes itself, and crumbles into grey flakes.'), destroy_obj(me)))",
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

BUILD_127 = [
    "@create tuning bench",
    "drop tuning bench",
    "@desc tuning bench = A vibration-damped bench ruled into a calibration grid. Etched under the lamp: TOOLS MAKE THE MACHINIST.",
    "@set tuning bench/recipe_gyro = {\"output\": \"a balanced gyro assembly\", \"tags\": [\"thing\", \"gyro\"], \"needs\": {\"component\": 1}, \"tools\": [\"arc_welder\", \"micro_vice\"]}",
    "@set tuning bench/cmd_tune = $tune *: sel = trim(arg0).lower(); r = get_attr(me, 'recipe_' + sel); near = contents(here) + contents(enactor) if r else []; stat = [t + (' (ready)' if [o for o in near if has_tag(o, t)] else ' (MISSING)') for t in r['tools']] if r else []; miss = [t for t in r['tools'] if not [o for o in near if has_tag(o, t)]] if r else []; stock = [o for o in contents(enactor) if has_tag(o, 'component')] if r else []; pemit(enactor, 'No such job is chalked on this bench.') if not r else None; pemit(enactor, 'Tool check -- ' + ', '.join(stat) + ': ' + str(len(r['tools']) - len(miss)) + ' of ' + str(len(r['tools'])) + ' present.') if r and miss else None; pemit(enactor, 'The jig wants 1x component; you carry ' + str(len(stock)) + '.') if r and not miss and not stock else None; (destroy_obj(stock[0]), create_obj(r['output'], r['tags'], here), remit(here, name(enactor) + ' clamps, welds, and spins a gyro assembly true on the bench.')) if r and not miss and stock else None",
    "@create arc welder",
    "@tag arc welder = arc_welder",
    "drop arc welder",
    "@create micro vice",
    "@tag micro vice = micro_vice",
]


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

BUILD_128 = [
    "@create hydro tray",
    "drop hydro tray",
    "@desc hydro tray = A chest-high hydroponic vat webbed with drip lines under grow-lamps. [[w = get_attr(me, 'water', 0); result = ('Nutrient gauge: ' + str(w) + '/3.') if has_attr(me, 'stage') else 'Its growth bed sits empty, lamps dimmed to standby.']]",
    "@set hydro tray/stages = [[\"germinating\", 2, \"Pale threads spider through the growth foam.\"], [\"flowering\", 2, \"White blossoms nod under the grow-lamps.\"], [\"fruiting\", 0, \"Fat helio-tomatoes hang glowing faintly orange.\"]]",
    "@set hydro tray/cmd_plant = $plant *: seeds = [o for o in contents(enactor) if has_tag(o, 'seed')]; pemit(enactor, 'The bed is already planted.') if has_attr(me, 'stage') else (pemit(enactor, 'You carry no seed stock.') if not seeds else (destroy_obj(seeds[0]), set_attr(me, 'stage', 0), set_attr(me, 'stage_left', get_attr(me, 'stages')[0][1]), set_attr(me, 'water', 2), set_attr(me, 'desc_extras', [['', get_attr(me, 'stages')[0][2]]]), remit(here, name(enactor) + ' beds a seed into the growth foam; the lamps hum up to full.')))",
    "@set hydro tray/cmd_water = $water tray: pemit(enactor, 'Nothing is planted.') if not has_attr(me, 'stage') else (set_attr(me, 'water', 3), remit(here, 'Nutrient mist hisses through the drip lines.'))",
    "@set hydro tray/cmd_harvest = $harvest *: s = get_attr(me, 'stage', None); st = get_attr(me, 'stages', []); ripe = s is not None and s >= len(st) - 1; pemit(enactor, 'Nothing is planted.') if s is None else None; pemit(enactor, 'Not yet -- the crop is still ' + st[s][0] + '.') if s is not None and not ripe else None; ([create_obj('a glowing helio-tomato', ['thing', 'produce'], here) for i in range(3)], del_attr(me, 'stage'), del_attr(me, 'stage_left'), del_attr(me, 'water'), del_attr(me, 'desc_extras'), remit(here, name(enactor) + ' gathers 3 glowing helio-tomatoes; the lamps dim to standby.')) if ripe else None",
    "@set hydro tray/on_tick = s = get_attr(me, 'stage', None); st = get_attr(me, 'stages', []); w = get_attr(me, 'water', 0); ripe = s is not None and s >= len(st) - 1; go = s is not None and not ripe; (remit(here, 'The hydro tray blinks a dry amber warning.') if w < 1 else (set_attr(me, 'water', w - 1), (set_attr(me, 'stage_left', get_attr(me, 'stage_left', 1) - 1) if get_attr(me, 'stage_left', 1) > 1 else (set_attr(me, 'stage', s + 1), set_attr(me, 'stage_left', st[s + 1][1]), set_attr(me, 'desc_extras', [['', st[s + 1][2]]]), remit(here, 'In the hydro tray: ' + st[s + 1][2]))))) if go else None",
    "@behavior hydro tray = script_ticker, interval:60",
    "@create packet of helio-tomato seeds",
    "@tag packet of helio-tomato seeds = seed",
]


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

BUILD_129 = [
    "@create galley range",
    "drop galley range",
    "@desc galley range = A blackened four-ring galley range. The menu card wedged over the ignition reads: STEW.",
    "@set galley range/cook_stew = {\"name\": \"a bowl of ember-root stew\", \"needs\": {\"produce\": 2}, \"buff_kind\": \"hearty\", \"buff_skill\": \"throwing\", \"buff_mod\": 3, \"buff_beats\": 10, \"fresh\": 4}",
    "@set galley range/eat_code = $eat *: b = get_attr(me, 'buff'); pemit(enactor, 'Both hands and a flat spot: set ' + name(me) + ' down somewhere first.') if loc(me) == enactor else ((pemit(enactor, 'One sniff says no -- but hunger wins. It has gone rank.'), apply_effect(enactor, 'damage_over_time', kind='food_poisoning', damage=1, interval=1, duration=3, tick_msg='Your stomach knots and cramps.', expire_msg='Your stomach finally settles.'), destroy_obj(me)) if has_tag(me, 'spoiled') else (apply_effect(enactor, 'modifier_effect', kind=b['kind'], duration=b['beats'], check_mods={b['skill']: b['mod']}, apply_msg='Warmth spreads from your belly: ' + b['kind'] + ' (+' + str(b['mod']) + ' ' + b['skill'] + ' while it lasts).', expire_msg='The warm, well-fed feeling fades.'), remit(here, name(enactor) + ' scrapes the bowl clean.'), destroy_obj(me)))",
    "@set galley range/spoil_code = sp = has_tag(me, 'spoiled'); f = get_attr(me, 'freshness', 4) - get_attr(loc(me), 'decay_rate', 1); (set_attr(me, 'freshness', f), (add_tag(me, 'spoiled'), remit(here, ucfirst(name(me)) + ' films over and goes rank.')) if f <= 0 else None) if not sp else None",
    "@set galley range/cmd_cook = $cook *: sel = trim(arg0).lower(); r = get_attr(me, 'cook_' + sel); carried = contents(enactor) if r else []; short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in (r['needs'].items() if r else []) if len([o for o in carried if has_tag(o, t)]) < n]; pemit(enactor, 'The menu card lists no such dish.') if not r else None; pemit(enactor, 'Short of fixings: ' + ', '.join(short) + '.') if r and short else None; ([destroy_obj(o) for t, n in r['needs'].items() for o in [x for x in carried if has_tag(x, t)][:n]], [(set_attr(m, 'buff', {'kind': r['buff_kind'], 'skill': r['buff_skill'], 'mod': r['buff_mod'], 'beats': r['buff_beats']}), set_attr(m, 'freshness', r['fresh']), set_attr(m, 'cmd_eat', get_attr(me, 'eat_code')), set_attr(m, 'on_tick', get_attr(me, 'spoil_code')), attach_behavior(m, 'script_ticker', interval=45), set_attr(m, 'desc_extras', [['', 'Chunks of ember-root in a pepper-dark broth, still steaming.']]), remit(here, 'The range flares; ' + r['name'] + ' ladles out onto the counter.')) for m in [create_obj(r['name'], ['thing', 'meal'], here)]]) if r and not short else None",
    "@create knife board",
    "drop knife board",
    "@desc knife board = A scarred target board bolted by the galley door, one painted ring, many old knife scars. THROW KNIFE at it.",
    "@set knife board/cmd_throw = $throw knife: hit = skill_check(enactor, 'throwing'); remit(here, name(enactor) + (' snaps a knife dead into the painted ring. THOCK.' if hit else ' throws wide; the knife skitters off the plating.'))",
]


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

BUILD_130 = [
    "@create scum pond",
    "drop scum pond",
    "@desc scum pond = A green-skinned catch pool between dock pilings. Now and then something moves under the scum. CAST LINE here.",
    "@set scum pond/lull = 6",
    "@set scum pond/window = 4",
    "@set scum pond/catches = [[\"a mottled mudskipper\", 55, [\"thing\", \"fish\"]], [\"a silver dartfish\", 30, [\"thing\", \"fish\"]], [\"a waterlogged boot\", 15, [\"thing\", \"junk\"]]]",
    "@set scum pond/cmd_cast = $cast line: pemit(enactor, 'A line is already out. Watch the float; hook when it dips.') if get_attr(me, 'line_out', 0) else (set_attr(me, 'line_out', 1), set_attr(me, 'angler', enactor.id), remit(here, name(enactor) + ' casts a line out over the scum.'), wait(get_attr(me, 'lull', 6), 'trigger me/bite'))",
    "@set scum pond/bite = (set_attr(me, 'bite_open', 1), remit(here, 'The float dips hard -- something is on!'), wait(get_attr(me, 'window', 4), 'trigger me/slack')) if get_attr(me, 'line_out', 0) else None",
    "@set scum pond/slack = (del_attr(me, 'bite_open'), del_attr(me, 'line_out'), del_attr(me, 'angler'), remit(here, 'The water stills. The line drifts back slack, bait gone.')) if get_attr(me, 'bite_open', 0) else None",
    "@set scum pond/cmd_hook = $hook: lined = get_attr(me, 'line_out', 0); dip = get_attr(me, 'bite_open', 0); pemit(enactor, 'No line in the water. cast line first.') if not lined else None; (del_attr(me, 'line_out'), del_attr(me, 'angler'), pemit(enactor, 'You yank at still water; anything under the scum is long warned off.')) if lined and not dip else None; res = margin_under(roll('3d6'), get_attr(enactor, 'skill_angling', 9)) if lined and dip else None; draw = lambda draw, t, r: t[0] if r <= t[0][1] or len(t) == 1 else draw(draw, t[1:], r - t[0][1]); c = draw(draw, get_attr(me, 'catches', []), rand(1, 100)) if lined and dip else None; (del_attr(me, 'bite_open'), del_attr(me, 'line_out'), del_attr(me, 'angler'), (create_obj(c[0], c[2], here), remit(here, name(enactor) + ' hooks it clean -- ' + c[0] + ' lands flopping on the dock! (margin +' + str(res.margin) + ')')) if res.success else remit(here, 'It spits the hook and is gone. (rolled ' + str(res.roll) + ' vs angling ' + str(res.effective) + ')')) if lined and dip else None",
]

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

BUILD_131 = [
    "@create synthesis rig",
    "drop synthesis rig",
    "@desc synthesis rig = A fume-hooded synthesis rig of coiled glass and ceramic pumps. Its status ring idles amber. MIX here -- if you are licensed.",
    "@set synthesis rig/menu = [\"mend\", \"etch\"]",
    "@set synthesis rig/form_mend = {\"name\": \"a vial of mendicine gel\", \"tags\": [\"thing\", \"medicine\"], \"needs\": {\"biomass\": 1, \"solvent\": 1}, \"min_skill\": 10, \"apply\": true, \"value\": 40, \"blurb\": \"Cold blue gel that knits burns and scrapes. APPLY GEL once it is set down.\"}",
    "@set synthesis rig/form_etch = {\"name\": \"a flask of kryl etchant\", \"tags\": [\"thing\", \"acid\"], \"needs\": {\"solvent\": 2}, \"min_skill\": 12, \"apply\": false, \"value\": 25, \"blurb\": \"Amber etchant that whispers against its glass. Industrial use only.\"}",
    "@set synthesis rig/gel_code = $apply gel: pemit(enactor, 'Set the vial down first; the applicator wants a steady base.') if loc(me) == enactor else (remove_effect(enactor, 'chem_burn'), heal(enactor, 2), pemit(enactor, 'The gel knits skin cold and quick; the burning stops.'), remit(here, name(enactor) + ' smooths mendicine gel over the burns.'), destroy_obj(me))",
    "@set synthesis rig/cmd_formulas = $formulas: [pemit(enactor, '  ' + s + ' -> ' + get_attr(me, 'form_' + s)['name'] + ' (CHEM-' + str(get_attr(me, 'form_' + s)['min_skill']) + '; needs: ' + ', '.join(str(n) + 'x ' + t for t, n in get_attr(me, 'form_' + s)['needs'].items()) + ')') for s in get_attr(me, 'menu', [])]",
    "@set synthesis rig/cmd_mix = $mix *: sel = trim(arg0).lower(); r = get_attr(me, 'form_' + sel); known = get_attr(enactor, 'known_formulas', []); lvl = get_attr(enactor, 'skill_chemistry', 0); carried = contents(enactor) if r else []; short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in (r['needs'].items() if r else []) if len([o for o in carried if has_tag(o, t)]) < n]; pemit(enactor, 'The rig lists no such formula. Try formulas.') if not r else None; pemit(enactor, 'The rig refuses: no verified pathway for ' + sel + ' in your neural index.') if r and sel not in known else None; pemit(enactor, 'The rig refuses: certification CHEM-' + str(r['min_skill']) + ' required (your chemistry: ' + str(lvl) + ').') if r and sel in known and lvl < r['min_skill'] else None; pemit(enactor, 'Reagents short: ' + ', '.join(short) + '.') if r and sel in known and lvl >= r['min_skill'] and short else None; go = bool(r) and sel in known and lvl >= r['min_skill'] and not short; res = margin_under(roll('3d6'), lvl) if go else None; ([destroy_obj(o) for t, n in r['needs'].items() for o in [x for x in carried if has_tag(x, t)][:n]], ([(set_attr(v, 'cmd_apply', get_attr(me, 'gel_code')) if r['apply'] else None, set_attr(v, 'value', r['value']), set_attr(v, 'desc_extras', [['', r['blurb']]]), remit(here, 'The rig cycles green; ' + r['name'] + ' fills in the cradle. (margin +' + str(res.margin) + ')')) for v in [create_obj(r['name'], r['tags'], here)]] if res.success else (remit(here, 'The mix curdles into inert sludge. (rolled ' + str(res.roll) + ' vs chemistry ' + str(res.effective) + ')') if res.margin > -5 else (remit(here, 'The rig shrieks -- the mix flashes back in a caustic spray!'), damage(enactor, roll('1d2')), apply_effect(enactor, 'damage_over_time', kind='chem_burn', damage=1, interval=1, duration=4, tick_msg='Caustic residue eats at your skin!', room_msg='{name} claws at smoking sleeves.', expire_msg='The last of the residue burns itself out.'))))) if go else None",
    "@create mend formula chip",
    "drop mend formula chip",
    "@desc mend formula chip = A ceramic data-chip etched MEND-7G. MEMORIZE CHIP to take the synthesis pathway.",
    "@set mend formula chip/formula = mend",
    "@set mend formula chip/cmd_memorize = $memorize chip: f = get_attr(me, 'formula'); k = get_attr(enactor, 'known_formulas', []); pemit(enactor, 'You already hold the ' + f + ' pathway.') if f in k else (pemit(enactor, 'The chip blinks: WRITE REFUSED (unlicensed chip).') if not set_attr(enactor, 'known_formulas', k + [f]) else pemit(enactor, 'Cold data blooms behind your eyes: the ' + f + ' pathway is yours.'))",
]


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


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "121_gathering_nodes.md": BUILD_121,
    "122_recipe_crafting.md": BUILD_122,
    "123_refining_chain.md": BUILD_123,
    "124_salvage.md": BUILD_124,
    "125_quality_tiers.md": BUILD_125,
    "126_blueprints.md": BUILD_126,
    "127_crafting_stations.md": BUILD_127,
    "128_farming.md": BUILD_128,
    "129_cooking_buffs.md": BUILD_129,
    "130_fishing.md": BUILD_130,
    "131_chemistry_poisons.md": BUILD_131,
}


def _build_it_lines(text):
    """Every non-blank line inside ```text fences of the Build-it section."""
    section = text.split("## Build it", 1)[1].split("## Try it", 1)[0]
    lines = []
    in_fence = False
    for line in section.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence and line.strip():
            lines.append(line.rstrip())
    return lines


def test_tutorial_docs_match_the_exact_tested_command_lines():
    """The embedded transcripts equal the docs' Build-it sections line for
    line, so the tutorials can never drift from what the tests prove."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        doc = (DOCS / doc_name).read_text(encoding="utf-8")
        assert _build_it_lines(doc) == lines, (
            f"{doc_name} Build-it lines differ from the tested transcript")
