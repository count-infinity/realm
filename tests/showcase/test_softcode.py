"""
Showcase arc: Softcode for builders (items 243, 240, 241, 242, 250).

Every test drives a real in-process world through the dispatcher with
the command lines from the tutorials' "Build it" transcripts
(docs/showcase/243_object_verbs.md, 240_builder_triggers.md,
241_yaml_responses.md, 242_inline_functions.md, 250_player_scripting.md),
then asserts the outcomes the tutorials promise — including, for the
capstone, that the sandbox's limits actually hold.

Those lines are read out of the markdown, never mirrored here, so the
tutorial is the source of truth and cannot drift from the test. Two of
these tutorials interleave command blocks with *expected output* and
*JSON* blocks inside their Build it (and 250's is typed by three
different people), so blocks are picked by their opening line with
`build_block` rather than swept up wholesale — a doc that renames a
block's opener fails loudly here instead of silently skipping it.
"""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"


def build_section(doc_name: str) -> str:
    """The tutorial's "Build it" section, raw."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    return match.group(1)


def build_blocks(doc_name: str) -> list[list[str]]:
    """The "Build it" fenced blocks that hold typed lines (```text or a
    bare ```), each as its list of non-blank lines. Fences are walked
    rather than regexed so that a ```json block — data the tutorial has
    you paste into a file, not a line you type — is skipped whole
    instead of having its closing fence mistaken for an opening one."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    info = ""
    for line in build_section(doc_name).splitlines():
        if line.startswith("```"):
            if current is None:
                current, info = [], line[3:].strip()
            else:
                if info in ("", "text") and any(l.strip() for l in current):
                    blocks.append([l for l in current if l.strip()])
                current = None
        elif current is not None:
            current.append(line)
    assert current is None, f"{doc_name}: unclosed fence in Build it"
    assert blocks, f"{doc_name}: empty Build it"
    return blocks


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" — for the
    tutorials whose build is one actor's uninterrupted transcript."""
    return [line for block in build_blocks(doc_name) for line in block]


def build_block(doc_name: str, opener: str) -> list[str]:
    """The one "Build it" block that starts with `opener` — for
    tutorials whose build mixes typed lines with printed output."""
    hits = [b for b in build_blocks(doc_name) if b[0].startswith(opener)]
    assert len(hits) == 1, (
        f"{doc_name}: expected exactly 1 Build-it block opening {opener!r}, "
        f"found {len(hits)}")
    return hits[0]


def joined(messages: list[str]) -> str:
    return "\n".join(messages)


async def do_block(sim, actor, doc_name: str, opener: str) -> None:
    """Type one Build-it block, as the person the tutorial has typing it."""
    for line in build_block(doc_name, opener):
        await sim.do(actor, line)


# --- 243. Object-verb pattern -------------------------------------------------


@pytest.fixture
def jukebox_world():
    sim = Simulator()
    cantina = sim.room("The Void's Edge Cantina")
    bela = sim.player("Bela", location=cantina)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=cantina)
    bob = sim.player("Bob", location=cantina)
    try:
        yield sim, bela, alice, bob
    finally:
        sim.close()


async def build_jukebox(sim, bela):
    """The whole 243 Build-it transcript, read from the doc. It ends with
    the tutorial's own demonstrations: the use lock set and then cleared
    again, and the $say hijack that the dispatcher refuses to honour."""
    for line in build_lines("243_object_verbs.md"):
        await sim.do(bela, line)
    sim.seen(bela)


@pytest.mark.asyncio
class TestObjectVerbs:

    async def test_verbs_answer_and_capture_wildcards(self, jukebox_world):
        sim, bela, alice, bob = jukebox_world
        await build_jukebox(sim, bela)
        sim.seen(alice), sim.seen(bob)

        await sim.do(alice, "tracks")
        assert ("Track list: Stardock Shanty, Nebula Nocturne, "
                "The Comet's Tail") in sim.seen(alice)

        await sim.do(alice, "play comet")
        line = "holo-jukebox spins up: The Comet's Tail"
        assert line in sim.seen(alice)
        assert line in sim.seen(bob)          # remit reaches the room

        await sim.do(alice, "play polka")
        assert "holo-jukebox does not know that one." in sim.seen(alice)
        assert sim.seen(bob) == []            # the miss is private

    async def test_use_lock_gates_the_verbs(self, jukebox_world):
        sim, bela, alice, _bob = jukebox_world
        await build_jukebox(sim, bela)
        await sim.do(bela, "@lock/use holo-jukebox = caller == owner")
        assert "Lock/use set on holo-jukebox." in sim.seen(bela)
        sim.seen(alice)

        await sim.do(alice, "play comet")     # not the owner: silence
        assert sim.seen(alice) == []

        await sim.do(bela, "play comet")      # the owner still may
        assert "holo-jukebox spins up: The Comet's Tail" in sim.seen(bela)

        await sim.do(bela, "@lock/use holo-jukebox =")
        assert "Lock/use cleared from holo-jukebox." in sim.seen(bela)
        sim.seen(alice)
        await sim.do(alice, "play comet")
        assert "holo-jukebox spins up: The Comet's Tail" in sim.seen(alice)

    async def test_builtins_dispatch_before_dollar_triggers(self, jukebox_world):
        sim, bela, alice, bob = jukebox_world
        await build_jukebox(sim, bela)
        await sim.do(bela, "@set holo-jukebox/cmd_hijack = "
                           "$say *:pemit(enactor, 'GOTCHA')")
        sim.seen(alice), sim.seen(bob)

        await sim.do(alice, "say hello there")

        assert sim.seen(alice) == ['You say, "hello there"']
        assert sim.seen(bob) == ['Alice says, "hello there"']  # no GOTCHA


