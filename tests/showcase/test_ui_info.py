"""
Showcase "Information & UI" — checklist items 189, 190, 191, 193, 196.

Verifies the tutorials in docs/showcase/ (189_minimap.md, 190_score_screen.md,
191_help_extensions.md, 193_gmcp_oob.md, 196_nicks.md) by driving a real
in-process world — realm.testing.Simulator wires the same store/propagation/
scripting/dispatcher stack a live GameServer does — with each tutorial's EXACT
"Build it" command lines (raw input in, session output out).

The build lines are read straight out of the markdown at run time, so these
tests execute *what the tutorial says* — a doc edit that breaks a build breaks
this suite, and drift is impossible rather than merely detectable.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

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


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


async def build(sim, player, doc_name):
    """Run a tutorial's Build-it transcript; fail loudly if a line misfires."""
    for line in build_lines(doc_name):
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

class TestMinimap:

    async def test_look_paints_the_grid(self, sim):
        _room, bilda = builder_in(sim)
        await build(sim, bilda, "189_minimap.md")

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
        await build(sim, bilda, "189_minimap.md")
        # Give the East Wing its own hook so a look there also maps: reuse
        # the tutorial's own renderer line, minus its `@set here/render_map =`.
        renderer = build_lines("189_minimap.md")[-2].split(" = ", 1)[1]
        await do(sim, bilda, "east")
        await do(sim, bilda, "@set here/render_map = " + renderer)
        await do(sim, bilda, "@set here/on_look = eval_attr(me, 'render_map')")
        out = await do(sim, bilda, "look")
        joined = "\n".join(out)
        # From the East Wing, The Workshop (initial 'T') lies WEST of '@'.
        assert "T  @" in joined
        assert "Nearby" in joined


# =========================================================================
# 190. Score screen — docs/showcase/190_score_screen.md
# =========================================================================

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
        await build(sim, bilda, "190_score_screen.md")

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
        await build(sim, bilda, "190_score_screen.md")
        out = await do(sim, bilda, "sheet")
        joined = "\n".join(out)
        assert "3/12" in joined
        # 30 // 12 == 2 filled green cells, then eight empties.
        assert "|G##|n" in joined and "--------" in joined


# =========================================================================
# 191. Help system extensions — docs/showcase/191_help_extensions.md
# =========================================================================

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
        await build(sim, bilda, "191_help_extensions.md")

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

class TestGmcpOob:

    async def test_verbs_push_gmcp_packages(self, sim):
        _room, bilda = builder_in(sim)
        bilda.db.hp = 9
        bilda.db.max_hp = 12
        await build(sim, bilda, "193_gmcp_oob.md")

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
        await build(sim, bilda, "193_gmcp_oob.md")
        # No OOB writer negotiated (plain telnet): oob() is a silent no-op,
        # but the visible confirmation still prints — same build, no errors.
        out = await do(sim, bilda, "scan")
        assert "Sensor sweep sent to your console HUD." in out


# =========================================================================
# 196. Personal aliases (nicks) — docs/showcase/196_nicks.md
# =========================================================================

class TestNicks:

    async def _built(self, sim):
        barracks = sim.room("Barracks")
        bilda = sim.player("Bilda", location=barracks)
        bilda.add_tag("builder")
        await do(sim, bilda, "@dig Armory = north, south")
        armory = find_one(sim, "Armory")
        sim.obj("pebble", location=barracks)
        sim.obj("relic", location=armory)
        await build(sim, bilda, "196_nicks.md")
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
