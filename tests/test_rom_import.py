"""The ROM 2.4 .are -> REALM worldio converter (realm/tools/rom_import.py,
``realm import-rom``).

The fixture below is built from records taken verbatim from the canonical
Midgaard file (ROM 2.4 "new format"), plus a second room so an exit
resolves, canonical RESETS, and a SHOPS line. The test converts it and
imports the result into a live world, asserting the world materializes:
rooms + linked exits, mob/object prototypes, reset-placed instances, an
equipped weapon, and a shopkeeper behavior.
"""

from __future__ import annotations

import pytest

from realm.persistence.worldio import import_objects
from realm.testing import Simulator
from realm.tools import rom_import

ARE = """\
#AREA
midgaard.are~
Midgaard~
{ All } Diku    Midgaard~
3000 3399
#MOBILES
#3000
wizard~
the wizard~
A wizard walks around behind the counter.
~
The wizard looks old and senile.
~
human~
ABV D 900 0
23 0 1d1+999 1d1+999 1d8+32 magic
-15 -15 -15 -15
AF ABCD 0 0
stand stand male 15000
0 0 medium 0
#0
#OBJECTS
#3000
barrel beer~
a barrel of beer~
A beer barrel has been left here.~
wood~
drink 0 A
300 300 'beer' 0 0
0 160 75 P
#3010
sword long~
a long sword~
A long sword lies here.~
metal~
weapon 0 AN
sword 1 8 slash 0
5 40 120 P
#0
#ROOMS
#3001
The Temple Of Mota~
The southern end of the temple hall.
~
0 CDS 0
D2
You see the temple square.
~
~
0 -1 3005
S
#3005
The Temple Square~
The temple square lies before you.
~
0 C 1
D0
~
~
0 -1 3001
S
#0
#RESETS
M 0 3000 1 3001 1
E 0 3010 1 16
O 0 3000 1 3005
S
#SHOPS
3000 1 5 9 0 0 120 80 8 18
0
#$
"""


# A minimal area with a single NON-keeper mob, for the --repop spawner path.
REPOP_ARE = """\
#AREA
test.are~
Test~
{ All } Test    Test~
100 199
#MOBILES
#100
rat~
a rat~
A rat scurries here.
~
It is a rat.
~
rodent~
AG D 0 0
2 0 1d1+7 1d1+7 1d4 bite
5 5 5 5
0 0 0 0
stand stand neuter 0
0 0 small 0
#0
#ROOMS
#101
A Cellar~
A dank cellar.
~
0 0 0
S
#0
#RESETS
M 0 100 2 101 2
S
#$
"""


def _convert(text):
    return rom_import.convert(text)


