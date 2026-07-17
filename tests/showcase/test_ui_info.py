"""
Showcase "Information & UI" — checklist items 189, 190, 191, 193, 196.

Verifies the tutorials in docs/showcase/ (189_minimap.md, 190_score_screen.md,
191_help_extensions.md, 193_gmcp_oob.md, 196_nicks.md) by driving a real
in-process world — realm.testing.Simulator wires the same store/propagation/
scripting/dispatcher stack a live GameServer does — with each tutorial's EXACT
"Build it" command lines (raw input in, session output out).

The build transcripts below are copied verbatim from the docs' "Build it"
sections; the sync test at the bottom asserts they never drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from realm.testing import Simulator

# Output that must never appear while running a "Build it" transcript.
BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "error",
)


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


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


def builder_in(sim, room_name="The Workshop"):
    room = sim.room(room_name)
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    return room, bilda


# =========================================================================
# 189. In-room minimap — docs/showcase/189_minimap.md
# =========================================================================

MINIMAP_BUILD = [
    "@dig North Wing = north, south",
    "@dig East Wing = east, west",
    "@dig West Wing = west, east",
    "@dig South Wing = south, north",
    "north",
    "@dig Observation Deck = north, south",
    "south",
    r"@set here/render_map = dirs = {'north': [0, -1], 'south': [0, 1], 'east': [1, 0], 'west': [-1, 0]}; w1 = [[dirs[name(e)][0], dirs[name(e)][1], get('#' + str(get_attr(e, 'destination', '')))] for e in exits(me) if name(e) in dirs]; w1 = [c for c in w1 if c[2]]; w2 = [[c[0] + dirs[name(e)][0], c[1] + dirs[name(e)][1], get('#' + str(get_attr(e, 'destination', '')))] for c in w1 for e in exits(c[2]) if name(e) in dirs]; w2 = [c for c in w2 if c[2] and c[2].id != me.id]; seen = {str(c[0]) + ',' + str(c[1]): c[2] for c in (w2 + w1 + [[0, 0, me]])}; grid = ['  '.join(['@' if x == 0 and y == 0 else (capstr(left(name(seen[str(x) + ',' + str(y)]), 1)) if str(x) + ',' + str(y) in seen else '.') for x in [-2, -1, 0, 1, 2]]) for y in [-2, -1, 0, 1, 2]]; pemit(enactor, ansi('ch', 'Nearby') + '\n' + '\n'.join(grid))",
    "@set here/on_look = eval_attr(me, 'render_map')",
]


class TestMinimap:

    async def test_look_paints_the_grid(self, sim):
        _room, bilda = builder_in(sim)
        await build(sim, bilda, MINIMAP_BUILD)

        out = await do(sim, bilda, "look")
        joined = "\n".join(out)
        # The looker is the centre; the four wings ring it; the Observation
        # Deck is a second step north.
        assert "Nearby" in joined
        assert "W  @  E" in joined       # west - you - east
        assert "  N  " in joined          # north wing above centre
        assert "  S  " in joined          # south wing below
        assert "  O  " in joined          # observation deck, two north

    async def test_map_recenters_on_the_looker(self, sim):
        _room, bilda = builder_in(sim)
        await build(sim, bilda, MINIMAP_BUILD)
        # Give the East Wing its own hook so a look there also maps.
        await do(sim, bilda, "east")
        await do(sim, bilda, "@set here/render_map = " + MINIMAP_BUILD[-2].split(" = ", 1)[1])
        await do(sim, bilda, "@set here/on_look = eval_attr(me, 'render_map')")
        out = await do(sim, bilda, "look")
        joined = "\n".join(out)
        # From the East Wing, The Workshop (initial 'T') lies WEST of '@'.
        assert "T  @" in joined
        assert "Nearby" in joined


# =========================================================================
# 190. Score screen — docs/showcase/190_score_screen.md
# =========================================================================

SHEET_BUILD = [
    "@create datapad",
    '@set datapad/skills = ["guns", "stealth", "observation"]',
    r"@set datapad/cmd_sheet = $sheet: p = enactor; skl = get_attr(me, 'skills', []); st = get_attr(p, 'strength', 10); dx = get_attr(p, 'dexterity', 10); iq = get_attr(p, 'intelligence', 10); ht = get_attr(p, 'health', 10); mhp = max(get_attr(p, 'max_hp', st), 1); hp = get_attr(p, 'hp', mhp); fill = clamp((hp * 10) // mhp, 0, 10); bar = '[' + ansi('gh', repeat('#', fill)) + repeat('-', 10 - fill) + ']'; rows = [left(capstr(s) + repeat(' ', 16), 16) + str(get_attr(p, 'skill_' + s, '-')) for s in skl]; pemit(enactor, ansi('ch', capstr(name(p))) + ' the ' + str(get_attr(p, 'template', 'adventurer')) + '\n' + repeat('=', 32) + '\n' + 'ST ' + str(st) + '   DX ' + str(dx) + '   IQ ' + str(iq) + '   HT ' + str(ht) + '\n' + 'HP ' + bar + ' ' + str(hp) + '/' + str(mhp) + '   Dodge ' + str(get_attr(p, 'dodge', 8)) + '   CP ' + str(get_attr(p, 'character_points', 0)) + '\n' + ansi('c', 'Skills') + '\n' + '\n'.join(rows))",
]


def soldier_stats(player):
    player.db.strength = 12
    player.db.dexterity = 11
    player.db.intelligence = 10
    player.db.health = 12
    player.db.hp = 8
    player.db.max_hp = 12
    player.db.dodge = 8
    player.db.character_points = 40
    player.db.template = "soldier"
    player.db.skill_guns = 13
    player.db.skill_stealth = 11
    player.db.skill_observation = 12


class TestScoreScreen:

    async def test_sheet_renders_stats_bar_and_skills(self, sim):
        _room, bilda = builder_in(sim)
        soldier_stats(bilda)
        await build(sim, bilda, SHEET_BUILD)

        out = await do(sim, bilda, "sheet")
        joined = "\n".join(out)
        assert "Bilda" in joined and "soldier" in joined
        assert "ST 12" in joined and "DX 11" in joined
        assert "IQ 10" in joined and "HT 12" in joined
        assert "8/12" in joined and "Dodge 8" in joined and "CP 40" in joined
        # HP bar: 80 // 12 == 6 filled, 4 empty.
        assert "######" in joined and "----" in joined
        # Featured skills, padded and capitalised.
        assert "Guns" in joined and "13" in joined
        assert "Stealth" in joined and "Observation" in joined

    async def test_bar_shrinks_with_damage(self, sim):
        _room, bilda = builder_in(sim)
        soldier_stats(bilda)
        bilda.db.hp = 3           # 30 // 12 == 2 filled
        await build(sim, bilda, SHEET_BUILD)
        out = await do(sim, bilda, "sheet")
        joined = "\n".join(out)
        assert "3/12" in joined
        # 30 // 12 == 2 filled green cells, then eight empties.
        assert "|G##|n" in joined and "--------" in joined


# =========================================================================
# 191. Help system extensions — docs/showcase/191_help_extensions.md
# =========================================================================

GUIDE_BUILD = [
    "@create field guide",
    "drop field guide",
    '@set field guide/index = ["sheet", "map"]',
    "@set field guide/topic_sheet = The datapad sheet verb prints your "
    "vitals at a glance: ST/DX/IQ/HT, a HP bar, and featured skills.",
    "@set field guide/topic_map = Looking in a mapped room paints a small "
    "grid of the rooms around you. The @ marks where you stand.",
    "@set field guide/cmd_index = $guide: pemit(enactor, 'Guide topics: ' "
    "+ ', '.join(get_attr(me, 'index', [])) + '. Type: guide <topic>.')",
    r"@set field guide/cmd_guide = $guide *: t = trim(arg0).lower(); body = get_attr(me, 'topic_' + t, ''); pemit(enactor, ansi('ch', capstr(t)) + '\n' + body) if body else pemit(enactor, 'No guide entry for ' + t + '. Try: guide')",
]


class TestHelpExtensions:

    async def test_native_help_is_generated_from_metadata(self, sim):
        _room, bilda = builder_in(sim)

        out = await do(sim, bilda, "help")
        joined = "\n".join(out)
        assert "Combat:" in joined and "Movement:" in joined

        out = await do(sim, bilda, "help attack")
        joined = "\n".join(out)
        assert "aliases: kill, att" in joined
        assert "usage: attack <target>" in joined

    async def test_native_help_search_fallback(self, sim):
        _room, bilda = builder_in(sim)
        out = await do(sim, bilda, "help merchant")
        joined = "\n".join(out)
        assert "Related:" in joined and "buy" in joined

    async def test_field_guide_lists_and_prints_topics(self, sim):
        _room, bilda = builder_in(sim)
        await build(sim, bilda, GUIDE_BUILD)

        out = await do(sim, bilda, "guide")
        assert "Guide topics: sheet, map. Type: guide <topic>." in "\n".join(out)

        out = await do(sim, bilda, "guide map")
        joined = "\n".join(out)
        assert "Map" in joined
        assert "small grid of the rooms around you" in joined

        out = await do(sim, bilda, "guide compass")
        assert "No guide entry for compass. Try: guide" in "\n".join(out)


# =========================================================================
# 193. GMCP / OOB data — docs/showcase/193_gmcp_oob.md
# =========================================================================

GMCP_BUILD = [
    "@create bridge console",
    "drop bridge console",
    "@set bridge console/hull = 87",
    "@set bridge console/shields = 62",
    "@set bridge console/cmd_scan = $scan: oob(enactor, 'Ship.Status', "
    "{'hull': get_attr(me, 'hull', 100), 'shields': get_attr(me, 'shields', "
    "100)}); pemit(enactor, 'Sensor sweep sent to your console HUD.')",
    "@set bridge console/cmd_readout = $readout: oob(enactor, 'Char.Vitals', "
    "{'hp': get_attr(enactor, 'hp', 10), 'max_hp': get_attr(enactor, "
    "'max_hp', 10)}); pemit(enactor, 'Vitals telemetry pushed.')",
]


class TestGmcpOob:

    async def test_verbs_push_gmcp_packages(self, sim):
        _room, bilda = builder_in(sim)
        bilda.db.hp = 9
        bilda.db.max_hp = 12
        await build(sim, bilda, GMCP_BUILD)

        # Model a client that negotiated GMCP: capture the OOB channel.
        seen_oob = []
        sim.session(bilda).set_oob_writer(lambda p, d: seen_oob.append((p, d)))

        out = await do(sim, bilda, "scan")
        assert "Sensor sweep sent to your console HUD." in out
        assert ("Ship.Status", {"hull": 87, "shields": 62}) in seen_oob

        out = await do(sim, bilda, "readout")
        assert "Vitals telemetry pushed." in out
        assert ("Char.Vitals", {"hp": 9, "max_hp": 12}) in seen_oob

    async def test_no_gmcp_client_is_a_silent_noop(self, sim):
        _room, bilda = builder_in(sim)
        await build(sim, bilda, GMCP_BUILD)
        # No OOB writer negotiated (plain telnet): oob() is a silent no-op,
        # but the visible confirmation still prints — same build, no errors.
        out = await do(sim, bilda, "scan")
        assert "Sensor sweep sent to your console HUD." in out


# =========================================================================
# 196. Personal aliases (nicks) — docs/showcase/196_nicks.md
# =========================================================================

NICK_BUILD = [
    "@create nick ring",
    "@set nick ring/cmd_fetch = $fetch *: force(enactor, 'get ' + trim(arg0))",
    "@set nick ring/cmd_stow = $stow *: force(enactor, 'drop ' + trim(arg0))",
    "@set nick ring/cmd_patrol = $patrol: [force(enactor, c) for c in "
    "['north', 'get relic', 'south']]",
]


class TestNicks:

    async def _built(self, sim):
        barracks = sim.room("Barracks")
        bilda = sim.player("Bilda", location=barracks)
        bilda.add_tag("builder")
        await do(sim, bilda, "@dig Armory = north, south")
        armory = find_one(sim, "Armory")
        sim.obj("pebble", location=barracks)
        sim.obj("relic", location=armory)
        await build(sim, bilda, NICK_BUILD)
        return barracks, armory, bilda

    async def test_parametric_nicks_expand_to_real_commands(self, sim):
        barracks, _armory, bilda = await self._built(sim)

        await do(sim, bilda, "fetch pebble")
        pebble = find_one(sim, "pebble")
        assert pebble.location is bilda, "fetch <x> should force 'get <x>'"

        await do(sim, bilda, "stow pebble")
        assert pebble.location.id == barracks.id, "stow <x> should force 'drop <x>'"

    async def test_multi_step_macro(self, sim):
        barracks, _armory, bilda = await self._built(sim)
        await do(sim, bilda, "patrol")
        relic = find_one(sim, "relic")
        assert relic.location is bilda, "patrol should fetch the relic"
        assert bilda.location.id == barracks.id, "patrol should return home"

    async def test_nicks_are_private_to_the_carrier(self, sim):
        barracks, _armory, bilda = await self._built(sim)
        # A second player without the ring gets no such alias.
        kess = sim.player("Kess", location=barracks)
        out = await do(sim, kess, "patrol")
        assert kess.location.id == barracks.id
        assert not any("relic" in line.lower() for line in out)


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "189_minimap.md": MINIMAP_BUILD,
    "190_score_screen.md": SHEET_BUILD,
    "191_help_extensions.md": GUIDE_BUILD,
    "193_gmcp_oob.md": GMCP_BUILD,
    "196_nicks.md": NICK_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
