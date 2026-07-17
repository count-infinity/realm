"""
Showcase arc: Scripting & Extensibility extras (items 235, 244-249).

Every test drives a real in-process world through the dispatcher with the
exact command lines from the tutorials' "Build it" transcripts
(docs/showcase/235_content_packs.md, 244_player_macros.md,
245_event_bus_tour.md, 246_hot_reload.md, 247_testing_your_game.md,
248_custom_input.md, 249_writing_a_contrib.md), then asserts the outcomes
the tutorials promise.

The transcripts are not duplicated here: ``build_lines()`` reads every
command line straight out of the tutorial's "Build it" fenced blocks, so
the tests execute *what the doc says* and drift is impossible rather than
merely detectable — no sync test needed. (This is the pattern 247 itself
teaches.)

Several of these tutorials interleave *operations* into their build — an
``@export`` and its ``@import`` plan/apply, a live verb rewrite, a
``@reload`` — because that interleaving is the lesson. Those tests assert
between the steps, so they pick lines out of the transcript by content
(``upto`` / ``line_with``) rather than replaying it end to end. Try-it
lines stay literals: the Build-it section is what drifts.
"""

from __future__ import annotations

import json
import re
import types
from pathlib import Path

import pytest

from realm.persistence.worldio import import_objects
from realm.testing import Simulator


def joined(messages: list[str]) -> str:
    return "\n".join(messages)


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


def line_with(lines: list[str], needle: str) -> str:
    """The one Build-it line containing `needle` (ambiguity is a bug)."""
    hits = [line for line in lines if needle in line]
    assert len(hits) == 1, f"want exactly one line with {needle!r}, got {hits}"
    return hits[0]


def upto(lines: list[str], needle: str) -> list[str]:
    """The Build-it lines before the one containing `needle`."""
    return lines[:lines.index(line_with(lines, needle))]


async def run(sim, player, lines) -> None:
    for line in lines:
        await sim.do(player, line)


# =========================================================================
# 235. JSON content packs
# =========================================================================

RELICS = build_lines("235_content_packs.md")
RELICS_SETUP = upto(RELICS, "@export relics")     # the zone and its two defs
PRICE_ATTR = "^*price*:say A medkit runs you forty credits."


@pytest.fixture
def relics_world(tmp_path):
    sim = Simulator()
    sim.store.db_path = str(tmp_path / "world.db3")
    vault = sim.room("Vault")
    bela = sim.player("Bela", location=vault)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=vault)
    try:
        yield sim, bela, alice, tmp_path / "areas" / "relics.realm"
    finally:
        sim.close()


async def build_relics(sim, bela):
    await run(sim, bela, RELICS_SETUP)


@pytest.mark.asyncio
class TestContentPacks:

    async def test_definitions_live_then_export_carries_version(self, relics_world):
        sim, bela, _alice, area = relics_world
        await build_relics(sim, bela)
        sim.seen(bela)

        await sim.do(bela, line_with(RELICS, "@export relics"))
        assert "Exported 3 objects to areas/relics.realm." in sim.seen(bela)

        data = json.loads(area.read_text())
        assert data["realm_format"] == 1                    # the version stamp
        quartermaster = next(o for o in data["objects"]
                             if o["name"] == "Quartermaster")
        assert quartermaster["attrs"]["listen_supply"].startswith("^*supply*:")
        ration = next(o for o in data["objects"] if o["name"] == "ration bar")
        assert ration["attrs"]["heals"] == 2                # item def is data

    async def test_file_edit_then_plan_apply_installs_definition(self, relics_world):
        sim, bela, alice, area = relics_world
        await build_relics(sim, bela)
        await sim.do(bela, line_with(RELICS, "@export relics"))

        # The text-editor step: add one response to the definition in the file.
        data = json.loads(area.read_text())
        quartermaster = next(o for o in data["objects"]
                             if o["name"] == "Quartermaster")
        quartermaster["attrs"]["listen_price"] = PRICE_ATTR
        area.write_text(json.dumps(data, indent=2))
        sim.seen(bela)

        await sim.do(bela, line_with(RELICS, "@import relics"))   # the PLAN
        plan_out = joined(sim.seen(bela))
        assert "Quartermaster" in plan_out and "listen_price" in plan_out
        assert "Run @import/apply relics to execute." in plan_out

        await sim.do(bela, line_with(RELICS, "@import/apply relics"))
        assert any("1 updated" in line for line in sim.seen(bela))

        sim.seen(alice)
        await sim.do(alice, "say What is the price of a medkit?")
        assert ('Quartermaster says, "A medkit runs you forty credits."'
                in sim.seen(alice))

    async def test_version_guard_refuses_a_newer_file(self, relics_world):
        sim, bela, _alice, area = relics_world
        await build_relics(sim, bela)
        await sim.do(bela, line_with(RELICS, "@export relics"))

        data = json.loads(area.read_text())
        data["realm_format"] = 999                          # from a future REALM
        area.write_text(json.dumps(data, indent=2))
        sim.seen(bela)

        await sim.do(bela, line_with(RELICS, "@import relics"))
        assert any("newer REALM" in line for line in sim.seen(bela))

    async def test_pack_command_lists_the_shipped_bundle(self, relics_world):
        sim, bela, _alice, _area = relics_world
        sim.seen(bela)
        await sim.do(bela, "@pack")
        assert "gurps-scifi" in joined(sim.seen(bela))