class TestParse:

    def test_counts(self):
        area = _convert(ARE)
        assert area.name == "Midgaard"
        rooms = [o for o in area.objects if "room" in o["tags"]]
        exits = [o for o in area.objects if "exit" in o["tags"]]
        assert len(rooms) == 2
        assert len(exits) == 2                       # one door each way
        assert set(area.mob_protos) == {3000}
        assert set(area.obj_protos) == {3000, 3010}

    def test_a_shop_patches_its_keeper_not_an_object_of_the_same_vnum(self):
        # MUD_PLAN step 17: mob 3000 (the wizard) keeps a shop, and object
        # 3000 is a barrel of beer. Only the mob is a shopkeeper.
        area = _convert(ARE)
        barrels = [o for o in area.objects if o["attrs"].get("prototype_vnum") == 3000
                   and "thing" in o["tags"]]
        assert barrels and all(o["behaviors"] == [] for o in barrels)
        assert "rom_shop_buys" not in area.obj_protos[3000]["attrs"]
        wizard = next(o for o in area.objects if o["attrs"].get("prototype_vnum") == 3000
                      and "npc" in o["tags"])
        assert [b["behavior_id"] for b in wizard["behaviors"]] == ["shopkeeper"]

    def test_reset_comments_never_swallow_a_reset(self):
        # ROM's loader reads a reset's fields, then skips to the end of the
        # line: whatever follows is a comment, and a line starting with `*`
        # is one too. A one- or two-word comment used to eat the next line.
        resets = ("#RESETS\n"
                  "*\n"
                  "* the temple\n"
                  "O 0 3000 1 3005\tbarrel\n"
                  "M 0 3000 1 3001 1\t* wizard\n"
                  "E 0 3010 1 16\tsword\n"
                  "P 0 3010 1 3000 1\t* a sword in the barrel, not the wizard\n"
                  "S\n")
        start = ARE.index("#RESETS")
        text = ARE[:start] + resets + ARE[ARE.index("#SHOPS"):]
        area = _convert(text)
        wizard = [o for o in area.objects if o["attrs"].get("prototype_vnum") == 3000
                  and "npc" in o["tags"]]
        assert len(wizard) == 1 and wizard[0]["location"] == "rom_3001"
        swords = [o for o in area.objects if o["attrs"].get("prototype_vnum") == 3010
                  and "prototype" not in o["tags"]]
        barrel = next(o for o in area.objects if o["attrs"].get("prototype_vnum") == 3000
                      and "thing" in o["tags"] and "prototype" not in o["tags"])
        assert barrel["location"] == "rom_3005"
        assert [o["location"] for o in swords] == [wizard[0]["id"], barrel["id"]]

    def test_the_refresh_script_takes_a_shop_off_an_object(self):
        # The shipped Midgaard was converted before the fix above, and its
        # .are is not at hand: the refresh script mends the converted file.
        import importlib.util
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "refresh_rom_items.py"
        spec = importlib.util.spec_from_file_location("refresh_rom_items", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        shop = [{"behavior_id": "shopkeeper", "params": {"markup": 1.1}},
                {"behavior_id": "restock", "params": {}}]
        data = {"objects": [
            {"id": "o1", "name": "bottle beer", "tags": ["thing", "drink_container"],
             "attrs": {"item_type": "drink", "rom_values": [0, 0, 0, 0, 0],
                       "rom_shop_buys": [], "prototype_vnum": 3001},
             "behaviors": [dict(b) for b in shop]},
            {"id": "m1", "name": "baker", "tags": ["npc"],
             "attrs": {"rom_act": ["B"], "rom_shop_buys": []},
             "behaviors": [dict(b) for b in shop]},
        ]}
        module.refresh(data)
        beer, baker = data["objects"]
        assert beer["behaviors"] == [] and "rom_shop_buys" not in beer["attrs"]
        assert baker["behaviors"] == shop and baker["attrs"]["rom_shop_buys"] == []

    def test_the_refresh_script_gives_a_spawner_its_vnum(self):
        import importlib.util
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "refresh_rom_items.py"
        spec = importlib.util.spec_from_file_location("refresh_rom_items", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        prototype = {"name": "fido dog", "tags": ["npc"], "attrs": {"rom_vnum": 3062}}
        data = {"objects": [
            {"id": "r1", "name": "Square", "tags": ["room"], "attrs": {"sector": "city"},
             "behaviors": [{"behavior_id": "spawner",
                            "params": {"key": "m3062", "prototype": prototype}}]},
        ]}
        module.refresh(data)
        spawned = data["objects"][0]["behaviors"][0]["params"]["prototype"]
        assert spawned["attrs"]["prototype_vnum"] == 3062

    def test_the_refresh_script_stops_act_scavengers_eating_corpses(self):
        import importlib.util
        from pathlib import Path
        script = Path(__file__).resolve().parents[1] / "scripts" / "dev" / "refresh_rom_items.py"
        spec = importlib.util.spec_from_file_location("refresh_rom_items", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        guard = {"name": "cityguard", "tags": ["npc", "rom_spec:spec_guard"],
                 "attrs": {"rom_act": ["A", "C", "G"], "rom_vnum": 3060},
                 "behaviors": [{"behavior_id": "scavenger", "params": {}}]}
        fido = {"name": "fido", "tags": ["npc", "rom_spec:spec_fido"],
                "attrs": {"rom_act": ["A", "F"], "rom_vnum": 3062},
                "behaviors": [{"behavior_id": "scavenger",
                               "params": {"eat_corpses": True, "pick_up": False}}]}
        room = {"id": "r1", "name": "Square", "tags": ["room"], "attrs": {"sector": "city"},
                "behaviors": [{"behavior_id": "spawner",
                               "params": {"key": "m3060", "prototype": dict(guard)}}]}
        data = {"objects": [dict(guard, id="m1"), dict(fido, id="m2"), room]}
        module.refresh(data)
        picks = {"eat_corpses": False, "pick_up": True}
        assert data["objects"][0]["behaviors"][0]["params"] == picks
        assert data["objects"][1]["behaviors"][0]["params"]["eat_corpses"] is True
        spawned = data["objects"][2]["behaviors"][0]["params"]["prototype"]
        assert spawned["behaviors"][0]["params"] == picks

    def test_letter_flags_and_dice(self):
        # ABV -> bits 0,1,21 ; 1d1+999 averages to 1000
        assert rom_import.rom_flags("ABV") == (1 | 2 | (1 << 21))
        assert rom_import.rom_flags("0") == 0
        assert rom_import.rom_flags("300") == 300
        assert rom_import.dice_avg("1d1+999") == 1000
        assert rom_import.dice_avg("2d6") == 7

    def test_new_format_item_type_is_a_word(self):
        area = _convert(ARE)
        assert area.obj_protos[3000]["attrs"]["item_type"] == "drink"
        assert area.obj_protos[3010]["attrs"]["item_type"] == "weapon"
        assert "wieldable" in area.obj_protos[3010]["tags"]
        assert area.obj_protos[3010]["attrs"]["damage"] == "1d8"

    def test_merc_combat_stats_are_emitted(self):
        # The mob's descending AC, level-derived THAC0, and natural-attack
        # dice come through as MERC-native attrs, so an imported area is
        # combat-ready on the merc ruleset with no hand-work.
        area = _convert(ARE)
        wiz = area.mob_protos[3000]["attrs"]
        assert wiz["armor_class"] == -15            # ROM ac[pierce]
        assert wiz["thac0"] == 0                    # 20 - level 23, clamped
        assert wiz["damage_dice"] == "1d8+32"
        sword = area.obj_protos[3010]["attrs"]
        assert sword["damage_dice"] == "1d8"        # what MercRuleset reads

    def test_gaps_are_reported(self):
        area = _convert(ARE)
        assert any("SHOPS" in g for g in area.gaps)
        # Resistance is no longer a gap -- it is normalized (below).
        assert not any("resistance" in g.lower() for g in area.gaps)

    def test_resistances_are_normalized(self):
        # The wizard's imm=ABCD -> C(magic)/D(weapon) map to damage types;
        # A(summon)/B(charm) are affect immunities and are dropped. MERC reads
        # the multiplier map directly (immune -> 0.0).
        area = _convert(ARE)
        wiz = area.mob_protos[3000]["attrs"]
        assert wiz["resistances"] == {"magical": 0.0, "physical": 0.0}
        assert wiz["rom_imm"] == ["A", "B", "C", "D"]      # raw letters kept

    def test_repop_keeper_stays_a_static_fixture(self):
        # The wizard (vnum 3000) is a shopkeeper (#SHOPS), so under --repop it
        # is placed statically WITH its stock and gets NO spawner (respawning
        # a keeper empty would break its shop).
        area = rom_import.convert(ARE, repop=True)
        placed = [o for o in area.objects
                  if o["attrs"].get("prototype_vnum") == 3000
                  and "npc" in o["tags"]]
        assert len(placed) == 1                            # still placed
        temple = [o for o in area.objects if "room" in o["tags"]
                  and o["attrs"].get("rom_vnum") == 3001][0]
        assert not any(b["behavior_id"] == "spawner"
                       for b in temple["behaviors"])       # no respawn

    def test_repop_adopts_and_respawns_a_nonkeeper(self):
        # A non-keeper mob: placed statically AND adopted by a spawner (tagged,
        # tracking seeded) so it respawns on death without duplicating.
        area = rom_import.convert(REPOP_ARE, repop=True)
        cellar = [o for o in area.objects if "room" in o["tags"]
                  and o["attrs"].get("rom_vnum") == 101][0]
        spawners = [b for b in cellar["behaviors"]
                    if b["behavior_id"] == "spawner"]
        assert len(spawners) == 1
        sp = spawners[0]["params"]
        assert sp["prototype"]["name"] == "rat" and sp["count"] == 1
        rat = [o for o in area.objects
               if o["attrs"].get("prototype_vnum") == 100 and "npc" in o["tags"]]
        assert len(rat) == 1                               # static instance
        assert "spawned:m100" in rat[0]["tags"]            # adopted, not dup'd
        assert cellar["attrs"]["spawner_m100_ids"] == [rat[0]["id"]]
        assert cellar["attrs"]["spawner_m100_seeded"] is True

    def test_a_respawn_is_the_same_mob_by_vnum(self):
        # MUD_PLAN step 17: a quest that counts fidos matches them by
        # prototype_vnum; the fido a spawner brings back must carry it too,
        # and so must a zone reset's.
        area = rom_import.convert(REPOP_ARE, repop=True)
        cellar = next(o for o in area.objects if o["attrs"].get("rom_vnum") == 101
                      and "room" in o["tags"])
        spawner = next(b for b in cellar["behaviors"] if b["behavior_id"] == "spawner")
        assert spawner["params"]["prototype"]["attrs"]["prototype_vnum"] == 100
        area = rom_import.convert(REPOP_ARE, zone_reset=True)
        master = next(o for o in area.objects if "zone_master" in o["tags"])
        spec = master["attrs"]["reset_spec"]
        assert [e["prototype"]["attrs"]["prototype_vnum"] for e in spec] == [100]

    def test_a_scavenger_picks_things_up_and_eats_no_corpse(self):
        # MUD_PLAN step 17: ROM's ACT_SCAVENGER (C) picks up the best thing
        # in the room; it was mapped to a scavenger that devours corpses, so
        # Midgaard's cityguards ate the fidos players had just killed.
        area = rom_import.convert(REPOP_ARE.replace("AG D 0 0", "ACG D 0 0"))
        rat = area.mob_protos[100]
        scavenger = [b for b in rat["behaviors"] if b["behavior_id"] == "scavenger"]
        assert scavenger == [{"behavior_id": "scavenger",
                              "params": {"eat_corpses": False, "pick_up": True}}]

    def test_act_flags_map_to_shipped_behaviors(self):
        # The rat is ACT_STAY_AREA (G), not SENTINEL: it gets the shipped
        # `wandering` behavior, zone-bounded.
        area = rom_import.convert(REPOP_ARE)
        rat = area.mob_protos[100]
        wander = [b for b in rat["behaviors"]
                  if b["behavior_id"] == "wandering"]
        assert len(wander) == 1
        assert wander[0]["params"]["stay_in_zone"] is True
        rooms = [o for o in area.objects if "room" in o["tags"]]
        assert "zone:test" in rooms[0]["tags"]

    def test_zone_reset_emits_a_master_with_spec(self):
        # --zone-reset: one zone master with a zone_reset behavior + a
        # reset_spec, statics adopted, and NO per-room spawners (a different
        # strategy from --repop).
        area = rom_import.convert(ARE, zone_reset=True)
        masters = [o for o in area.objects if "zone_master" in o["tags"]]
        assert len(masters) == 1
        master = masters[0]
        assert any(b["behavior_id"] == "zone_reset"
                   for b in master["behaviors"])
        assert "zone:midgaard" in master["tags"]
        spec = master["attrs"]["reset_spec"]
        wiz = [e for e in spec if e["prototype"]["name"] == "wizard"]
        assert wiz and wiz[0]["room"] == "rom_3001"    # mob 3000 in room 3001
        assert any("reset:rom_reset_master" in o["tags"]
                   for o in area.objects if "npc" in o["tags"])
        assert not any(b["behavior_id"] == "spawner"
                       for o in area.objects if "room" in o["tags"]
                       for b in o["behaviors"])

    def test_sentinel_and_keepers_do_not_wander(self):
        # The wizard is ACT_SENTINEL (B) AND a shopkeeper: it stays put.
        area = _convert(ARE)
        wiz = area.mob_protos[3000]
        assert not any(b["behavior_id"] == "wandering"
                       for b in wiz["behaviors"])


@pytest.mark.asyncio
class TestImportIntoWorld:

    async def _world(self):
        area = _convert(ARE)
        sim = Simulator()
        created = await import_objects(
            {"realm_format": 1, "objects": area.objects},
            sim.store, preserve_ids=True)
        return sim, created

    def _one(self, created, name, *, proto=False):
        return [o for o in created if o.name == name
                and o.has_tag("prototype") == proto][0]

    async def test_rooms_and_exits_link(self):
        sim, created = await self._world()
        try:
            temple = self._one(created, "The Temple Of Mota")
            assert "sector:inside" in temple.tags
            for ex in [o for o in created if o.has_tag("exit")]:
                dest = sim.store.get_cached(ex.db.get("destination"))
                assert dest is not None
            south = [o for o in created if o.name == "south"][0]
            assert sim.store.get_cached(south.db.get("destination")).name \
                == "The Temple Square"
        finally:
            sim.close()

    async def test_reset_places_mob_with_stats(self):
        sim, created = await self._world()
        try:
            wiz = self._one(created, "wizard")
            assert wiz.location.name == "The Temple Of Mota"
            assert wiz.db.get("hp") == 1000
            assert wiz.db.get("level") == 23
        finally:
            sim.close()

    async def test_equipped_weapon_goes_to_the_mob(self):
        sim, created = await self._world()
        try:
            wiz = self._one(created, "wizard")
            sword = self._one(created, "sword long")
            assert sword.location is wiz
            assert sword.db.get("worn") == "wield"
        finally:
            sim.close()

    async def test_object_reset_places_in_room(self):
        sim, created = await self._world()
        try:
            barrel = self._one(created, "barrel beer")
            assert barrel.location.name == "The Temple Square"
        finally:
            sim.close()

    async def test_shopkeeper_behavior_on_the_instance(self):
        sim, created = await self._world()
        try:
            wiz = self._one(created, "wizard")
            behaviors = wiz.get_behaviors()
            assert [b.behavior_id for b in behaviors] == ["shopkeeper"]
            assert behaviors[0].params["markup"] == 1.2
            assert behaviors[0].params["buyback"] == 0.8
        finally:
            sim.close()


# --- realm import-rom ----------------------------------------------------------


def _import_rom(*files: str, out=None, report=None) -> int:
    import argparse

    from realm.cli import cmd_import_rom
    return cmd_import_rom(argparse.Namespace(
        files=list(files), out=out, repop=False, zone_reset=False, report=report))


class TestTheCommand:

    def test_one_area_to_a_file(self, tmp_path, capsys):
        import json
        are = tmp_path / "midgaard.are"
        are.write_text(ARE)
        out = tmp_path / "midgaard.json"
        assert _import_rom(str(are), out=str(out), report="") == 0   # bare --report
        doc = json.loads(out.read_text())
        assert doc["realm_format"] == 1 and doc["objects"]
        err = capsys.readouterr().err
        assert "rooms" in err and "capability gaps" in err

    def test_a_directory_with_a_parity_report(self, tmp_path):
        areas = tmp_path / "areas"
        (areas / "east").mkdir(parents=True)
        (areas / "midgaard.are").write_text(ARE)
        (areas / "east" / "repop.are.txt").write_text(REPOP_ARE)
        out, report = tmp_path / "converted", tmp_path / "parity.md"
        assert _import_rom(str(areas), out=str(out), report=str(report)) == 0
        assert (out / "midgaard.json").is_file()
        assert (out / "east" / "repop.json").is_file()
        assert "Converted **2/2** area files" in report.read_text()

    def test_a_missing_file_is_an_error(self, tmp_path, capsys):
        assert _import_rom(str(tmp_path / "nope.are")) == 1
        assert "no such file" in capsys.readouterr().err


# --- MUD_PLAN step 3: wear slots and consumables ------------------------------------

ITEMS_ARE = """\
#AREA
items.are~
Items~
{ All } Test    Items~
200 299
#OBJECTS
#201
ring gold~
a gold ring~
A gold ring lies here.~
gold~
jewelry 0 AB
0 0 0 0 0
1 1 100 P
#202
lantern~
a lantern~
A lantern lies here.~
brass~
light 0 A
0 0 500 0 0
1 5 20 P
#203
orb~
a glass orb~
An orb lies here.~
glass~
treasure 0 AO
0 0 0 0 0
1 1 10 P
#204
potion red~
a red potion~
A red potion lies here.~
glass~
potion 0 AO
12 'cure light' '' '' ''
1 1 100 P
#205
potion yellow~
a yellow potion~
A yellow potion lies here.~
glass~
potion 0 AO
12 16 -1 -1 -1
1 1 100 P
#206
wand oak~
an oak wand~
An oak wand lies here.~
wood~
wand 0 AO
4 10 7 'magic missile' 0
1 1 100 P
#207
stew bowl~
a bowl of stew~
A bowl of stew sits here.~
food~
food 0 A
25 25 0 0 0
1 1 10 P
#208
cup tea~
a cup of tea~
A cup of tea sits here.~
china~
drink 0 A
6 6 'tea' 0 0
1 1 10 P
#209
fountain~
a fountain~
A fountain gurgles here.~
stone~
fountain 0 0
0 0 'water' 0 0
1 1000 0 P
#210
scroll strange~
a strange scroll~
A strange scroll lies here.~
paper~
scroll 0 AO
12 'polymorph other' '' '' ''
1 1 100 P
#0
#$
"""


class TestSlotsAndConsumables:

    @pytest.fixture
    def protos(self):
        area = _convert(ITEMS_ARE)
        return area, {vnum: rec["attrs"] for vnum, rec in area.obj_protos.items()}

    def test_wear_flags_become_merc_slots(self, protos):
        _area, attrs = protos
        assert attrs[201]["slot"] == "finger"
        assert attrs[202]["slot"] == "light"
        assert attrs[203]["slot"] == "held"

    def test_potions_name_their_spells_by_name_or_slot(self, protos):
        _area, attrs = protos
        assert attrs[204]["spells"] == ["cure light"]
        assert attrs[204]["spell_level"] == 12
        assert attrs[205]["spells"] == ["cure light"]       # ROM slot 16

    def test_a_wand_carries_its_charges(self, protos):
        _area, attrs = protos
        assert attrs[206]["spells"] == ["magic missile"]
        assert (attrs[206]["spell_level"], attrs[206]["charges"]) == (4, 7)

    def test_food_drink_and_fountains(self, protos):
        # MUD_PLAN 12.4, at CoffeeMud's importer's scale: hours x 20, units x 30.
        area, attrs = protos
        assert attrs[207]["nourishment"] == 500
        assert (attrs[208]["liquid"], attrs[208]["liquid_held"],
                attrs[208]["liquid_remaining"]) == ("tea", 180, 180)
        assert {"drink", "fountain"} <= set(area.obj_protos[209]["tags"])
        assert attrs[209]["liquid"] == "water"
        assert "liquid_remaining" not in attrs[209]          # a fountain never empties
        for vnum in (207, 208, 209):
            assert "restores" not in attrs[vnum] and "charges" not in attrs[vnum]

    def test_an_old_format_liquid_is_named_from_roms_table(self):
        area = rom_import.Area()
        assert rom_import.liquid_name(12, area) == "coffee"
        assert rom_import.liquid_name("Dark Ale", area) == "dark ale"
        assert rom_import.liquid_name(99, area) == "water"
        assert any("unknown ROM liquid" in gap for gap in rom_import.gap_lines(area))

    def test_a_weapon_deals_its_attack_words_damage_type(self):
        area = _convert(ARE)
        assert area.obj_protos[3010]["attrs"]["damage_type"] == "slashing"
        # Old-format files read the word as flag letters; it is recognised.
        assert rom_import.attack_damage_type(rom_import.rom_flags("stab")) == "piercing"
        assert rom_import.attack_damage_type("pierce") == "piercing"
        assert rom_import.attack_damage_type("hug") is None

    def test_city_streets_are_lamplit(self):
        assert rom_import.room_light_tags("city") == ["lamplit"]
        assert rom_import.room_light_tags("forest") == []
        area = _convert(ARE)
        square = next(o for o in area.objects if o.get("name") == "The Temple Square")
        assert "outdoor" in square["tags"]

    def test_guildmasters_become_trainers(self):
        assert rom_import.trainer_behavior(["A", "B", "J", "K", "T"]) == {
            "behavior_id": "trainer", "params": {"teaches": "class", "trains_stats": True}}
        assert rom_import.trainer_behavior(["A", "J"])["params"] == {
            "teaches": [], "trains_stats": True}
        assert rom_import.trainer_behavior(["A", "B"]) is None

    def test_a_spell_no_pack_defines_is_a_gap(self, protos):
        area, attrs = protos
        assert attrs[210]["spells"] == ["polymorph other"]
        assert any("polymorph other" in gap for gap in area.gaps)
