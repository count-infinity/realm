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

    async def test_reenter_after_reap_materializes_a_fresh_copy(self, world):
        w = world
        first = await instances.enter("crypt", w.alice, w.store)
        w.alice.location = w.hub
        await instances.reap_idle(w.store, now=time.time() + 10_000)

        second = await instances.enter("crypt", w.alice, w.store)

        assert second is not None
        assert second is not first          # recreate, don't resurrect
        assert w.alice.location is second

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


def _portal(sim, room, template="crypt", **attrs):
    """A real portal exit with a deferred instance destination."""
    portal = sim.obj("portal", location=room, tags=["exit"])
    portal.db.set("dest_resolver", "instance")
    portal.db.set("instance_template", template)
    for key, value in attrs.items():
        portal.db.set(key, value)
    return portal


@pytest.mark.asyncio
class TestPortalExit:
    """Instance portals as real exits (dest_resolver="instance") — the
    deferred-destination migration; walking is a normal traversal."""

    async def test_walking_the_portal_materializes_and_moves(self, world):
        w = world
        _portal(w.sim, w.hub)
        await w.sim.do(w.alice, "portal")

        assert w.alice.location is not w.hub
        assert w.alice.location.has_tag("ephemeral")
        assert w.alice.location.has_tag(f"instance:crypt:{w.alice.id}")

    async def test_return_room_defaults_to_the_portal_room(self, world):
        w = world
        _portal(w.sim, w.hub)
        await w.sim.do(w.alice, "portal")
        master = instances.instance_for("crypt", w.alice)

        await instances.destroy_instance(master, w.store)

        assert w.alice.location is w.hub      # evacuated to where they entered

    async def test_rewalk_reuses_the_same_copy(self, world):
        w = world
        _portal(w.sim, w.hub)
        await w.sim.do(w.alice, "portal")
        first = w.alice.location
        w.alice.location = w.hub
        await w.sim.do(w.alice, "portal")
        assert w.alice.location is first

    async def test_two_players_get_separate_solo_copies(self, world):
        w = world
        _portal(w.sim, w.hub)
        await w.sim.do(w.alice, "portal")
        await w.sim.do(w.bob, "portal")
        assert w.alice.location is not w.bob.location

    async def test_shared_portal_cascades_followers_into_the_owners_copy(self, world):
        w = world
        _portal(w.sim, w.hub, instance_mode="shared")
        w.bob.db.set("following", w.alice.id)
        await w.sim.do(w.alice, "portal")

        assert w.bob.location is w.alice.location    # routed, not left behind
        assert w.bob.location.has_tag(f"instance:crypt:{w.alice.id}")

    async def test_solo_portal_bounces_the_follower_at_the_threshold(self, world):
        w = world
        _portal(w.sim, w.hub)                        # mode defaults to solo
        w.bob.db.set("following", w.alice.id)
        await w.sim.do(w.alice, "portal")

        assert w.alice.location.has_tag(f"instance:crypt:{w.alice.id}")
        assert w.bob.location is w.hub               # bounced, no second copy
        assert instances.instance_for("crypt", w.bob) is None

    async def test_npc_pet_rides_a_shared_copy_but_never_owns_one(self, world):
        w = world
        portal = _portal(w.sim, w.hub, instance_mode="shared")
        pet = w.sim.obj("a loyal hound", location=w.hub, tags=["npc"])
        pet.db.set("following", w.alice.id)
        await w.sim.do(w.alice, "portal")
        assert pet.location is w.alice.location      # routed into the copy

        lone = w.sim.obj("a stray cat", location=w.hub, tags=["npc"])
        assert await instances.resolve_instance_exit(portal, lone) is None
        assert instances.instance_for("crypt", lone) is None

    async def test_locked_template_refuses_before_materializing(self, world):
        from realm.permissions.locks import LockType
        w = world
        _portal(w.sim, w.hub)
        w.entry.locks[LockType.ENTER.value] = "False"
        await w.sim.do(w.alice, "portal")

        assert w.alice.location is w.hub
        assert instances.instance_for("crypt", w.alice) is None  # no import

    async def test_non_template_zone_is_loud_not_geography(self, world):
        w = world
        _portal(w.sim, w.hub, template="hub")        # never opted in
        await w.sim.do(w.alice, "portal")

        assert w.alice.location is w.hub
        assert any("strange force" in line for line in w.sim.seen(w.alice))

    async def test_refused_walker_materializes_nothing(self, world):
        w = world
        _portal(w.sim, w.hub)
        w.alice.add_tag("in_combat")
        await w.sim.do(w.alice, "portal")

        assert w.alice.location is w.hub
        assert instances.instance_for("crypt", w.alice) is None
        w.alice.remove_tag("in_combat")

    async def test_garbage_ttl_falls_back_to_the_default(self, world):
        w = world
        _portal(w.sim, w.hub, instance_ttl="soon")
        await w.sim.do(w.alice, "portal")
        master = instances.instance_for("crypt", w.alice)
        assert master.db.get("idle_ttl") == instances.DEFAULT_IDLE_TTL

    async def test_dual_attr_exit_never_splits_the_party(self, world):
        """An exit carrying BOTH a static destination and a dest_resolver:
        the static destination wins for every walker — the leader and the
        followers all land in the same place."""
        w = world
        street = w.sim.room("Street")
        door = _portal(w.sim, w.hub)
        door.db.set("destination", street.id)        # static wins
        w.bob.db.set("following", w.alice.id)
        await w.sim.do(w.alice, "portal")

        assert w.alice.location is street
        assert w.bob.location is street              # not routed, not blocked
        assert instances.instance_for("crypt", w.alice) is None

    async def test_transitive_shared_chain_rides_the_owners_copy(self, world):
        """A follows B follows C: the whole chain lands in C's shared
        copy, not in per-member private copies."""
        w = world
        carol = w.sim.player("Carol", location=w.hub)
        _portal(w.sim, w.hub, instance_mode="shared")
        w.bob.db.set("following", w.alice.id)
        carol.db.set("following", w.bob.id)
        await w.sim.do(w.alice, "portal")

        assert w.bob.location is w.alice.location
        assert carol.location is w.alice.location
        assert instances.instance_for("crypt", carol) is not None
        assert len(instances._masters("crypt")) == 1  # one copy, one party

    async def test_transitive_solo_chain_bounces_everyone(self, world):
        w = world
        carol = w.sim.player("Carol", location=w.hub)
        _portal(w.sim, w.hub)                        # solo
        w.bob.db.set("following", w.alice.id)
        carol.db.set("following", w.bob.id)
        await w.sim.do(w.alice, "portal")

        assert w.alice.location.has_tag(f"instance:crypt:{w.alice.id}")
        assert w.bob.location is w.hub
        assert carol.location is w.hub
        assert len(instances._masters("crypt")) == 1

    async def test_identity_sensitive_lock_leaves_no_orphan_copy(self, world):
        """A lock reading the ROOM's identity can pass on the template and
        deny on the fresh clone (new tags/ids) — the just-imported copy is
        torn down, not left to linger until the reaper."""
        from realm.permissions.locks import LockType
        w = world
        _portal(w.sim, w.hub)
        w.entry.locks[LockType.ENTER.value] = "not target.has_tag('ephemeral')"
        await w.sim.do(w.alice, "portal")

        assert w.alice.location is w.hub
        assert instances.instance_for("crypt", w.alice) is None
        ghosts = [o for o in w.store.find_cached(tag="ephemeral")
                  if o.has_tag("room")]
        assert ghosts == []                          # nothing lingers


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

        # __new__ skips __init__ deliberately: _reconcile_orphaned_players
        # touches only .persistence and ._startup_room, and a full GameServer
        # would drag in sockets/dispatcher we don't want in a unit test.
        server = GameServer.__new__(GameServer)
        server.persistence = pm
        server._startup_room = start
        await server._reconcile_orphaned_players()

        assert lost.location is start
    finally:
        set_active_manager(None)
        await pm.close()
