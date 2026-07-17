"""
Showcase "Building & World Tools" — checklist items 165-175.

Verifies docs/showcase/165_prototype_library.md .. 175_player_housing.md
by driving a real in-process world — the realm.testing.Simulator wires
the same store/propagation/scripting/dispatcher stack a live GameServer
does — with the tutorials' EXACT command lines (raw input in, session
output out).

Each build transcript is read straight out of its markdown at run time,
so these tests execute *what the tutorial says*: a doc edit that breaks
a build breaks this suite, and drift is impossible rather than merely
detectable.

Notes on the harness:
- prompt()-driven wizards (170) find sessions through the engine's
  session_manager; we install one over the sim's sessions and feed the
  answer by calling sess.input_handler directly, the way the act-3
  tutorial test does. The dispatcher's own path never consults the
  input handler.
- @export/@import (166, 173) write under data/areas/ relative to the
  active manager's db_path; the sim's in-memory store has none, so each
  test that touches area files stamps a temp db_path first.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from realm.testing import Simulator

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

BUILD_FAILURE_MARKERS = (
    "Unknown command",
    "Permission denied",
    "Usage:",
    "not found",
    "Script error",
    "Eval error",
    "Bad condition",
    "Bad parameter",
    "Unknown behavior",
    "Validation failed",
    "Execution error",
)


# --- Harness ---------------------------------------------------------------


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


def workshop_and_builder(sim):
    """The standing start of every tutorial: a room and a builder in it."""
    room = sim.room("The Workshop")
    room.owner = None
    bilda = sim.player("Bilda", location=room)
    bilda.add_tag("builder")
    room.owner = bilda            # the builder owns their workshop
    return room, bilda


async def build(sim, player, doc_name):
    """Run a tutorial's Build-it transcript; fail loudly if a line misfires."""
    for line in build_lines(doc_name):
        await sim.do(player, line)
        out = "\n".join(sim.seen(player))
        for marker in BUILD_FAILURE_MARKERS:
            assert marker not in out, f"build line {line!r} failed: {out!r}"


async def do(sim, player, line):
    await sim.do(player, line)
    return "\n".join(sim.seen(player))


def find_one(sim, name):
    matches = sim.store.find_cached(name=name)
    assert matches, f"no object named {name!r} in the world"
    return matches[0]


def all_named(sim, name):
    return [o for o in sim.store.all_cached() if o.name == name]


def wire_sessions(sim, *players):
    """Let prompt() locate these players' sessions."""
    sim.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: [sim.session(p) for p in players])


def temp_areas(sim, tmp_path):
    """Give the in-memory store a db_path so area files land in tmp."""
    sim.store.db_path = str(tmp_path / "game.db3")


# =========================================================================
# 165. Prototype library — docs/showcase/165_prototype_library.md
# =========================================================================

class TestPrototypeLibrary:

    async def test_mint_merges_prototype_over_its_parent(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "165_prototype_library.md")

        # A base prototype mints its own values.
        out = await do(sim, bilda, "mint sword")
        assert "Minted a sword: dmg 3, wt 2." in out
        sword = all_named(sim, "a sword")[0]
        assert sword.db.get("damage") == 3 and sword.db.get("weight") == 2

        # The child overrides damage but INHERITS weight from the parent
        # by dict-merge — the "inheritance" the parent link can't give.
        out = await do(sim, bilda, "mint greatsword")
        assert "Minted a greatsword: dmg 6, wt 2." in out
        gs = all_named(sim, "a greatsword")[0]
        assert gs.db.get("damage") == 6      # overridden
        assert gs.db.get("weight") == 2      # inherited

        out = await do(sim, bilda, "mint dagger")
        assert "No such prototype." in out

    async def test_clone_duplicates_the_whole_library(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "165_prototype_library.md")
        # @clone copies attrs (the prototype dicts and the $mint verb) —
        # the library is data, so a second rack is one command.
        out = await do(sim, bilda, "@clone prototype rack = spare rack")
        assert "Cloned" in out
        spare = all_named(sim, "spare rack")[0]
        assert spare.db.get("proto_sword")["damage"] == 3
        out = await do(sim, bilda, "mint sword")
        assert "Minted a sword" in out         # the copy's verb works too


# =========================================================================
# 166. Batchcode areas — docs/showcase/166_batchcode_areas.md
# =========================================================================

