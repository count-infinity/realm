"""The ROM 2.4 .are -> REALM worldio converter (scripts/rom_import.py).

The fixture below is built from records taken verbatim from the canonical
Midgaard file (ROM 2.4 "new format"), plus a second room so an exit
resolves, canonical RESETS, and a SHOPS line. The test converts it and
imports the result into a live world, asserting the world materializes:
rooms + linked exits, mob/object prototypes, reset-placed instances, an
equipped weapon, and a shopkeeper behavior.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from realm.persistence.worldio import import_objects
from realm.testing import Simulator

_SPEC = importlib.util.spec_from_file_location(
    "rom_import",
    Path(__file__).resolve().parents[1] / "scripts" / "rom_import.py")
rom_import = importlib.util.module_from_spec(_SPEC)
sys.modules["rom_import"] = rom_import      # dataclass resolves via sys.modules
_SPEC.loader.exec_module(rom_import)


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

    def test_act_flags_map_to_wander(self):
        # The rat is ACT_STAY_AREA (G), not SENTINEL: it wanders its zone.
        area = rom_import.convert(REPOP_ARE)
        rat = area.mob_protos[100]
        wander = [b for b in rat["behaviors"] if b["behavior_id"] == "wander"]
        assert len(wander) == 1
        assert wander[0]["params"]["stay_area"] is True
        rooms = [o for o in area.objects if "room" in o["tags"]]
        assert "zone:test" in rooms[0]["tags"]

    def test_sentinel_and_keepers_do_not_wander(self):
        # The wizard is ACT_SENTINEL (B) AND a shopkeeper: it stays put.
        area = _convert(ARE)
        wiz = area.mob_protos[3000]
        assert not any(b["behavior_id"] == "wander" for b in wiz["behaviors"])


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
