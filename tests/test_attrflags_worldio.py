"""
Attribute flags (secret/visual/safe/no_clone) and world import/export.
"""

from __future__ import annotations

import pytest

from realm.core.attrflags import (
    cloneable_attrs,
    readable_attr,
    set_attr_flags,
    visual_attrs,
    writable_attr,
)
from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.persistence.worldio import export_objects, export_zone, import_objects
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    reset_engine()


class TestAttrFlags:

    def test_secret_hides_from_strangers(self):
        from realm.scripting.functions import ScriptFunctions

        gm_room = GameObject("Vault", tags=["room"])
        gm_room.db.gm_notes = "the butler did it"
        set_attr_flags(gm_room, "gm_notes", ["secret"])

        # Players (and player-owned objects) are the threat model: denied.
        alice = GameObject("Alice", tags=["player"])
        funcs = ScriptFunctions(executor=alice)
        assert funcs.get_attr(gm_room, "gm_notes") is None
        assert funcs.has_attr(gm_room, "gm_notes") is False
        gadget = GameObject("gadget", owner=alice)
        funcs2 = ScriptFunctions(executor=gadget)
        assert funcs2.get_attr(gm_room, "gm_notes") is None

        # World-trusts-world: an unowned world NPC's staff-authored script
        # still reads it (coherent — staff wrote both sides).
        imp = GameObject("imp")
        assert readable_attr(gm_room, "gm_notes", imp) is True
        assert readable_attr(gm_room, "gm_notes", gm_room) is True  # self

    def test_search_world_respects_secret(self):
        from realm.persistence.manager import set_active_manager
        from realm.scripting.functions import ScriptFunctions

        pers = MockPersistence()
        vault = GameObject("Vault", tags=["room"])
        vault.db.code = 1234
        set_attr_flags(vault, "code", ["secret"])
        pers.add(vault)
        set_active_manager(pers)
        try:
            alice = GameObject("Alice", tags=["player"])
            funcs = ScriptFunctions(executor=alice, persistence=pers)
            assert funcs.search_world(attr="code") == []
        finally:
            set_active_manager(None)

    def test_safe_refuses_writes(self):
        obj = GameObject("shrine")
        obj.db.on_pray = "say Blessings."
        set_attr_flags(obj, "on_pray", ["safe"])

        ok, reason = writable_attr(obj, "on_pray")
        assert ok is False and "safe" in reason

        from realm.scripting.functions import ScriptFunctions
        funcs = ScriptFunctions(executor=obj)  # self-control, still safe
        assert funcs.set_attr(obj, "on_pray", "hacked") is False
        assert obj.db.get("on_pray") == "say Blessings."

    def test_visual_listed(self):
        obj = GameObject("statue")
        obj.db.inscription = "To the fallen."
        set_attr_flags(obj, "inscription", ["visual"])
        assert visual_attrs(obj) == ["inscription"]

    def test_no_clone_filtered(self):
        attrs = {"hp": 5, "quest_token": "unique-123"}
        flags = {"quest_token": ["no_clone"]}
        assert cloneable_attrs(attrs, flags) == {"hp": 5}


@pytest.mark.asyncio
class TestAttrCommand:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_flag_set_remove_list(self):
        from realm.commands.olc.modify import cmd_attr

        room = GameObject("Vault", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        room.db.gm_notes = "secret plans"

        ctx = make_context(bea, left_args="here/gm_notes",
                           right_args="secret, safe")
        await cmd_attr(ctx)
        assert set(room.db.get("attr_flags")["gm_notes"]) == {"secret", "safe"}

        ctx = make_context(bea, left_args="here/gm_notes", right_args="!safe")
        await cmd_attr(ctx)
        assert room.db.get("attr_flags")["gm_notes"] == ["secret"]

        ctx = make_context(bea, left_args="here")
        await cmd_attr(ctx)
        assert any("gm_notes: secret" in m for m in ctx.session.messages)

    async def test_wipe_spares_safe(self):
        from realm.commands.olc.modify import cmd_wipe

        room = GameObject("Vault", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        room.db.on_pray = "say Blessings."
        room.db.junk = 1
        set_attr_flags(room, "on_pray", ["safe"])

        ctx = make_context(bea, args="here")
        await cmd_wipe(ctx)
        assert room.db.get("on_pray") == "say Blessings."
        assert room.db.get("junk") is None


@pytest.mark.asyncio
class TestWorldIO:

    async def test_round_trip_remaps_references(self):
        pers = MockPersistence()
        keep = GameObject("Keep", tags=["room", "zone:castle"])
        gate = GameObject("gate", tags=["exit"], location=keep)
        yard = GameObject("Yard", tags=["room", "zone:castle"])
        gate.db.destination = yard.id          # id-bearing attribute
        guard = GameObject("guard", tags=["npc"], location=keep)
        guard.db.cmd_halt = "$halt:say None shall pass."
        master = GameObject("Castle Zone", tags=["zone_master", "zone:castle"])
        master.db.xp_multiplier = 1.2

        data = export_objects([keep, gate, yard, guard, master])
        assert data["realm_format"] == 1

        created = await import_objects(data, pers)
        by_name = {o.name: o for o in created}
        new_keep, new_gate, new_yard = (by_name["Keep"], by_name["gate"],
                                        by_name["Yard"])
        assert new_keep.id != keep.id                     # fresh ids
        assert new_gate.location is new_keep              # refs remapped
        assert new_gate.db.get("destination") == new_yard.id  # attr id remapped
        assert by_name["guard"].db.get("cmd_halt").startswith("$halt")
        assert by_name["Castle Zone"].db.get("xp_multiplier") == 1.2
        assert all(o in pers.saved for o in created)

    async def test_password_always_stripped(self):
        pers = MockPersistence()
        alice = GameObject("Alice", tags=["player"])
        alice.db.password = "scrypt$x$y"
        alice.db.hp = 10

        data = export_objects([alice])
        assert "password" not in data["objects"][0]["attrs"]
        created = await import_objects(data, pers)
        assert created[0].db.get("password") is None
        assert created[0].db.get("hp") == 10

    async def test_export_zone_scopes(self):
        from realm.persistence.manager import set_active_manager

        pers = MockPersistence()
        keep = GameObject("Keep", tags=["room", "zone:castle"])
        rock = GameObject("rock", tags=["thing"], location=keep)
        outsider = GameObject("Elsewhere", tags=["room"])
        master = GameObject("Castle Zone", tags=["zone_master", "zone:castle"])
        for o in (keep, rock, outsider, master):
            pers.add(o)
        set_active_manager(pers)
        try:
            data = export_zone("castle")
        finally:
            set_active_manager(None)
        names = {e["name"] for e in data["objects"]}
        assert names == {"Keep", "rock", "Castle Zone"}

    async def test_external_refs_resolve_or_drop(self):
        pers = MockPersistence()
        hub = GameObject("Hub", tags=["room"])
        pers.add(hub)

        area_room = GameObject("Annex", tags=["room"], location=hub)
        data = export_objects([area_room])
        created = await import_objects(data, pers)
        assert created[0].location is hub  # external ref resolved live

        pers2 = MockPersistence()
        created2 = await import_objects(data, pers2)
        assert created2[0].location is None  # missing ref drops cleanly

    async def test_newer_format_refused(self):
        with pytest.raises(ValueError):
            await import_objects({"realm_format": 99, "objects": []}, None)