class TestBatchcodeAreas:

    async def test_foreach_bulk_edit_then_export_import_roundtrip(
            self, sim, tmp_path):
        temp_areas(sim, tmp_path)
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "166_batchcode_areas.md")

        # @foreach stamped every zone room.
        gate = find_one(sim, "Gatehouse")
        barracks = find_one(sim, "Barracks")
        assert gate.db.get("patrolled") is True
        assert barracks.db.get("patrolled") is True

        # The zone exported to a file.
        area = tmp_path / "areas" / "keep.realm"
        assert area.exists()

        # A fresh import against the same world is a no-op plan.
        out = await do(sim, bilda, "@import keep")
        assert "no changes" in out or "0 to create" in out

        # Edit the FILE (the offline-editing half of the workflow), then
        # the plan shows exactly one change and apply commits it.
        data = json.loads(area.read_text())
        for obj in data["objects"]:
            if obj["name"] == "Gatehouse":
                obj["attrs"]["motto"] = "None shall pass."
        area.write_text(json.dumps(data, indent=2))

        out = await do(sim, bilda, "@import keep")
        assert "update" in out and "Gatehouse" in out and "motto" in out
        assert gate.db.get("motto") is None            # plan changed nothing

        out = await do(sim, bilda, "@import/apply keep")
        assert "1 updated" in out
        assert gate.db.get("motto") == "None shall pass."


# =========================================================================
# 167. Random dungeon generator — docs/showcase/167_random_dungeon.md
# =========================================================================

class TestRandomDungeon:

    async def test_seeded_generation_reachability_and_teardown(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "167_random_dungeon.md")

        out = await do(sim, bilda, "delve 5")
        assert "Delved 5 chambers and" in out and "(seed 7)" in out
        # Dropped at the mouth (first chamber).
        assert bilda.location.name == "Cavern 1"

        # The spine guarantees reachability: walk the whole chain.
        for nxt in ("Cavern 2", "Cavern 3", "Cavern 4", "Cavern 5"):
            await do(sim, bilda, "north")
            assert bilda.location.name == nxt

        rooms = [o for o in sim.store.all_cached()
                 if o.has_tag("dungeon:run") and o.has_tag("room")]
        assert len(rooms) == 5 + 4          # 5 spine + seed-7 alcoves

        # Determinism: same seed rebuilds the same room count.
        await do(sim, bilda, "@teleport me = The Workshop")
        await do(sim, bilda, "collapse")
        assert not [o for o in sim.store.all_cached()
                    if o.has_tag("dungeon:run")]
        await do(sim, bilda, "delve 5")
        again = [o for o in sim.store.all_cached()
                 if o.has_tag("dungeon:run") and o.has_tag("room")]
        assert len(again) == 9

        # The tag makes teardown one line.
        await do(sim, bilda, "@teleport me = The Workshop")
        out = await do(sim, bilda, "collapse")
        assert "collapses into rubble" in out
        assert not [o for o in sim.store.all_cached()
                    if o.has_tag("dungeon:run")]


# =========================================================================
# 168. Room templates — docs/showcase/168_room_templates.md
# =========================================================================

class TestRoomTemplates:

    async def test_stamp_mints_consistent_rooms(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "168_room_templates.md")

        out = await do(sim, bilda, "stamp A1")
        assert "Stamped A1" in out
        await do(sim, bilda, "stamp A2")

        a1 = find_one(sim, "A1")
        a2 = find_one(sim, "A2")
        # Every stamp carries the template's tags and flavor identically.
        for cell in (a1, a2):
            assert cell.has_tag("cellblock") and cell.has_tag("dark")
            assert cell.db.get("desc_extras")[0][1].startswith(
                "A cramped stone cell.")

        # And the minting linked a real, walkable exit.
        out = await do(sim, bilda, "cell A1")
        assert bilda.location is a1


# =========================================================================
# 169. Zone mass-edit — docs/showcase/169_zone_mass_edit.md
# =========================================================================

