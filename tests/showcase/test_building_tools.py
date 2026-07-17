"""
Showcase "Building & World Tools" — checklist items 165-175.

Verifies docs/showcase/165_prototype_library.md .. 175_player_housing.md
by driving a real in-process world — the realm.testing.Simulator wires
the same store/propagation/scripting/dispatcher stack a live GameServer
does — with the tutorials' EXACT command lines (raw input in, session
output out).

The build transcripts below are copied verbatim from the docs' "Build
it" sections; the doc-sync test at the bottom keeps them from drifting.

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
from types import SimpleNamespace

import pytest

from realm.testing import Simulator

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


async def build(sim, player, lines):
    """Run a Build-it transcript; fail loudly if any line misfires."""
    for line in lines:
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

PROTOTYPE_BUILD = [
    "@create prototype rack",
    "drop prototype rack",
    '@set prototype rack/proto_sword = {"name": "a sword", "damage": 3, "weight": 2}',
    '@set prototype rack/proto_greatsword = {"parent": "sword", "name": "a greatsword", "damage": 6}',
    "@set prototype rack/cmd_mint = $mint *: key = 'proto_' + trim(arg0); "
    "p = V(key); base = V('proto_' + str(p.get('parent')), {}) "
    "if p and p.get('parent') else {}; spec = {**base, **p} if p else None; "
    "o = create_obj(spec['name'], tags=['thing'], location=enactor) if spec else None; "
    "(set_attr(o, 'damage', spec.get('damage', 1)), set_attr(o, 'weight', "
    "spec.get('weight', 1)), pemit(enactor, 'Minted ' + spec['name'] + ': dmg ' + "
    "str(spec.get('damage')) + ', wt ' + str(spec.get('weight')) + '.')) if o else "
    "pemit(enactor, 'No such prototype.')",
]


class TestPrototypeLibrary:

    async def test_mint_merges_prototype_over_its_parent(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, PROTOTYPE_BUILD)

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
        await build(sim, bilda, PROTOTYPE_BUILD)
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

BATCHCODE_BUILD = [
    "@dig Gatehouse = gate, back",
    "gate",
    "@zone here = keep",
    "@dig Barracks = barracks, out",
    "barracks",
    "@zone here = keep",
    "out",
    "@foreach tag:zone:keep = @set %o/patrolled = true",
    "@export keep",
    "@areas",
    "@import keep",
]


class TestBatchcodeAreas:

    async def test_foreach_bulk_edit_then_export_import_roundtrip(
            self, sim, tmp_path):
        temp_areas(sim, tmp_path)
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, BATCHCODE_BUILD)

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

DUNGEON_BUILD = [
    "@create dungeon forge",
    "drop dungeon forge",
    "@set dungeon forge/seed = 7",
    "@set dungeon forge/cmd_delve = $delve *: n = clamp(int(arg0), 2, 8); "
    "s = V('seed', 1); rooms = [create_obj('Cavern ' + str(i + 1), "
    "tags=['room', 'dungeon:run']) for i in range(n)]; "
    "[set_attr(rooms[i], 'desc_extras', [['', 'Hewn rock, chamber ' + str(i + 1) + "
    "' of ' + str(n) + '.']]) for i in range(n)]; "
    "[(set_attr(create_obj('north', tags=['exit'], location=rooms[i - 1]), "
    "'destination', rooms[i].id), set_attr(create_obj('south', tags=['exit'], "
    "location=rooms[i]), 'destination', rooms[i - 1].id)) for i in range(1, n)]; "
    "seq = []; [seq.append((s * 1103515245 + 12345) % 2147483648) if not seq else "
    "seq.append((seq[-1] * 1103515245 + 12345) % 2147483648) for i in range(n)]; "
    "picks = [i for i in range(n) if seq[i] % 3 == 0]; "
    "alcoves = [create_obj('Alcove ' + str(j + 1), tags=['room', 'dungeon:run']) "
    "for j in range(len(picks))]; "
    "[(set_attr(create_obj('east', tags=['exit'], location=rooms[picks[j]]), "
    "'destination', alcoves[j].id), set_attr(create_obj('west', tags=['exit'], "
    "location=alcoves[j]), 'destination', rooms[picks[j]].id), set_attr(alcoves[j], "
    "'desc_extras', [['', 'A dead-end alcove, thick with dust.']])) "
    "for j in range(len(picks))]; teleport_obj(enactor, rooms[0]); "
    "pemit(enactor, 'Delved ' + str(n) + ' chambers and ' + str(len(picks)) + "
    "' alcoves (seed ' + str(s) + '). You stand at the mouth.')",
    "@set dungeon forge/cmd_collapse = $collapse: [destroy_obj(o) for o in "
    "search_world(tag='dungeon:run')]; pemit(enactor, 'The dungeon collapses "
    "into rubble.')",
]


class TestRandomDungeon:

    async def test_seeded_generation_reachability_and_teardown(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, DUNGEON_BUILD)

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

TEMPLATE_BUILD = [
    "@create cell stamp",
    "drop cell stamp",
    '@set cell stamp/tmpl_tags = ["room", "cellblock", "dark"]',
    "@set cell stamp/tmpl_desc = A cramped stone cell. A slot in the door "
    "passes a tin tray; the air is cold and close.",
    "@set cell stamp/cmd_stamp = $stamp *: nm = escape(trim(arg0)); "
    "r = create_obj(nm, tags=V('tmpl_tags', ['room'])); "
    "set_attr(r, 'desc_extras', [['', V('tmpl_desc', '')]]); "
    "e = create_obj('cell ' + nm, tags=['exit'], location=loc(enactor)); "
    "set_attr(e, 'destination', r.id); pemit(enactor, 'Stamped ' + nm + "
    "', reachable as: cell ' + nm + '.')",
]


class TestRoomTemplates:

    async def test_stamp_mints_consistent_rooms(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, TEMPLATE_BUILD)

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

MASSEDIT_BUILD = [
    "@dig Nave = nave, back",
    "nave",
    "@zone here = chapel",
    "@dig Crypt = crypt, up",
    "crypt",
    "@zone here = chapel",
    "up",
    "@create warden",
    "drop warden",
    "@set warden/cmd_retheme = $retheme *: parts = trim(arg0).split(' '); "
    "apply = parts[0] == 'apply'; zone = parts[-1]; rooms = zone_rooms(zone); "
    "pemit(enactor, ('APPLYING to ' if apply else 'DRY RUN over ') + "
    "str(len(rooms)) + ' rooms in ' + zone + ':'); "
    "[(set_attr(r, 'ambient', 'Candlewax and cold stone.'), pemit(enactor, "
    "'  set ambient on ' + name(r))) if apply else pemit(enactor, "
    "'  would set ambient on ' + name(r)) for r in rooms]",
]


class TestZoneMassEdit:

    async def test_dry_run_is_default_apply_commits(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, MASSEDIT_BUILD)
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

WIZARD_BUILD = [
    "@create build wizard",
    "drop build wizard",
    "@set build wizard/cmd_build = $build: set_attr(me, 'wip_room_' + enactor.id, "
    "''); prompt(enactor, 'Name the new room:', 'on_name')",
    "@set build wizard/on_name = r = create_obj(escape(trim(arg0)), tags=['room']); "
    "set_attr(me, 'wip_room_' + enactor.id, r.id); prompt(enactor, 'Describe it in "
    "a sentence:', 'on_desc')",
    "@set build wizard/on_desc = r = get('#' + str(V('wip_room_' + "
    "enactor.id))); set_attr(r, 'desc_extras', [['', escape(trim(arg0))]]); "
    "prompt(enactor, 'Which direction leads there from here?', 'on_exit')",
    "@set build wizard/on_exit = d = trim(arg0).lower(); r = get('#' + str(V("
    "'wip_room_' + enactor.id))); e = create_obj(d, tags=['exit'], "
    "location=loc(enactor)); set_attr(e, 'destination', r.id); del_attr(me, "
    "'wip_room_' + enactor.id); pemit(enactor, 'Done. ' + name(r) + ' is now ' + d "
    "+ ' of here.')",
]


class TestBuilderWizard:

    async def test_prompt_chain_builds_a_linked_room(self, sim):
        room, bilda = workshop_and_builder(sim)
        # A non-coder drives the admin-owned wizard (delegated authority).
        dana = sim.player("Dana", location=room)
        wire_sessions(sim, bilda, dana)
        await build(sim, bilda, WIZARD_BUILD)

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

DYNDESC_BUILD = [
    "@dig Lighthouse Gallery = up, down",
    "up",
    "@zone here = cape",
    "@set here/lamp_state = dark",
    "@desc here = A spiral stair climbs to the lamp room. [[result = 'The great "
    "lamp is ' + V('lamp_state', 'dark') + '.']] [[result = ansi('yh', "
    "'A beam sweeps the black water below.') if V('lamp_state', 'dark') "
    "== 'lit' else '']]",
    "@create lamp keeper",
    "@zone/master lamp keeper = cape",
    "drop lamp keeper",
    "@set lamp keeper/on_tick = state = 'lit' if (now() // 30) % 2 == 0 else "
    "'dark'; [(set_attr(r, 'lamp_state', state), remit(r, 'The lamp ' + ('flares "
    "to life.' if state == 'lit' else 'gutters out.'))) for r in zone_rooms('cape') "
    "if get_attr(r, 'lamp_state', 'dark') != state]",
    "@behavior lamp keeper = script_ticker, interval:15",
]


class TestDynamicDescriptions:

    async def test_desc_weaves_state_and_ticker_pushes_changes(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, DYNDESC_BUILD)
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

AUDIT_BUILD = [
    "@create auditor",
    "drop auditor",
    "@set auditor/cmd_audit = $audit: world = search_world(limit=500); "
    "orphans = [name(o) for o in world if loc(o) is None and not has_tag(o, 'room') "
    "and not has_tag(o, 'player')]; broken = [name(e) for e in world if has_tag(e, "
    "'exit') and not get('#' + str(get_attr(e, 'destination', '')))]; "
    "fat = [f'{name(o)}/{k}' for o in world for k, v in o.db.all().items() "
    "if len(str(v)) > 1000]; pemit(enactor, f'AUDIT: {len(orphans)} orphan(s), "
    "{len(broken)} broken exit(s), {len(fat)} oversized attr(s).'); "
    "[pemit(enactor, f'  orphan: {o}') for o in orphans]; "
    "[pemit(enactor, f'  broken exit: {e}') for e in broken]; "
    "[pemit(enactor, f'  oversized: {f}') for f in fat]",
]


class TestWorldAudit:

    async def test_reports_orphans_broken_exits_and_bloat(self, sim):
        room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, AUDIT_BUILD)

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

CSV_BUILD = [
    "@create room importer",
    "drop room importer",
    '@set room importer/rows = ["r1,Guardroom,Spears line the wall.", '
    '"r2,Armory,Racks of dented steel."]',
    "@set room importer/cmd_csv = $csv *: mode = trim(arg0); rows = V("
    "'rows', []); parsed = [[c.strip() for c in row.split(',')] for row in rows]; "
    "bad = [p for p in parsed if len(p) != 3]; pemit(enactor, 'VALIDATION FAILED: ' "
    "+ str(len(bad)) + ' malformed row(s); fix them first.') if bad else None; "
    "[(set_attr(hit[0], 'desc_extras', [['', p[2]]]) if hit else set_attr(create_obj("
    "p[1], tags=['room', 'extid:' + p[0]]), 'desc_extras', [['', p[2]]]), "
    "pemit(enactor, '  ' + ('updated ' if hit else 'created ') + p[1])) "
    "for p in parsed if not bad and mode == 'apply' for hit in "
    "[search_world(tag='extid:' + p[0])]]; [pemit(enactor, '  would import ' + p[1] "
    "+ ' (extid ' + p[0] + ')') for p in parsed if not bad and mode != 'apply']",
]


class TestCsvImport:

    async def test_validate_apply_and_idempotent_reimport(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, CSV_BUILD)

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
        await build(sim, bilda, CSV_BUILD)
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

AUTOMAP_BUILD = [
    "@dig Keep Hub = enter, leave",
    "enter",
    "@zone here = keep",
    "@dig East Wing = east, west",
    "east",
    "@zone here = keep",
    "@dig Watchtower = north, south",
    "north",
    "@zone here = keep",
    "south",
    "west",
    "@dig North Hall = north, south",
    "north",
    "@zone here = keep",
    "south",
    "@dig Cellar = down, up",
    "down",
    "@zone here = keep",
    "up",
    "@create cartographer",
    "drop cartographer",
    "@set cartographer/cmd_map = $map *: z = trim(arg0); rooms = zone_rooms(z); "
    "dirs = {'north': [0, 1], 'south': [0, -1], 'east': [1, 0], 'west': [-1, 0]}; "
    "[del_attr(me, 'coord_' + r.id) for r in rooms]; set_attr(me, 'coord_' + here.id, "
    "[0, 0]); [[set_attr(me, 'coord_' + d.id, [V('coord_' + s.id)[0] + "
    "dirs[nm][0], V('coord_' + s.id)[1] + dirs[nm][1]]) for s in rooms "
    "for e in exits(s) for nm in [name(e).lower()] if nm in dirs for d in "
    "[get('#' + str(get_attr(e, 'destination', '')))] if d is not None and "
    "V('coord_' + s.id) is not None and V('coord_' + d.id) "
    "is None] for step in range(len(rooms))]; placed = [r for r in rooms if "
    "V('coord_' + r.id) is not None]; xs = [V('coord_' + r.id)"
    "[0] for r in placed]; ys = [V('coord_' + r.id)[1] for r in placed]; "
    "pemit(enactor, f'Map of {z} ({len(placed)}/{len(rooms)} rooms placed):'); "
    "[pemit(enactor, ''.join(['[' + left(name([r for r in "
    "placed if V('coord_' + r.id) == [x, y]][0]), 2) + ']' if [r for r "
    "in placed if V('coord_' + r.id) == [x, y]] else '    ' for x in "
    "range(min(xs), max(xs) + 1)])) for y in range(max(ys), min(ys) - 1, -1)]; "
    "unmap = [f'{name(s)}/{name(e)}' for s in rooms for e in exits(s) if "
    "name(e).lower() not in dirs]; pemit(enactor, 'Unmappable links: ' + "
    "(', '.join(unmap) if unmap else 'none')); [del_attr(me, 'coord_' + r.id) "
    "for r in rooms]",
]


class TestAutoMap:

    async def test_bfs_grid_and_unmappable_links(self, sim):
        _room, bilda = workshop_and_builder(sim)
        await build(sim, bilda, AUTOMAP_BUILD)
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

HOUSING_BUILD = [
    "@dig Rowhouse 12 = door, street",
    "door",
    '@set here/furniture_ok = ["chair", "table", "rug", "lamp", "bed"]',
    "@set here/decor_max = 80",
    "@set here/cmd_claim = $claim: pemit(enactor, 'This home already has an "
    "owner.') if V('owner_id') else (set_attr(me, 'owner_id', "
    "enactor.id), set_attr(me, 'owner_name', name(enactor)), pemit(enactor, "
    "'You take the keys. Try: decorate <text>, furnish <item>.'))",
    "@set here/cmd_decorate = $decorate *: txt = trim(arg0); mx = V("
    "'decor_max', 80); ok = enactor.id == V('owner_id'); pemit(enactor, "
    "'This is not your home.') if not ok else (pemit(enactor, 'Too long — keep it "
    "under ' + str(mx) + ' characters.') if len(txt) > mx else (set_attr(me, "
    "'desc_extras', [['', escape(txt)]]), pemit(enactor, 'You redecorate.')))",
    "@set here/cmd_furnish = $furnish *: item = trim(arg0).lower(); wl = V("
    "'furniture_ok', []); ok = enactor.id == V('owner_id'); "
    "pemit(enactor, 'This is not your home.') if not ok else (pemit(enactor, "
    "'Not an allowed furnishing. Try: ' + ', '.join(wl)) if item not in wl else "
    "(set_attr(create_obj('a ' + item, tags=['thing', 'furniture'], location=me), "
    "'safe', True), remit(me, V('owner_name', 'Someone') + ' sets out "
    "a ' + item + '.')))",
    "street",
]


class TestPlayerHousing:

    async def test_delegated_decorating_with_guardrails(self, sim):
        room, bilda = workshop_and_builder(sim)
        cass = sim.player("Cass", location=room)
        await build(sim, bilda, HOUSING_BUILD)
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


# =========================================================================
# Docs <-> tests sync — the transcripts above must match the tutorials
# =========================================================================

DOCS = Path(__file__).resolve().parents[2] / "docs" / "showcase"

DOC_TRANSCRIPTS = {
    "165_prototype_library.md": PROTOTYPE_BUILD,
    "166_batchcode_areas.md": BATCHCODE_BUILD,
    "167_random_dungeon.md": DUNGEON_BUILD,
    "168_room_templates.md": TEMPLATE_BUILD,
    "169_zone_mass_edit.md": MASSEDIT_BUILD,
    "170_builder_wizard.md": WIZARD_BUILD,
    "171_dynamic_descriptions.md": DYNDESC_BUILD,
    "172_world_audit.md": AUDIT_BUILD,
    "173_csv_import.md": CSV_BUILD,
    "174_auto_map.md": AUTOMAP_BUILD,
    "175_player_housing.md": HOUSING_BUILD,
}


def test_tutorial_docs_contain_the_exact_tested_command_lines():
    """Every Build-it line exercised above appears verbatim in its doc,
    so the tutorials can never drift from what the tests prove works."""
    for doc_name, lines in DOC_TRANSCRIPTS.items():
        text = (DOCS / doc_name).read_text(encoding="utf-8")
        for line in lines:
            assert line in text, (
                f"{doc_name} is missing a tested tutorial line:\n{line}")
