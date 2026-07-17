"""
Showcase arc: Softcode for builders (items 243, 240, 241, 242, 250).

Every test drives a real in-process world through the dispatcher with
the exact command lines from the tutorials' "Build it" transcripts
(docs/showcase/243_object_verbs.md, 240_builder_triggers.md,
241_yaml_responses.md, 242_inline_functions.md, 250_player_scripting.md),
then asserts the outcomes the tutorials promise — including, for the
capstone, that the sandbox's limits actually hold.
"""

from __future__ import annotations

import json

import pytest

from realm.testing import Simulator


def joined(messages: list[str]) -> str:
    return "\n".join(messages)


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
    """The 243 Build-it transcript, line for line."""
    await sim.do(bela, "@create holo-jukebox")
    await sim.do(bela, "drop holo-jukebox")
    await sim.do(bela, '@set holo-jukebox/tracks = ["Stardock Shanty", '
                       '"Nebula Nocturne", "The Comet\'s Tail"]')
    await sim.do(bela, "@set holo-jukebox/cmd_tracks = $tracks:"
                       "pemit(enactor, 'Track list: ' + "
                       "', '.join(V('tracks', [])))")
    await sim.do(bela, "@set holo-jukebox/cmd_play = $play *:"
                       "hits = [t for t in V('tracks', []) "
                       "if arg0.lower() in t.lower()]; "
                       "remit(here, f'{name(me)} spins up: {hits[0]}') "
                       "if hits else pemit(enactor, "
                       "f'{name(me)} does not know that one.')")


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
    """The 240 Build-it transcript, line for line."""
    await sim.do(bela, "@dig The Gallery = out, in")
    await sim.do(bela, "out")
    await sim.do(bela, "@set here/on_enter = pemit(enactor, "
                       "'Salt wind claws at you as you step onto the gallery.')")
    await sim.do(bela, "in")
    await sim.do(bela, "@create keeper")
    await sim.do(bela, "drop keeper")
    await sim.do(bela, "@set keeper/listen_dark = "
                       "^*dark*:say The lamp must never go dark. Never!")
    await sim.do(bela, "@create storm lantern")
    await sim.do(bela, "drop storm lantern")
    await sim.do(bela, "@set storm lantern/on_get = pemit(enactor, "
                       "'The lantern flares white as you lift it.')")
    await sim.do(bela, "@behavior keeper = script_ticker, interval:30")
    await sim.do(bela, "@set keeper/on_tick = pose polishes the great lens.")


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


async def build_dockside(sim, bela):
    """The 241 Build-it transcript up to the export, line for line."""
    await sim.do(bela, "@zone here = dockside")
    await sim.do(bela, "@create Old Marta")
    await sim.do(bela, "drop Old Marta")
    await sim.do(bela, "@set Old Marta/listen_rumor = ^*rumor*:"
                       "say They say the lighthouse keeper has not slept in years.")
    await sim.do(bela, "@set Old Marta/cmd_menu = $menu:"
                       "pemit(enactor, 'Chowder, hardtack, and black coffee.')")


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

        await sim.do(bela, "@export dockside")
        assert "Exported 2 objects to areas/dockside.realm." in sim.seen(bela)

        data = json.loads(area.read_text())
        marta = next(o for o in data["objects"] if o["name"] == "Old Marta")
        assert marta["attrs"]["listen_rumor"].startswith("^*rumor*:")
        assert marta["attrs"]["cmd_menu"].startswith("$menu:")

    async def test_file_edit_then_plan_apply_installs_response(self, dockside_world):
        sim, bela, alice, area = dockside_world
        await build_dockside(sim, bela)
        await sim.do(bela, "@export dockside")

        # The tutorial's text-editor step: add one response in the file.
        data = json.loads(area.read_text())
        marta = next(o for o in data["objects"] if o["name"] == "Old Marta")
        marta["attrs"]["listen_wreck"] = (
            "^*wreck*:say Half her cargo still lies out on the reef.")
        area.write_text(json.dumps(data, indent=2))
        sim.seen(bela)

        await sim.do(bela, "@import dockside")           # the PLAN
        plan_out = joined(sim.seen(bela))
        assert "update" in plan_out and "Old Marta" in plan_out
        assert "listen_wreck" in plan_out
        assert "Run @import/apply dockside to execute." in plan_out

        await sim.do(bela, "@import/apply dockside")
        assert any("Applied: 0 created, 1 updated" in line
                   for line in sim.seen(bela))

        sim.seen(alice)
        await sim.do(alice, "say What about the wreck?")
        assert ('Old Marta says, "Half her cargo still lies out on the reef."'
                in sim.seen(alice))

    async def test_pack_command_lists_builtin_bundles(self, dockside_world):
        sim, bela, _alice, _area = dockside_world
        sim.seen(bela)
        await sim.do(bela, "@pack")
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