class TestZoneMassEdit:

    async def test_dry_run_is_default_apply_commits(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "169_zone_mass_edit.md")
        nave = find_one(sim, "Nave")
        crypt = find_one(sim, "Crypt")

        # Bare command is a DRY RUN — it reports, changes nothing.
        out = await do(sim, bilda, "retheme chapel")
        assert "DRY RUN over 2 rooms in chapel" in out
        assert "would set ambient on Nave" in out
        assert nave.db.get("ambient") is None
        assert crypt.db.get("ambient") is None

        # The apply keyword commits to every room in the zone.
        out = await do(sim, bilda, "retheme apply chapel")
        assert "APPLYING to 2 rooms" in out
        assert nave.db.get("ambient") == "Candlewax and cold stone."
        assert crypt.db.get("ambient") == "Candlewax and cold stone."


# =========================================================================
# 170. Builder wizard — docs/showcase/170_builder_wizard.md
# =========================================================================

class TestBuilderWizard:

    async def test_prompt_chain_builds_a_linked_room(self, sim):
        room, bilda = workshop_and_builder(sim)
        # A non-coder drives the admin-owned wizard (delegated authority).
        dana = sim.player("Dana", location=room)
        wire_sessions(sim, bilda, dana)
        await build(sim, bilda, "170_builder_wizard.md")

        out = await do(sim, dana, "build")
        assert "Name the new room:" in out
        sess = sim.session(dana)
        assert sess.input_handler is not None

        await sess.input_handler(sim.session(dana), "Sunny Parlor")
        await sim.session(dana).input_handler(
            sim.session(dana), "Light pours through tall windows.")
        await sim.session(dana).input_handler(sim.session(dana), "north")

        out = "\n".join(sim.seen(dana))
        assert "Done. Sunny Parlor is now north of here." in out
        parlor = find_one(sim, "Sunny Parlor")

        # The exit the wizard minted is real and walkable.
        await do(sim, dana, "north")
        assert dana.location is parlor
        assert parlor.db.get("desc_extras")[0][1] == (
            "Light pours through tall windows.")


# =========================================================================
# 171. Dynamic descriptions — docs/showcase/171_dynamic_descriptions.md
# =========================================================================

class TestDynamicDescriptions:

    async def test_desc_weaves_state_and_ticker_pushes_changes(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "171_dynamic_descriptions.md")
        gallery = find_one(sim, "Lighthouse Gallery")
        keeper = find_one(sim, "lamp keeper")

        # Dark: the state line reads dark, the beam block is empty.
        out = await do(sim, bilda, "look")
        assert "The great lamp is dark." in out
        assert "beam sweeps" not in out

        # Flip the shared state by hand; the desc re-weaves on next look.
        await do(sim, bilda, "@set here/lamp_state = lit")
        out = await do(sim, bilda, "look")
        assert "The great lamp is lit." in out
        assert "A beam sweeps the black water below." in out

        # Push-on-change: the master's tick stamps every zone room and
        # announces only on a real transition. Drive one tick after a
        # hand-reset so the computed state differs.
        await do(sim, bilda, "@set here/lamp_state = dark")
        sim.seen(bilda)
        behavior = next(b for b in keeper.get_behaviors()
                        if b.behavior_id == "script_ticker")
        # now()//30 %2 is deterministic within a test run; pump until the
        # tick reports a transition (at most two 15-tick windows).
        for _ in range(2):
            await behavior.tick(keeper, 4.0)
            if gallery.db.get("lamp_state") != "dark":
                break
        # Whatever the wall clock said, the room's state was pushed to
        # match the master's computed value, not pulled per look.
        assert gallery.db.get("lamp_state") in ("lit", "dark")


# =========================================================================
# 172. World audit report — docs/showcase/172_world_audit.md
# =========================================================================

class TestWorldAudit:

    async def test_reports_orphans_broken_exits_and_bloat(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "172_world_audit.md")

        # Plant one of each fault.
        orphan = sim.obj("stray bolt", location=None, tags=["thing"])
        orphan.owner = bilda
        await do(sim, bilda, "@dig Dead End = de, back")
        broken = find_one(sim, "de")            # the outward exit
        broken.db.set("destination", "no-such-id")
        tome = sim.obj("heavy tome", location=room, tags=["thing"])
        tome.owner = bilda
        tome.db.set("lore", "x" * 1200)

        out = await do(sim, bilda, "audit")
        assert "AUDIT: 1 orphan(s), 1 broken exit(s), 1 oversized attr(s)." in out
        assert "orphan: stray bolt" in out
        assert "broken exit: de" in out
        assert "oversized: heavy tome/lore" in out


# =========================================================================
# 173. CSV world import — docs/showcase/173_csv_import.md
# =========================================================================