# =========================================================================
# 244. Player macros
# =========================================================================

SPAM_CMD = "record spam = " + "|".join(["say a"] * 11)   # 11 steps > cap


@pytest.fixture
def macro_world():
    sim = Simulator()
    workshop = sim.room("The Tinker's Workshop")
    vess = sim.player("Vess", location=workshop)
    vess.add_tag("admin")
    ada = sim.player("Ada", location=workshop)
    rook = sim.player("Rook", location=workshop)
    try:
        yield sim, vess, ada, rook
    finally:
        sim.close()


async def hand_over_band(sim, vess):
    await run(sim, vess, build_lines("244_player_macros.md"))
    return next(o for o in sim.store.all_cached() if o.name == "macro band")


@pytest.mark.asyncio
class TestPlayerMacros:

    async def test_record_and_replay_runs_as_the_player(self, macro_world):
        sim, vess, ada, rook = macro_world
        band = await hand_over_band(sim, vess)
        assert band.location is ada
        sim.seen(ada), sim.seen(rook)

        await sim.do(ada, "record hello = say Hello, station.|"
                          "pose taps her comm badge.")
        assert "Recorded hello (2 steps)." in sim.seen(ada)

        sim.seen(ada), sim.seen(rook)
        await sim.do(ada, "play hello")
        ada_saw = sim.seen(ada)
        assert 'You say, "Hello, station."' in ada_saw
        assert "Ada taps her comm badge." in ada_saw
        # The room sees the steps attributed to Ada, not the band.
        rook_saw = sim.seen(rook)
        assert 'Ada says, "Hello, station."' in rook_saw
        assert "Ada taps her comm badge." in rook_saw

    async def test_macro_cannot_escalate_beyond_owner_authority(self, macro_world):
        sim, vess, ada, _rook = macro_world
        await hand_over_band(sim, vess)
        sim.seen(ada)

        await sim.do(ada, "record breakin = @dig Backdoor")
        assert "Recorded breakin (1 steps)." in sim.seen(ada)

        await sim.do(ada, "play breakin")
        # force(Ada, '@dig Backdoor') is Ada typing @dig — and Ada is no
        # builder, so no room is dug.
        assert not any(o.name == "Backdoor" for o in sim.store.all_cached())

    async def test_step_cap_refuses_an_oversized_macro(self, macro_world):
        sim, vess, ada, _rook = macro_world
        band = await hand_over_band(sim, vess)
        sim.seen(ada)

        await sim.do(ada, SPAM_CMD)
        assert "Macros hold at most 10 steps." in sim.seen(ada)
        assert band.db.get("macro_spam") is None            # nothing stored

    async def test_use_lock_keeps_the_band_personal(self, macro_world):
        sim, vess, ada, rook = macro_world
        band = await hand_over_band(sim, vess)
        await sim.do(ada, "record hello = say Hi.")
        stored = band.db.get("macro_hello")

        await sim.do(ada, "drop macro band")                # now Rook can reach it
        sim.seen(rook)
        await sim.do(rook, "record hello = say pwned")
        assert band.db.get("macro_hello") == stored         # lock ignored him
        assert all("Recorded" not in line for line in sim.seen(rook))


# =========================================================================
# 245. Event bus tour
# =========================================================================

