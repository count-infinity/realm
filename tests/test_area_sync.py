"""
Area sync: stable-id upsert with a Terraform-style plan. The two tests
that matter — re-import is idempotent (no duplicate area), and path
escape is rejected — plus plan mechanics (create/update/orphan/conflict)
and the control gate.
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.persistence.manager import set_active_manager
from realm.persistence.worldio import (
    apply_plan,
    diff_plan,
    export_zone,
)
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    set_active_manager(None)
    reset_engine()


def build_castle(pers):
    keep = GameObject("Keep", tags=["room", "zone:castle"])
    gate = GameObject("gate", tags=["exit"], location=keep)
    yard = GameObject("Yard", tags=["room", "zone:castle"])
    gate.db.destination = yard.id
    rat = GameObject("rat", tags=["npc"], location=keep)
    rat.db.hp = 3
    master = GameObject("Castle Zone", tags=["zone_master", "zone:castle"])
    master.db.xp_multiplier = 1.2
    for o in (keep, gate, yard, rat, master):
        pers.add(o)
    return keep, gate, yard, rat, master


class TestExportSync:

    def test_reimport_is_idempotent(self):
        """The core promise: export → import twice = ONE castle, not two."""
        import asyncio

        source = MockPersistence()
        set_active_manager(source)
        build_castle(source)
        data = export_zone("castle")

        # Diff against the SAME world: everything already matches.
        assert diff_plan(data, "castle", source).is_empty()

        # Import into a FRESH world: all creates, applied once.
        target = MockPersistence()
        set_active_manager(target)
        plan = diff_plan(data, "castle", target)
        assert len(plan.create) == 5

        async def apply():
            await apply_plan(data, plan, target)
        asyncio.run(apply())
        assert len(target.all_cached()) == 5

        # Re-import the SAME file: no duplicates, nothing to create.
        assert diff_plan(data, "castle", target).is_empty()
        assert len(target.all_cached()) == 5  # still ONE castle


@pytest.mark.asyncio
class TestPlanMechanics:

    async def test_update_shows_field_changes(self):
        pers = MockPersistence()
        set_active_manager(pers)
        keep, _g, _y, rat, _m = build_castle(pers)
        data = export_zone("castle")

        # Edit the live world; the file is now the "desired" older state.
        keep.name = "The Keep (renovated)"
        rat.db.hp = 99

        plan = diff_plan(data, "castle", pers)
        names = {e['name'] for e, _c in plan.update}
        # Both changed objects appear in the update set.
        assert "Keep" in names and "rat" in names
        keep_changes = next(c for e, c in plan.update if e['name'] == "Keep")
        assert any("name" in ch for ch in keep_changes)

    async def test_apply_updates_in_place_preserving_id(self):
        pers = MockPersistence()
        set_active_manager(pers)
        keep, _g, _y, rat, _m = build_castle(pers)
        original_id = keep.id
        data = export_zone("castle")
        keep.name = "wrongname"

        plan = diff_plan(data, "castle", pers)
        await apply_plan(data, plan, pers)
        assert keep.name == "Keep"        # synced back to the file
        assert keep.id == original_id     # same object, not a fresh copy

    async def test_orphan_reported_not_deleted(self):
        pers = MockPersistence()
        set_active_manager(pers)
        keep, _g, _y, _r, _m = build_castle(pers)
        data = export_zone("castle")
        # A new NPC appears in a castle room AFTER export.
        intruder = GameObject("goblin", tags=["npc"], location=keep)
        pers.add(intruder)

        plan = diff_plan(data, "castle", pers)
        assert intruder in plan.orphan
        await apply_plan(data, plan, pers)
        assert intruder in pers.all_cached()  # NOT destroyed

    async def test_carried_item_moves_back_visible_in_plan(self):
        """The documented hazard: upsert returns a looted item to its
        file location — and the plan shows it first."""
        pers = MockPersistence()
        set_active_manager(pers)
        keep, _g, _y, _r, _m = build_castle(pers)
        sword = GameObject("iron sword", tags=["thing"], location=keep)
        pers.add(sword)
        data = export_zone("castle")

        alice = GameObject("Alice", tags=["player"])
        sword.location = alice   # looted, carried out

        plan = diff_plan(data, "castle", pers)
        # sword is a member (was in Keep at export) — wait, it's now on
        # Alice, so it's matched by id from the file, shown as an update.
        assert any(e['name'] == "iron sword" for e, _c in plan.update)
        await apply_plan(data, plan, pers)
        assert sword.location is keep  # synced back


@pytest.mark.asyncio
class TestControlGate:

    async def test_uncontrolled_object_is_conflict(self):
        pers = MockPersistence()
        set_active_manager(pers)
        keep, _g, _y, _r, _m = build_castle(pers)
        keep.owner = GameObject("Someone", tags=["player"])  # not the actor
        data = export_zone("castle")
        keep.name = "changed"

        bob = GameObject("Bob", tags=["player", "builder"])
        plan = diff_plan(data, "castle", pers, actor=bob)
        assert any("Keep" in name for name, _r in plan.conflict)

        with pytest.raises(ValueError):
            await apply_plan(data, plan, pers)


@pytest.mark.asyncio
class TestAreaCommands:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)
        set_active_manager(self.persistence)

    def teardown_method(self):
        set_active_manager(None)

    async def test_export_then_plan_roundtrip(self, tmp_path):
        from realm.commands.olc.area import cmd_export, cmd_import

        # Point the sandbox at a temp dir via the manager's db_path.
        self.persistence.db_path = tmp_path / "game.db"
        keep = GameObject("Keep", tags=["room", "zone:keep"])
        GameObject("torch", tags=["thing"], location=keep)
        bea = GameObject("Bea", tags=["player", "builder"], location=keep)
        for o in (keep,):
            self.persistence.add(o)
        self.persistence.add(keep)

        ctx = make_context(bea, args="keep")
        await cmd_export(ctx)
        assert (tmp_path / "areas" / "keep.realm").exists()
        assert any("Exported" in m for m in ctx.session.messages)

        ctx2 = make_context(bea, args="keep")
        await cmd_import(ctx2)  # plan against same world = no changes
        assert any("matches the file" in m or "no changes" in m.lower()
                   for m in ctx2.session.messages)

    async def test_path_escape_rejected(self, tmp_path):
        from realm.commands.olc.area import _area_path, cmd_import

        self.persistence.db_path = tmp_path / "game.db"
        assert _area_path("../../etc/passwd") is None
        assert _area_path("a/b") is None
        assert _area_path("good_name-1") is not None

        bea = GameObject("Bea", tags=["player", "builder"])
        ctx = make_context(bea, args="../../etc/passwd")
        await cmd_import(ctx)
        assert any("No area file" in m for m in ctx.session.messages)
