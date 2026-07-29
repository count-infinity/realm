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

    def test_gaps_are_reported(self):
        area = _convert(ARE)
        joined = " ".join(area.gaps)
        assert "AC" in joined                        # Diku AC dropped
        assert any("SHOPS" in g for g in area.gaps)


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