@pytest.fixture
def temple_world():
    sim = Simulator()
    temple = sim.room("Temple of the Long Watch")
    bela = sim.player("Bela", location=temple)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=temple)
    try:
        yield sim, bela, alice
    finally:
        sim.close()


@pytest.mark.asyncio
class TestEventBusTour:

    async def test_custom_event_reaches_an_unwired_witness(self, temple_world):
        sim, bela, alice = temple_world
        await run(sim, bela, build_lines("245_event_bus_tour.md"))
        sim.seen(alice)

        await sim.do(alice, "ring bell")
        out = sim.seen(alice)
        # The bell spoke to the room...
        assert "A deep bell tolls across the temple." in out
        # ...and the shrine, never wired to the bell, reacted via on_toll
        # suffix-matching the act()'d event:toll -- reading the event's own
        # data to name what tolled (target) and quote it (adata('message')).
        assert ('The shrine candles flare as temple bell tolls: '
                '"A deep bell tolls across the temple."') in out

    async def test_witness_reads_the_events_data_not_a_wired_reference(
            self, temple_world):
        """The shrine names the bell only because `target` told it. Rename
        the bell and the reaction follows -- nothing is wired at build
        time."""
        sim, bela, alice = temple_world
        await run(sim, bela, build_lines("245_event_bus_tour.md"))
        await sim.do(bela, "@name temple bell = bronze gong")
        sim.seen(alice)

        await sim.do(alice, "ring bell")
        assert any("flare as bronze gong tolls" in line
                   for line in sim.seen(alice))


# =========================================================================
# 246. Hot-reload workflow
# =========================================================================

DOCKS = build_lines("246_hot_reload.md")
# The build is a narrative: the dockmaster and its first reply, then the
# SAME verb rewritten live, then a @reload (which softcode never needs).
DOCKS_V1 = upto(DOCKS, "Bay 1 is full")
HAIL_V2 = line_with(DOCKS, "Bay 1 is full")


@pytest.fixture
def docks_world():
    sim = Simulator()
    docks = sim.room("The Docks")
    bela = sim.player("Bela", location=docks)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=docks)
    try:
        yield sim, bela, alice
    finally:
        sim.close()


@pytest.mark.asyncio
class TestHotReload:

    async def test_softcode_edit_is_live_with_no_reload(self, docks_world):
        sim, bela, alice = docks_world
        await run(sim, bela, DOCKS_V1)
        sim.seen(alice)

        await sim.do(alice, "hail dockmaster")
        assert "Dockmaster: Bay 1 is open." in sim.seen(alice)

        # Rewrite the verb while the world runs — the next hail reads it.
        await sim.do(bela, HAIL_V2)
        sim.seen(alice)
        await sim.do(alice, "hail dockmaster")
        got = sim.seen(alice)
        assert "Dockmaster: Bay 1 is full - try Bay 7." in got
        assert "Bay 1 is open." not in joined(got)

    async def test_reload_rereads_data_rules(self, docks_world):
        sim, bela, _alice = docks_world
        sim.seen(bela)
        await sim.do(bela, line_with(DOCKS, "@reload"))
        assert "Rules reloaded from the world." in sim.seen(bela)


# =========================================================================
# 247. Testing your game  (the harness these tutorials use, tested on itself)
# =========================================================================

@pytest.fixture
def lounge_world():
    sim = Simulator()
    lounge = sim.room("Crew Lounge")
    bela = sim.player("Bela", location=lounge)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=lounge)
    try:
        yield sim, bela, alice
    finally:
        sim.close()


@pytest.mark.asyncio
class TestTestingYourGame:

    async def test_drive_input_and_assert_output(self, lounge_world):
        sim, bela, alice = lounge_world
        await run(sim, bela, build_lines("247_testing_your_game.md"))

        sim.seen(alice)
        await sim.do(alice, "crack cookie")
        line = joined(sim.seen(alice))
        assert "Your fortune:" in line
        assert any(w in line for w in ("travel", "fortune", "caution"))

    async def test_virtual_clock_fires_deferred_waits(self, lounge_world):
        sim, bela, alice = lounge_world
        await run(sim, bela, build_lines("247_testing_your_game.md"))

        sim.seen(alice)
        await sim.do(alice, "ping drone")
        assert sim.seen(alice) == []                 # the wait hasn't fired
        await sim.engine.tick_waits()                # advance the virtual clock
        assert "The drone pings back." in joined(sim.seen(alice))