# --- 240. Builder trigger system ----------------------------------------------


@pytest.fixture
def lighthouse_world():
    sim = Simulator()
    lamp = sim.room("The Lamp Room")
    bela = sim.player("Bela", location=lamp)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=lamp)
    try:
        yield sim, bela, alice
    finally:
        sim.close()


async def build_lighthouse(sim, bela):
    """The whole 240 Build-it transcript, read from the doc — including
    its closing `@tr keeper/on_tick` check-your-work line."""
    for line in build_lines("240_builder_triggers.md"):
        await sim.do(bela, line)
    sim.seen(bela)


@pytest.mark.asyncio
class TestBuilderTriggers:

    async def test_on_enter_greets_the_walker(self, lighthouse_world):
        sim, bela, alice = lighthouse_world
        await build_lighthouse(sim, bela)
        sim.seen(alice)

        await sim.do(alice, "out")
        assert ("Salt wind claws at you as you step onto the gallery."
                in sim.seen(alice))

    async def test_listen_trigger_overhears_keyword(self, lighthouse_world):
        sim, bela, alice = lighthouse_world
        await build_lighthouse(sim, bela)
        sim.seen(alice)

        await sim.do(alice, "say Looks like it's getting dark out there.")
        assert ('keeper says, "The lamp must never go dark. Never!"'
                in sim.seen(alice))

    async def test_on_get_fires_when_item_taken(self, lighthouse_world):
        sim, bela, alice = lighthouse_world
        await build_lighthouse(sim, bela)
        sim.seen(alice)

        await sim.do(alice, "get storm lantern")
        out = sim.seen(alice)
        assert "The lantern flares white as you lift it." in out
        assert any("pick up" in line for line in out)

    async def test_ticker_attached_and_test_fired_with_tr(self, lighthouse_world):
        sim, bela, alice = lighthouse_world
        await build_lighthouse(sim, bela)
        keeper = next(o for o in sim.store.all_cached() if o.name == "keeper")
        assert any(b.behavior_id == "script_ticker" and
                   b.params.get("interval") == 30
                   for b in keeper.get_behaviors())
        sim.seen(alice)

        await sim.do(bela, "@tr keeper/on_tick")
        assert "Triggered keeper/on_tick." in sim.seen(bela)
        assert "keeper polishes the great lens." in sim.seen(alice)

    async def test_halt_tag_silences_every_trigger(self, lighthouse_world):
        sim, bela, alice = lighthouse_world
        await build_lighthouse(sim, bela)
        await sim.do(bela, "@tag keeper = halt")
        sim.seen(alice)

        await sim.do(alice, "say So dark tonight.")
        assert all("never go dark" not in line.lower()
                   for line in sim.seen(alice))


# --- 241. Response scripting in data --------------------------------------------


@pytest.fixture
def dockside_world(tmp_path):
    sim = Simulator()
    # The Simulator's in-memory store has no on-disk home; give it one so
    # @export/@import resolve data/areas/ inside the test sandbox.
    sim.store.db_path = str(tmp_path / "world.db3")
    tavern = sim.room("The Salty Anchor")
    bela = sim.player("Bela", location=tavern)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=tavern)
    try:
        yield sim, bela, alice, tmp_path / "areas" / "dockside.realm"
    finally:
        sim.close()


DOC_241 = "241_yaml_responses.md"