THORNS_BLOCK = ("[[result = ansi('rh', 'Thorns glint among the stems.') "
                "if skill('observation') >= 12 else '']]")
VISITS_BLOCK = ("[[n = incr('visits_' + viewer.id); "
                "result = f\"You have paused here {n} "
                "time{'' if n == 1 else 's'}.\"]]")


async def build_garden(sim, bela, alice, rube):
    """The 242 Build-it transcript, line for line."""
    await sim.do(bela, "@dig The Garden = north, south")
    for who in (bela, alice, rube):
        await sim.do(who, "north")
    await sim.do(bela,
                 f"@desc here = Roses climb a broken trellis. {THORNS_BLOCK}")
    await sim.do(bela, "@create mood crystal")
    await sim.do(bela, "drop mood crystal")
    await sim.do(bela, "@desc mood crystal = A fist-sized crystal on a "
                       "plinth. [[result = 'Right now it glows ' + "
                       "extract('amber violet seafoam', rand(1, 3)) + '.']]")


@pytest.mark.asyncio
class TestInlineFunctions:

    async def test_skill_gated_desc_line_is_per_viewer(self, garden_world):
        sim, bela, alice, rube = garden_world
        await build_garden(sim, bela, alice, rube)
        sim.seen(alice), sim.seen(rube)

        await sim.do(alice, "look")
        assert "Thorns glint among the stems." in joined(sim.seen(alice))

        await sim.do(rube, "look")
        rube_saw = joined(sim.seen(rube))
        assert "Roses climb a broken trellis." in rube_saw
        assert "Thorns" not in rube_saw          # the block rendered to ''

    async def test_random_block_reevaluates_at_render(self, garden_world):
        sim, bela, alice, rube = garden_world
        await build_garden(sim, bela, alice, rube)
        sim.seen(alice)

        await sim.do(alice, "look mood crystal")
        out = joined(sim.seen(alice))
        assert "Right now it glows" in out
        assert any(color in out for color in ("amber", "violet", "seafoam"))

    async def test_stateful_block_counts_visits_per_viewer(self, garden_world):
        sim, bela, alice, rube = garden_world
        await build_garden(sim, bela, alice, rube)
        await sim.do(bela, f"@desc here = Roses climb a broken trellis. "
                           f"{THORNS_BLOCK} {VISITS_BLOCK}")
        sim.seen(alice), sim.seen(rube)

        await sim.do(alice, "look")
        first = joined(sim.seen(alice))
        assert "You have paused here 1 time." in first
        assert "Thorns glint among the stems." in first   # both blocks render

        await sim.do(alice, "look")
        assert "You have paused here 2 times." in joined(sim.seen(alice))

        await sim.do(rube, "look")                       # separate counter
        assert "You have paused here 1 time." in joined(sim.seen(rube))

    async def test_computed_speech_from_trigger_script(self, garden_world):
        sim, bela, alice, rube = garden_world
        await build_garden(sim, bela, alice, rube)
        await sim.do(bela, "@set mood crystal/cmd_consult = $consult crystal:"
                           "say('The auspices favor ' + "
                           "extract('war trade rest', rand(1, 3)) + '.')")
        sim.seen(alice)

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


async def hand_over_cube(sim, vess):
    """The 250 staff-side Build-it transcript, line for line."""
    await sim.do(vess, "@create Chrono-Cube")
    await sim.do(vess, "@set Chrono-Cube/cmd_program = $program cube = *:"
                       "set_attr(me, 'on_use', arg0); "
                       "pemit(enactor, 'The cube chimes: program stored.')")
    await sim.do(vess, "@lock/use Chrono-Cube = caller == owner")
    await sim.do(vess, "@chown Chrono-Cube = Ada")
    await sim.do(vess, "@examine Chrono-Cube")
    await sim.do(vess, "@untag Chrono-Cube = halt")
    await sim.do(vess, "give Chrono-Cube to Ada")
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

        await sim.do(ada, "program cube = f = lambda: f(); f(); "
                          "pemit(enactor, 'bottomless')")
        await sim.do(ada, "use cube")

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
