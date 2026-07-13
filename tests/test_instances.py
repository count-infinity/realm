"""
Ephemeral instanced areas — a private, transient copy of a template area,
materialized on demand, reaped when idle. See docs/design/ephemeral-rooms.md.

Instances and wilderness collapse into one primitive: materialize a real
room copy on demand (``import_objects``), tag it ``ephemeral`` so it never
persists, drop the owner in, and reap it once it's sat empty. These tests
drive the Python API (``realm.core.instances``), the softcode surface
(``enter_instance``), and the persistence exclusion end-to-end.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core import instances
from realm.testing import Simulator


@pytest.fixture
def world():
    """A ``crypt`` template zone (opt-in), plus a hub the players start in."""
    sim = Simulator()
    hub = sim.room("Hub")
    entry = sim.room("Crypt Entrance")
    entry.add_tag("zone:crypt")
    entry.add_tag("instance_template")     # opt-in mark
    entry.add_tag("instance_entry")        # where arrivals land
    depths = sim.room("Crypt Depths")
    depths.add_tag("zone:crypt")
    torch = sim.obj("a torch", location=entry)
    alice = sim.player("Alice", location=hub)
    bob = sim.player("Bob", location=hub)
    try:
        yield SimpleNamespace(sim=sim, store=sim.store, hub=hub, entry=entry,
                              depths=depths, torch=torch, alice=alice, bob=bob)
    finally:
        sim.close()


@pytest.mark.asyncio
class TestMaterialize:

    async def test_enter_materializes_a_private_copy(self, world):
        w = world
        entry = await instances.enter("crypt", w.alice, w.store)

        assert entry is not None
        assert w.alice.location is entry
        # A copy — not the authored template room.
        assert entry is not w.entry
        assert entry.has_tag("ephemeral")
        assert entry.has_tag(f"instance:crypt:{w.alice.id}")
        # The template's zone tag is stripped so zone queries don't mix the
        # copy in with the template.
        assert not entry.has_tag("zone:crypt")

    async def test_copy_clones_the_whole_area(self, world):
        w = world
        entry = await instances.enter("crypt", w.alice, w.store)

        # Contents came along (fresh copies, not the originals).
        torch = next(o for o in entry.contents if o.name == "a torch")
        assert torch is not w.torch
        assert torch.has_tag("ephemeral")
        # The second room was cloned too.
        clones = w.store.find_cached()
        depth_copies = [o for o in clones if o.name == "Crypt Depths"
                        and o.has_tag("ephemeral")]
        assert len(depth_copies) == 1

    async def test_reenter_reuses_the_same_copy(self, world):
        w = world
        first = await instances.enter("crypt", w.alice, w.store)
        w.alice.location = w.hub
        second = await instances.enter("crypt", w.alice, w.store)
        assert second is first

    async def test_each_player_gets_their_own_copy(self, world):
        w = world
        a_entry = await instances.enter("crypt", w.alice, w.store)
        b_entry = await instances.enter("crypt", w.bob, w.store)
        assert a_entry is not b_entry
        assert b_entry.has_tag(f"instance:crypt:{w.bob.id}")


@pytest.mark.asyncio
class TestSharedMode:

    async def test_shared_follower_enters_the_owners_copy(self, world):
        w = world
        a_entry = await instances.enter("crypt", w.alice, w.store, mode="shared")
        w.bob.db.set("following", w.alice.id)
        b_entry = await instances.enter("crypt", w.bob, w.store, mode="shared")
        assert b_entry is a_entry

    async def test_solo_follower_gets_their_own_copy(self, world):
        w = world
        a_entry = await instances.enter("crypt", w.alice, w.store, mode="solo")
        w.bob.db.set("following", w.alice.id)
        b_entry = await instances.enter("crypt", w.bob, w.store, mode="solo")
        assert b_entry is not a_entry


@pytest.mark.asyncio
class TestReaping:

    async def test_idle_empty_copy_is_reaped(self, world):
        w = world
        entry = await instances.enter("crypt", w.alice, w.store)
        w.alice.location = w.hub                      # owner leaves → empty

        reaped = await instances.reap_idle(w.store, now=time.time() + 10_000)

        assert reaped == 1
        assert w.store.get_cached(entry.id) is None   # rooms destroyed
        assert instances.instance_for("crypt", w.alice) is None  # master gone

    async def test_occupied_copy_survives(self, world):
        w = world
        entry = await instances.enter("crypt", w.alice, w.store)  # stays inside

        reaped = await instances.reap_idle(w.store, now=time.time() + 10_000)

        assert reaped == 0
        assert w.store.get_cached(entry.id) is entry

    async def test_fresh_copy_is_not_reaped(self, world):
        w = world
        entry = await instances.enter("crypt", w.alice, w.store)
        w.alice.location = w.hub
        # Empty, but well within its idle TTL.
        reaped = await instances.reap_idle(w.store, now=time.time())
        assert reaped == 0
        assert w.store.get_cached(entry.id) is entry


@pytest.mark.asyncio
class TestEvacuation:

    async def test_destroy_evacuates_straggler_to_return_room(self, world):
        w = world
        entry = await instances.enter("crypt", w.alice, w.store,
                                      return_room=w.hub)
        master = instances.instance_for("crypt", w.alice)

        await instances.destroy_instance(master, w.store)

        assert w.alice.location is w.hub
        assert w.store.get_cached(entry.id) is None

    async def test_destroy_falls_back_to_home(self, world):
        w = world
        w.alice.db.set("home", w.hub.id)
        await instances.enter("crypt", w.alice, w.store)  # no return_room
        master = instances.instance_for("crypt", w.alice)

        await instances.destroy_instance(master, w.store)

        assert w.alice.location is w.hub

    async def test_destroy_falls_back_to_start_room(self, world):
        w = world
        w.hub.add_tag("start_room")     # the world's guaranteed floor
        # No return_room, no home — must still land somewhere, never None.
        await instances.enter("crypt", w.alice, w.store)
        master = instances.instance_for("crypt", w.alice)

        await instances.destroy_instance(master, w.store)

        assert w.alice.location is w.hub


@pytest.mark.asyncio
class TestSoftcodeSurface:

    async def test_enter_instance_moves_the_enactor(self, world):
        w = world
        res, err = await w.sim.eval(
            w.alice, "result = enter_instance(enactor, 'crypt')",
            enactor=w.alice)
        assert err is None
        assert res is True
        assert w.alice.location is not w.hub
        assert w.alice.location.has_tag("ephemeral")

    async def test_non_template_zone_is_refused(self, world):
        w = world
        # 'hub' is a real zone-less area, never opted in as a template.
        res, err = await w.sim.eval(
            w.alice, "result = enter_instance(enactor, 'hub')",
            enactor=w.alice)
        assert err is None
        assert res is False
        assert w.alice.location is w.hub

    async def test_locked_template_refuses_entry(self, world):
        from realm.permissions.locks import LockType
        w = world
        # The author locks the portal room — enter_instance is gated on the
        # entry room's ENTER lock, exactly like teleport_obj's destination.
        w.entry.locks[LockType.ENTER.value] = "False"
        res, err = await w.sim.eval(
            w.alice, "result = enter_instance(enactor, 'crypt')",
            enactor=w.alice)
        assert err is None
        assert res is False
        assert w.alice.location is w.hub


@pytest.mark.asyncio
async def test_ephemeral_objects_are_never_persisted(tmp_path):
    """Kernel bit #1: an ``ephemeral``-tagged object is registered in the
    live cache but never written to SQLite — so a copy can't resurrect on
    reboot. Every save path funnels through ``_save_object``."""
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager

    pm = PersistenceManager(":memory:")
    await pm.initialize()
    try:
        ghost = GameObject(name="ghost room", tags=["ephemeral"])
        solid = GameObject(name="solid room")

        await pm.save(ghost)          # explicit save path
        await pm.save(solid)

        assert await pm.exists(solid.id) is True
        assert await pm.exists(ghost.id) is False   # skipped

        # Registered in the live cache regardless (queryable while it lives).
        assert pm.get_cached(ghost.id) is ghost

        # The dirty-sweep flush skips it too.
        ghost.db.set("touched", True)
        await pm._flush_queue()
        assert await pm.exists(ghost.id) is False
    finally:
        await pm.close()


@pytest.mark.asyncio
async def test_reboot_reconciles_a_player_whose_instance_vanished():
    """Kernel bit #2, reboot half: a player left pointing at an ephemeral
    room (which never reloads) must be relocated on world-load, not dropped
    at 'nowhere'."""
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager, set_active_manager
    from realm.server.game import GameServer

    pm = PersistenceManager(":memory:")
    await pm.initialize()
    set_active_manager(pm)
    try:
        start = GameObject(name="The Void", tags=["room", "start_room"])
        await pm.save(start)
        # Stands for a player reloaded with a dangling (ephemeral) location.
        lost = GameObject(name="Wanderer", tags=["player"])
        await pm.save(lost)
        assert lost.location is None

        server = GameServer.__new__(GameServer)
        server.persistence = pm
        server._startup_room = start
        await server._reconcile_orphaned_players()

        assert lost.location is start
    finally:
        set_active_manager(None)
        await pm.close()