def added_response() -> dict:
    """The one attribute 241 has you add by hand in a text editor — read
    from the tutorial's own JSON block, so the file edit the test makes
    is literally the edit the doc prints."""
    blocks = re.findall(r"```json\n(.*?)```", build_section(DOC_241), re.S)
    added = json.loads("{" + blocks[-1].strip().rstrip(",") + "}")
    assert len(added) == 1, f"{DOC_241}: expected one added response key"
    return added


async def build_dockside(sim, bela):
    """The 241 Build-it transcript up to the export, read from the doc."""
    for line in build_block(DOC_241, "@zone here = dockside"):
        await sim.do(bela, line)


@pytest.mark.asyncio
class TestResponsesInData:

    async def test_responses_work_live_before_export(self, dockside_world):
        sim, bela, alice, _area = dockside_world
        await build_dockside(sim, bela)
        sim.seen(bela)

        await sim.do(bela, "say Any rumors, Marta?")
        assert ('Old Marta says, "They say the lighthouse keeper has not '
                'slept in years."') in sim.seen(bela)

        sim.seen(alice)
        await sim.do(alice, "menu")
        assert "Chowder, hardtack, and black coffee." in sim.seen(alice)

    async def test_export_carries_triggers_as_data(self, dockside_world):
        sim, bela, _alice, area = dockside_world
        await build_dockside(sim, bela)
        sim.seen(bela)

        await do_block(sim, bela, DOC_241, "@export dockside")
        assert "Exported 2 objects to areas/dockside.realm." in sim.seen(bela)

        data = json.loads(area.read_text())
        marta = next(o for o in data["objects"] if o["name"] == "Old Marta")
        assert marta["attrs"]["listen_rumor"].startswith("^*rumor*:")
        assert marta["attrs"]["cmd_menu"].startswith("$menu:")

    async def test_file_edit_then_plan_apply_installs_response(self, dockside_world):
        sim, bela, alice, area = dockside_world
        await build_dockside(sim, bela)
        await do_block(sim, bela, DOC_241, "@export dockside")

        # The tutorial's text-editor step: add its one response to the file.
        data = json.loads(area.read_text())
        marta = next(o for o in data["objects"] if o["name"] == "Old Marta")
        marta["attrs"].update(added_response())
        area.write_text(json.dumps(data, indent=2))
        sim.seen(bela)

        await do_block(sim, bela, DOC_241, "@import dockside")   # the PLAN
        plan_out = joined(sim.seen(bela))
        assert "update" in plan_out and "Old Marta" in plan_out
        assert "listen_wreck" in plan_out
        assert "Run @import/apply dockside to execute." in plan_out

        await do_block(sim, bela, DOC_241, "@import/apply dockside")
        assert any("Applied: 0 created, 1 updated" in line
                   for line in sim.seen(bela))

        sim.seen(alice)
        await sim.do(alice, "say What about the wreck?")
        assert ('Old Marta says, "Half her cargo still lies out on the reef."'
                in sim.seen(alice))

    async def test_pack_command_lists_builtin_bundles(self, dockside_world):
        sim, bela, _alice, _area = dockside_world
        sim.seen(bela)
        await do_block(sim, bela, DOC_241, "@pack")
        assert "gurps-scifi" in joined(sim.seen(bela))


# --- 242. Inline functions in text ----------------------------------------------


@pytest.fixture
def garden_world():
    sim = Simulator()
    path = sim.room("The Cliff Path")
    bela = sim.player("Bela", location=path)
    bela.add_tag("builder")
    alice = sim.player("Alice", location=path)
    alice.db.set("skill_observation", 14)
    rube = sim.player("Rube", location=path)
    rube.db.set("skill_observation", 4)
    try:
        yield sim, bela, alice, rube
    finally:
        sim.close()


async def build_garden(sim, bela):
    """The whole 242 Build-it transcript, read from the doc — including
    its final `@desc here`, which re-hangs the room's description with
    both the thorns block and the visit counter."""
    for line in build_lines("242_inline_functions.md"):
        await sim.do(bela, line)
    sim.seen(bela)


async def enter_garden(sim, who) -> str:
    """Walk a viewer in. Arriving renders the room, so this *is* their
    first look at it — which is what the visit counter counts."""
    await sim.do(who, "north")
    return joined(sim.seen(who))