# =========================================================================
# 248. Custom input handling
# =========================================================================

@pytest.fixture
def quiz_world():
    sim = Simulator()
    # The softcode prompt() needs to find a player's session; wire the
    # engine to the Simulator's session table (a live server hands it a
    # real SessionManager).
    sim.engine.session_manager = types.SimpleNamespace(
        all_sessions=lambda: list(sim._sessions.values()))
    hall = sim.room("Orientation Hall")
    bela = sim.player("Bela", location=hall)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=hall)
    try:
        yield sim, bela, alice
    finally:
        sim.close()


@pytest.mark.asyncio
class TestCustomInput:

    async def test_prompt_captures_next_line_as_answer(self, quiz_world):
        sim, bela, alice = quiz_world
        await run(sim, bela, build_lines("248_custom_input.md"))
        sim.seen(alice)

        await sim.do(alice, "quiz")
        sess = sim.session(alice)
        # The next line is captured, not parsed as a command.
        assert sess.input_handler is not None
        assert any("Capital of the inner colony?" in m for m in sim.seen(alice))

        await sess.input_handler(sess, "Helios")     # the player's raw answer
        assert "Correct!" in sim.seen(alice)
        assert sess.input_handler is None            # released after one line

    async def test_prompt_callback_grades_a_wrong_answer(self, quiz_world):
        sim, bela, alice = quiz_world
        await run(sim, bela, build_lines("248_custom_input.md"))
        sim.seen(alice)

        await sim.do(alice, "quiz")
        sess = sim.session(alice)
        sim.seen(alice)
        await sess.input_handler(sess, "Tyr")
        assert "Wrong. It is Helios." in sim.seen(alice)


# =========================================================================
# 249. Writing a contrib
# =========================================================================

CONTRIB = build_lines("249_writing_a_contrib.md")
CONTRIB_SETUP = upto(CONTRIB, "@export suggestbox")   # the box and its knob


@pytest.fixture
def contrib_world(tmp_path):
    sim = Simulator()
    sim.store.db_path = str(tmp_path / "world.db3")
    mess = sim.room("Mess Hall")
    bela = sim.player("Bela", location=mess)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=mess)
    try:
        yield sim, bela, alice, tmp_path / "areas" / "suggestbox.realm"
    finally:
        sim.close()


@pytest.mark.asyncio
class TestWritingAContrib:

    async def test_feature_reads_its_config_knob(self, contrib_world):
        sim, bela, alice, _area = contrib_world
        await run(sim, bela, CONTRIB_SETUP)
        box = next(o for o in sim.store.all_cached()
                   if o.name == "suggestion box")
        sim.seen(alice)

        await sim.do(alice, "suggest add more benches")
        assert "Thanks - the crew will read it." in sim.seen(alice)
        assert box.db.get("log") == ["add more benches"]     # logged as data

        # The knob is data: override it, and the reply changes, no code edit.
        await sim.do(bela, "@set suggestion box/config_thanks = "
                           "Logged. Command will review.")
        sim.seen(alice)
        await sim.do(alice, "suggest fix the airlock")
        assert "Logged. Command will review." in sim.seen(alice)

    async def test_exported_contrib_is_versioned_and_portable(self, contrib_world):
        sim, bela, _alice, area = contrib_world
        await run(sim, bela, CONTRIB_SETUP)
        sim.seen(bela)

        await sim.do(bela, line_with(CONTRIB, "@export suggestbox"))
        assert any("Exported" in m for m in sim.seen(bela))

        data = json.loads(area.read_text())
        assert data["realm_format"] == 1
        entry = next(o for o in data["objects"]
                     if o["name"] == "suggestion box")
        assert "config_thanks" in entry["attrs"]
        assert entry["attrs"]["cmd_suggest"].startswith("$suggest *:")

        # Portability: import the file into a FRESH world; the feature and
        # its knob survive the round trip intact.
        other = Simulator()
        try:
            created = await import_objects(data, other.store)
            box2 = next(o for o in created if o.name == "suggestion box")
            assert box2.db.get("cmd_suggest").startswith("$suggest *:")
            assert box2.db.get("config_thanks") == "Thanks - the crew will read it."
        finally:
            other.close()