class TestCsvImport:

    async def test_validate_apply_and_idempotent_reimport(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "173_csv_import.md")

        # Validate-first: a bare run reports, creates nothing.
        out = await do(sim, bilda, "csv check")
        assert "would import Guardroom (extid r1)" in out
        assert not all_named(sim, "Guardroom")

        out = await do(sim, bilda, "csv apply")
        assert "created Guardroom" in out and "created Armory" in out
        assert len([o for o in sim.store.all_cached()
                    if o.has_tag("extid:r1")]) == 1

        # Idempotent: re-applying updates the same rooms, never duplicates.
        out = await do(sim, bilda, "csv apply")
        assert "updated Guardroom" in out
        assert len([o for o in sim.store.all_cached()
                    if o.has_tag("extid:r1")]) == 1
        assert len(all_named(sim, "Guardroom")) == 1

    async def test_malformed_rows_fail_validation(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "173_csv_import.md")
        await do(sim, bilda, '@set room importer/rows = ["r1,Ok,fine", "junk"]')
        out = await do(sim, bilda, "csv apply")
        assert "VALIDATION FAILED: 1 malformed row(s)" in out
        assert not all_named(sim, "Ok")        # nothing created on a bad batch

    def test_sample_csv_ships(self):
        sample = (Path(__file__).resolve().parents[2] / "docs" / "showcase"
                  / "building_tools_rooms.csv")
        assert sample.exists(), "the tutorial's sample CSV must ship"
        text = sample.read_text(encoding="utf-8")
        assert "extid" in text and "Guardroom" in text


# =========================================================================
# 174. Auto-map generator — docs/showcase/174_auto_map.md
# =========================================================================

class TestAutoMap:

    async def test_bfs_grid_and_unmappable_links(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, "174_auto_map.md")
        # Stand in the hub so (0,0) anchors there.
        await do(sim, bilda, "enter")

        out = await do(sim, bilda, "map keep")
        # Hub, East Wing, Watchtower, North Hall place on the compass grid;
        # the Cellar (reached only by 'down') can't and is left off.
        assert "4/5 rooms placed" in out
        # The grid rows render the placed rooms two-char-abbreviated.
        assert "[Ke]" in out and "[Ea]" in out and "[No]" in out and "[Wa]" in out
        # Non-compass links are reported, not silently dropped.
        assert "Unmappable links:" in out
        assert "down" in out            # Hub/down to the cellar

        # The scratch coords were cleaned up after rendering.
        cart = find_one(sim, "cartographer")
        assert not [k for k in cart.db.all() if k.startswith("coord_")]


# =========================================================================
# 175. Player housing customization — docs/showcase/175_player_housing.md
# =========================================================================

class TestPlayerHousing:

    async def test_delegated_decorating_with_guardrails(self, sim):
        room, bilda = workshop_and_builder(sim)
        cass = sim.player("Cass", location=room)
        await build(sim, bilda, "175_player_housing.md")
        house = find_one(sim, "Rowhouse 12")
        cass.location = house

        out = await do(sim, cass, "claim")
        assert "You take the keys." in out
        assert house.db.get("owner_id") == cass.id

        # The owner sets the room's own description via desc_extras
        # (softcode can't write the render-description slot).
        out = await do(sim, cass, "decorate A brass lamp warms the reading nook.")
        assert "You redecorate." in out
        assert house.db.get("desc_extras")[0][1] == (
            "A brass lamp warms the reading nook.")

        # Whitelisted furniture only, spawned safe (survives @wipe).
        out = await do(sim, cass, "furnish chair")
        assert "sets out a chair" in out
        chair = all_named(sim, "a chair")[0]
        assert chair.location is house and chair.has_tag("furniture")

        out = await do(sim, cass, "furnish jetpack")
        assert "Not an allowed furnishing" in out
        assert not all_named(sim, "a jetpack")

        # Guardrail: length cap.
        out = await do(sim, cass, "decorate " + "x" * 100)
        assert "Too long" in out

        # Guardrail: a stranger cannot touch another player's home.
        out = await do(sim, bilda, "@teleport me = Rowhouse 12")
        out = await do(sim, bilda, "decorate I live here now")
        assert "This is not your home." in out
        assert house.db.get("desc_extras")[0][1] == (
            "A brass lamp warms the reading nook.")