@pytest.mark.asyncio
class TestInlineFunctions:

    async def test_skill_gated_desc_line_is_per_viewer(self, garden_world):
        sim, bela, alice, rube = garden_world
        await build_garden(sim, bela)

        assert "Thorns glint among the stems." in await enter_garden(sim, alice)

        rube_saw = await enter_garden(sim, rube)
        assert "Roses climb a broken trellis." in rube_saw
        assert "Thorns" not in rube_saw          # the block rendered to ''

    async def test_random_block_reevaluates_at_render(self, garden_world):
        sim, bela, alice, _rube = garden_world
        await build_garden(sim, bela)
        await enter_garden(sim, alice)

        await sim.do(alice, "look mood crystal")
        out = joined(sim.seen(alice))
        assert "Right now it glows" in out
        assert any(color in out for color in ("amber", "violet", "seafoam"))

    async def test_stateful_block_counts_visits_per_viewer(self, garden_world):
        sim, bela, alice, rube = garden_world
        await build_garden(sim, bela)

        first = await enter_garden(sim, alice)
        assert "You have paused here 1 time." in first
        assert "Thorns glint among the stems." in first   # both blocks render

        await sim.do(alice, "look")
        assert "You have paused here 2 times." in joined(sim.seen(alice))

        # Rube's count is his own, and starts where hers did.
        assert "You have paused here 1 time." in await enter_garden(sim, rube)

    async def test_computed_speech_from_trigger_script(self, garden_world):
        sim, bela, alice, _rube = garden_world
        await build_garden(sim, bela)
        await enter_garden(sim, alice)

        await sim.do(alice, "consult crystal")
        out = joined(sim.seen(alice))
        assert 'mood crystal says, "The auspices favor' in out
        assert any(word in out for word in ("war", "trade", "rest"))


# --- 250. Restricted player scripting ---------------------------------------------


@pytest.fixture
def workshop_world():
    sim = Simulator()
    workshop = sim.room("The Tinker's Workshop")
    vess = sim.player("Vess", location=workshop)
    vess.add_tag("admin")
    ada = sim.player("Ada", location=workshop)
    rook = sim.player("Rook", location=workshop)
    rook.db.set("hp", 10)
    try:
        yield sim, vess, ada, rook
    finally:
        sim.close()


DOC_250 = "250_player_scripting.md"

# 250's Build it is typed by three people and interleaves their commands
# with the output the tutorial promises, so each block is claimed by its
# opening line. Ada's attacks live one block apiece, next to the wall
# each one tests.
STAFF_BUILD = "@create Chrono-Cube"
STAFF_HANDOVER = "@examine Chrono-Cube"
ADA_PROGRAMS = "program cube = pemit(enactor, f'Tick."
ADA_HEXES_ROOK = 'program cube = pemit(enactor, f"hex result:'
ADA_IMPORTS = "program cube = import os;"
ADA_MARATHON = "program cube = [rand(1, 2)"
ADA_FLOODS = "program cube = for i in range(5000):"
ADA_RECURSES = "program cube = f = lambda: f();"
ADA_DROPS_CUBE = "drop cube"
ROOK_GRABS = "program cube = pemit(enactor, 'MINE NOW')"


async def hand_over_cube(sim, vess):
    """The 250 staff-side Build-it transcript, read from the doc: build
    the shell, @chown it (which halts it), review, wake it, hand it over."""
    await do_block(sim, vess, DOC_250, STAFF_BUILD)
    await do_block(sim, vess, DOC_250, STAFF_HANDOVER)
    return next(o for o in sim.store.all_cached() if o.name == "Chrono-Cube")


@pytest.mark.asyncio
class TestPlayerScripting:

    async def test_chown_halts_scripted_object_for_review(self, workshop_world):
        sim, vess, ada, _rook = workshop_world
        await sim.do(vess, "@create Chrono-Cube")
        await sim.do(vess, "@set Chrono-Cube/cmd_program = $program cube = *:"
                           "set_attr(me, 'on_use', arg0); "
                           "pemit(enactor, 'The cube chimes: program stored.')")
        await sim.do(vess, "@lock/use Chrono-Cube = caller == owner")
        sim.seen(vess)

        await sim.do(vess, "@chown Chrono-Cube = Ada")
        out = joined(sim.seen(vess))
        assert "halted for review" in out
        assert "transferred from Vess to Ada" in out

        cube = next(o for o in sim.store.all_cached()
                    if o.name == "Chrono-Cube")
        assert cube.has_tag("halt")
        assert cube.owner is ada

        await sim.do(vess, "@untag Chrono-Cube = halt")
        assert not cube.has_tag("halt")

    async def test_player_programs_and_fires_her_gadget(self, workshop_world):
        sim, vess, ada, _rook = workshop_world
        cube = await hand_over_cube(sim, vess)
        assert cube.location is ada
        sim.seen(ada)

        await sim.do(ada, "program cube = pemit(enactor, f'Tick. The cube "
                          "counts a heartbeat for {name(enactor)}.')")
        assert "The cube chimes: program stored." in sim.seen(ada)

        await sim.do(ada, "use cube")
        assert "Tick. The cube counts a heartbeat for Ada." in sim.seen(ada)

    async def test_owner_authority_cannot_touch_another_player(self, workshop_world):
        sim, vess, ada, rook = workshop_world
        await hand_over_cube(sim, vess)
        sim.seen(ada)

        await sim.do(ada, "program cube = pemit(enactor, "
                          "f\"hex result: {set_attr(get('Rook'), 'hp', 0)}\")")
        await sim.do(ada, "use cube")

        assert "hex result: False" in sim.seen(ada)   # denied, not crashed
        assert rook.db.get("hp") == 10                # sheet untouched

    async def test_ast_validation_rejects_import_wholesale(self, workshop_world):
        sim, vess, ada, _rook = workshop_world
        await hand_over_cube(sim, vess)
        sim.seen(ada)

        await sim.do(ada, "program cube = import os; "
                          "pemit(enactor, 'escaped!')")
        await sim.do(ada, "use cube")

        # Validation fails the whole program: even the pemit never runs.
        assert all("escaped!" not in line for line in sim.seen(ada))

    async def test_call_limit_kills_the_marathon(self, workshop_world):
        sim, vess, ada, _rook = workshop_world
        await hand_over_cube(sim, vess)
        sim.seen(ada)

        await sim.do(ada, "program cube = [rand(1, 2) for i in range(30000)]; "
                          "pemit(enactor, 'survived the marathon')")
        await sim.do(ada, "use cube")

        assert all("survived the marathon" not in line
                   for line in sim.seen(ada))

    async def test_output_limit_swallows_the_flood(self, workshop_world):
        sim, vess, ada, rook = workshop_world
        await hand_over_cube(sim, vess)
        sim.seen(ada), sim.seen(rook)

        await sim.do(ada, "program cube = for i in range(5000): say('spam')")
        await sim.do(ada, "use cube")

        # The run died at the output cap before anything was emitted.
        assert all("spam" not in line for line in sim.seen(ada))
        assert all("spam" not in line for line in sim.seen(rook))

    async def test_recursion_limit_holds(self, workshop_world):
        sim, vess, ada, _rook = workshop_world
        await hand_over_cube(sim, vess)
        sim.seen(ada)

        await do_block(sim, ada, DOC_250, ADA_RECURSES)

        assert all("bottomless" not in line for line in sim.seen(ada))

    async def test_use_lock_keeps_strangers_out(self, workshop_world):
        sim, vess, ada, rook = workshop_world
        cube = await hand_over_cube(sim, vess)
        sim.seen(ada)
        await sim.do(ada, "program cube = pemit(enactor, f'Tick. The cube "
                          "counts a heartbeat for {name(enactor)}.')")
        stored = cube.db.get("on_use")

        await sim.do(ada, "drop cube")               # now Rook can reach it
        sim.seen(rook)
        await sim.do(rook, "program cube = pemit(enactor, 'MINE NOW')")

        assert cube.db.get("on_use") == stored       # lock ignored him
        assert all("chimes" not in line for line in sim.seen(rook))
        await sim.do(ada, "get cube")
        assert cube.location is ada


# --- Build-it coverage -------------------------------------------------------

# 243, 240 and 242 are swept whole by build_lines(), so every line in them
# runs by construction. 241 and 250 are picked block by block (their builds
# interleave typed lines with printed output, and 250's is typed by three
# people) — so those two need a guard: every block is either claimed by a
# test above or is output the tutorial prints back at you. Add a block to
# either doc and this fails until someone drives it.

CLAIMED_241 = ["@zone here = dockside", "@export dockside", "@import dockside",
               "@import/apply dockside", "@pack"]
PRINTED_241 = ["Plan for area 'dockside':"]

CLAIMED_250 = [STAFF_BUILD, STAFF_HANDOVER, ADA_PROGRAMS, ADA_HEXES_ROOK,
               ADA_IMPORTS, ADA_MARATHON, ADA_FLOODS, ADA_RECURSES,
               ADA_DROPS_CUBE, ROOK_GRABS]
PRINTED_250 = ["The cube chimes: program stored."]


@pytest.mark.parametrize("doc_name, claimed, printed", [
    (DOC_241, CLAIMED_241, PRINTED_241),
    (DOC_250, CLAIMED_250, PRINTED_250),
])
def test_every_build_block_is_exercised_or_is_output(doc_name, claimed, printed):
    for block in build_blocks(doc_name):
        assert any(block[0].startswith(o) for o in claimed + printed), (
            f"{doc_name}: Build-it block opening {block[0]!r} is neither "
            f"driven by a test nor listed as printed output")
