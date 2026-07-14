"""
Wilderness — coordinate-keyed ephemeral cells, materialized on demand.
See docs/design/wilderness-requirements.md (§7 is this test plan).

Cells are real rooms shared per coordinate, entered through real exits
with deferred destinations (``dest_resolver = "wilderness"``), reaped
when empty of players, and torn down under the R9 disposition: players
evacuated, player-owned property to its owner's refuge, everything else
destroyed loudly.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from realm.core import wilderness
from realm.testing import Simulator

IS_VALID = "result = 0 <= x <= 4 and 0 <= y <= 4"
CELL_NAME = "result = 'Meadow ' + str(x) + ',' + str(y)"
CELL_DESC = "result = 'Grass ripples at ' + str(x) + ',' + str(y) + '.'"
EDGE_MSG = "The thorn wall blocks your way."


@pytest.fixture
def world():
    """A 5x5 ``wilds`` region, a town with a gate into it at (2, 2)."""
    sim = Simulator()
    wilderness.reset()
    town = sim.room("Town Square")
    town.add_tag("start_room")

    master = sim.obj("wilds", tags=["wilderness_region"])
    master.db.set("is_valid", IS_VALID)
    master.db.set("cell_name", CELL_NAME)
    master.db.set("cell_desc", CELL_DESC)
    master.db.set("edge_msg", EDGE_MSG)

    gate = sim.obj("wild", location=town, tags=["exit"])
    gate.db.set("dest_resolver", "wilderness")
    gate.db.set("wild_region", "wilds")
    gate.db.set("wild_x", 2)
    gate.db.set("wild_y", 2)

    alice = sim.player("Alice", location=town)
    bob = sim.player("Bob", location=town)
    try:
        yield SimpleNamespace(sim=sim, store=sim.store, town=town,
                              master=master, gate=gate, alice=alice, bob=bob)
    finally:
        wilderness.reset()
        sim.close()


@pytest.mark.asyncio
class TestMaterialize:

    async def test_valid_coord_builds_a_tagged_cell(self, world):
        w = world
        cell = await wilderness.materialize_cell("wilds", 2, 2, w.store)

        assert cell is not None
        assert cell.has_tag("room")
        assert cell.has_tag("ephemeral")
        assert cell.has_tag("zone:wilderness:wilds")
        assert cell.has_tag("wildcell:wilds:2,2")
        assert cell.name == "Meadow 2,2"
        assert cell.db.get("wild_region") == "wilds"
        assert (cell.db.get("wild_x"), cell.db.get("wild_y")) == (2, 2)
        # Indexed: the same live cell comes back.
        assert wilderness.cell_for("wilds", 2, 2) is cell

    async def test_cell_exits_are_deferred_real_exits(self, world):
        w = world
        cell = await wilderness.materialize_cell("wilds", 2, 2, w.store)
        exits = [o for o in cell.contents if o.has_tag("exit")]

        assert sorted(e.name for e in exits) == ["east", "north", "south", "west"]
        for e in exits:
            assert e.has_tag("ephemeral")
            assert e.db.get("dest_resolver") == "wilderness"
            assert e.db.get("destination") is None
            assert e.db.get("fail_msg") == EDGE_MSG

    async def test_invalid_coord_returns_none(self, world):
        w = world
        assert await wilderness.materialize_cell("wilds", 9, 9, w.store) is None
        assert wilderness.cell_for("wilds", 9, 9) is None

    async def test_missing_region_raises_provider_error(self, world):
        w = world
        with pytest.raises(wilderness.ProviderError):
            await wilderness.materialize_cell("nowhere", 0, 0, w.store)

    async def test_broken_is_valid_raises_never_masquerades(self, world):
        w = world
        w.master.db.set("is_valid", "result = 1 / 0")
        with pytest.raises(wilderness.ProviderError):
            await wilderness.materialize_cell("wilds", 2, 2, w.store)

    async def test_broken_flavor_falls_back_to_defaults(self, world):
        w = world
        w.master.db.set("cell_name", "result = 1 / 0")
        cell = await wilderness.materialize_cell("wilds", 2, 2, w.store)
        assert cell is not None
        assert cell.name == "wilds (2, 2)"      # terse default, cell still built


@pytest.mark.asyncio
class TestWalking:

    async def test_gate_drops_the_walker_at_the_entry_coord(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        assert w.alice.location is not w.town
        assert w.alice.location.has_tag("wildcell:wilds:2,2")

    async def test_walking_materializes_the_neighbor(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        await w.sim.do(w.alice, "north")
        assert w.alice.location.has_tag("wildcell:wilds:2,3")

    async def test_two_players_share_one_cell(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        await w.sim.do(w.bob, "wild")
        assert w.alice.location is w.bob.location

    async def test_walking_back_rejoins_the_same_cell(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        await w.sim.do(w.bob, "wild")
        origin = w.alice.location
        await w.sim.do(w.alice, "north")
        await w.sim.do(w.alice, "south")
        assert w.alice.location is origin       # bob kept it alive; rejoined

    async def test_map_edge_shows_the_authored_message(self, world):
        w = world
        await wilderness.enter_cell(w.alice, "wilds", 2, 4, w.store)
        await w.sim.do(w.alice, "north")        # y=5 is out of bounds

        assert w.alice.location.has_tag("wildcell:wilds:2,4")
        assert wilderness.cell_for("wilds", 2, 5) is None
        assert any(EDGE_MSG in line for line in w.sim.seen(w.alice))

    async def test_refused_walker_materializes_nothing(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        w.alice.add_tag("in_combat")
        await w.sim.do(w.alice, "north")

        assert w.alice.location.has_tag("wildcell:wilds:2,2")
        assert wilderness.cell_for("wilds", 2, 3) is None
        w.alice.remove_tag("in_combat")

    async def test_followers_cascade_into_the_neighbor(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        await w.sim.do(w.bob, "wild")
        w.bob.db.set("following", w.alice.id)
        await w.sim.do(w.alice, "north")

        assert w.alice.location.has_tag("wildcell:wilds:2,3")
        assert w.bob.location is w.alice.location

    async def test_broken_provider_is_loud_and_distinct(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        origin = w.alice.location
        w.master.db.set("is_valid", "result = 1 / 0")
        w.sim.seen(w.alice)                     # drain prior output
        await w.sim.do(w.alice, "north")

        assert w.alice.location is origin
        assert wilderness.cell_for("wilds", 2, 3) is None
        seen = w.sim.seen(w.alice)
        assert any("strange force" in line for line in seen)
        assert not any(EDGE_MSG in line for line in seen)


@pytest.mark.asyncio
class TestScriptedEntry:

    async def test_enter_wilderness_moves_the_enactor(self, world):
        w = world
        res, err = await w.sim.eval(
            w.alice, "result = enter_wilderness(enactor, 'wilds', 1, 1)",
            enactor=w.alice)
        assert err is None
        assert res is True
        assert w.alice.location.has_tag("wildcell:wilds:1,1")

    async def test_unknown_region_is_refused(self, world):
        w = world
        res, err = await w.sim.eval(
            w.alice, "result = enter_wilderness(enactor, 'nowhere', 1, 1)",
            enactor=w.alice)
        assert err is None
        assert res is False
        assert w.alice.location is w.town

    async def test_locked_region_refuses_entry(self, world):
        from realm.permissions.locks import LockType
        w = world
        w.master.locks[LockType.ENTER.value] = "False"
        res, err = await w.sim.eval(
            w.alice, "result = enter_wilderness(enactor, 'wilds', 1, 1)",
            enactor=w.alice)
        assert err is None
        assert res is False
        assert w.alice.location is w.town

    async def test_cell_occupant_cannot_relocate_a_co_occupant(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        await w.sim.do(w.bob, "wild")
        rock = w.sim.obj("a strange rock", location=w.alice.location)
        res, err = await w.sim.eval(
            rock, f"result = move_to('{w.bob.id}', '{w.town.id}')",
            enactor=rock)
        assert err is None
        assert res is False                     # unowned cell grants nothing
        assert w.bob.location is w.alice.location


@pytest.mark.asyncio
class TestReaping:

    async def test_empty_cell_past_ttl_is_reaped(self, world):
        w = world
        cell = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        exit_ids = [o.id for o in cell.contents if o.has_tag("exit")]

        reaped = await wilderness.reap_wilderness(
            w.store, now=time.time() + 10_000)

        assert reaped == 1
        assert wilderness.cell_for("wilds", 0, 0) is None
        assert w.store.get_cached(cell.id) is None
        assert all(w.store.get_cached(i) is None for i in exit_ids)

    async def test_occupied_cell_survives(self, world):
        w = world
        await w.sim.do(w.alice, "wild")
        cell = w.alice.location
        reaped = await wilderness.reap_wilderness(
            w.store, now=time.time() + 10_000)
        assert reaped == 0
        assert w.store.get_cached(cell.id) is cell

    async def test_fresh_empty_cell_is_not_reaped(self, world):
        w = world
        cell = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        reaped = await wilderness.reap_wilderness(w.store, now=time.time())
        assert reaped == 0
        assert w.store.get_cached(cell.id) is cell

    async def test_rematerialized_cell_has_identical_topology(self, world):
        w = world
        first = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        first_exits = sorted(
            o.name for o in first.contents if o.has_tag("exit"))
        await wilderness.reap_wilderness(w.store, now=time.time() + 10_000)

        second = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        second_exits = sorted(
            o.name for o in second.contents if o.has_tag("exit"))

        assert second is not first              # recreate, don't resurrect
        assert second_exits == first_exits      # R2 determinism
        assert second.name == first.name

    async def test_straggler_is_evacuated_on_destroy(self, world):
        w = world
        cell = await wilderness.enter_cell(w.alice, "wilds", 3, 3, w.store)
        await wilderness.destroy_cell(cell, w.store)
        assert w.alice.location is w.town       # home ladder -> start room

    async def test_unowned_contents_are_destroyed(self, world):
        w = world
        cell = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        rock = w.sim.obj("a rock", location=cell)
        wolf = w.sim.obj("a wolf", location=cell, tags=["npc"])

        await wilderness.reap_wilderness(w.store, now=time.time() + 10_000)

        assert w.store.get_cached(rock.id) is None
        assert w.store.get_cached(wolf.id) is None

    async def test_player_owned_item_lands_in_the_owners_home(self, world):
        w = world
        w.alice.db.set("home", w.town.id)
        cell = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        sword = w.sim.obj("a sword", location=cell)
        sword.owner = w.alice

        await wilderness.reap_wilderness(w.store, now=time.time() + 10_000)

        assert w.store.get_cached(sword.id) is sword
        assert sword.location is w.town


@pytest.mark.asyncio
class TestReviewRegressions:
    """Pins for the adversarial-review findings (see wilderness spec §6)."""

    async def test_typo_resolver_name_is_loud_not_geography(self, world):
        w = world
        hatch = w.sim.obj("hatch", location=w.town, tags=["exit"])
        hatch.db.set("dest_resolver", "no-such-resolver")
        await w.sim.do(w.alice, "hatch")

        assert w.alice.location is w.town
        assert any("strange force" in line for line in w.sim.seen(w.alice))

    async def test_world_entry_missing_wild_y_is_a_dead_end_not_y0(self, world):
        w = world
        half = w.sim.obj("rift", location=w.town, tags=["exit"])
        half.db.set("dest_resolver", "wilderness")
        half.db.set("wild_region", "wilds")
        half.db.set("wild_x", 2)                     # wild_y never set
        await w.sim.do(w.alice, "rift")

        assert w.alice.location is w.town
        assert wilderness.cell_for("wilds", 2, 0) is None

    async def test_malformed_coords_do_not_crash_the_walk(self, world):
        w = world
        bent = w.sim.obj("bent", location=w.town, tags=["exit"])
        bent.db.set("dest_resolver", "wilderness")
        bent.db.set("wild_region", "wilds")
        bent.db.set("wild_x", "abc")
        bent.db.set("wild_y", 2)
        await w.sim.do(w.alice, "bent")

        assert w.alice.location is w.town            # dead-end, no crash

    async def test_wrong_typed_cell_exits_falls_back_to_compass(self, world):
        w = world
        w.master.db.set("cell_exits", "result = 42")
        cell = await wilderness.materialize_cell("wilds", 2, 2, w.store)
        exits = sorted(o.name for o in cell.contents if o.has_tag("exit"))
        assert exits == ["east", "north", "south", "west"]

    async def test_garbage_idle_ttl_does_not_kill_the_reaper(self, world):
        w = world
        w.master.db.set("idle_ttl", "soon")
        await wilderness.materialize_cell("wilds", 0, 0, w.store)
        reaped = await wilderness.reap_wilderness(
            w.store, now=time.time() + 10_000)
        assert reaped == 1                            # default TTL applied

    async def test_nested_occupants_get_the_r9_disposition(self, world):
        w = world
        w.alice.db.set("home", w.town.id)
        cell = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        crate = w.sim.obj("a crate", location=cell)
        sword = w.sim.obj("a sword", location=crate)
        sword.owner = w.alice
        w.bob.location = crate                        # player INSIDE the crate

        await wilderness.destroy_cell(cell, w.store)

        assert w.bob.location is w.town               # evacuated, not deleted
        assert sword.location is w.town               # owner's refuge
        assert w.store.get_cached(crate.id) is None   # unowned shell destroyed

    async def test_reap_sees_a_player_nested_in_a_container(self, world):
        w = world
        cell = await wilderness.materialize_cell("wilds", 0, 0, w.store)
        wagon = w.sim.obj("a wagon", location=cell)
        w.bob.location = wagon

        reaped = await wilderness.reap_wilderness(
            w.store, now=time.time() + 10_000)

        assert reaped == 0
        assert w.store.get_cached(cell.id) is cell

    async def test_deferred_edge_honors_an_authored_on_fail_portal(self, world):
        w = world
        crypt = w.sim.room("Crypt Entrance")
        crypt.add_tag("zone:crypt")
        crypt.add_tag("instance_template")
        crypt.add_tag("instance_entry")

        await wilderness.enter_cell(w.alice, "wilds", 2, 4, w.store)
        cell = w.alice.location
        north = next(o for o in cell.contents if o.name == "north")
        north.db.set("on_fail", "enter_instance(enactor, 'crypt')")
        w.sim.seen(w.alice)                           # drain prior output
        await w.sim.do(w.alice, "north")              # y=5: edge -> ON_FAIL

        assert w.alice.location.has_tag("ephemeral")  # relocated by @afail
        assert w.alice.location.name == "Crypt Entrance"
        seen = w.sim.seen(w.alice)
        assert not any(EDGE_MSG in line for line in seen)   # line suppressed
        assert any("Crypt Entrance" in line for line in seen)  # room rendered


@pytest.mark.asyncio
async def test_deleted_object_is_not_resurrected_by_a_stale_flush():
    """The 4s reap tick can delete an object a 5s flush pass already swept
    up — INSERT OR REPLACE must not resurrect its row as silent limbo."""
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager

    pm = PersistenceManager(":memory:")
    await pm.initialize()
    try:
        rock = GameObject(name="a rock")
        await pm.save(rock)
        assert await pm.exists(rock.id) is True

        await pm.delete(rock)
        await pm._save_object(rock)      # the stale flush write

        assert await pm.exists(rock.id) is False
    finally:
        await pm.close()


@pytest.mark.asyncio
async def test_wilderness_cells_are_never_persisted():
    """A real ``:memory:`` PersistenceManager never writes a cell or its
    exits (mirror of test_instances.test_ephemeral_objects_are_never_persisted)."""
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager, set_active_manager

    pm = PersistenceManager(":memory:")
    await pm.initialize()
    set_active_manager(pm)
    wilderness.reset()
    try:
        master = GameObject(name="wilds", tags=["wilderness_region"])
        master.db.set("is_valid", IS_VALID)
        await pm.save(master)

        cell = await wilderness.materialize_cell("wilds", 1, 1, pm)

        assert cell is not None
        assert await pm.exists(master.id) is True
        assert await pm.exists(cell.id) is False
        for obj in cell.contents:
            assert await pm.exists(obj.id) is False
        # Live-cache queryable while it lives, like every ephemeral.
        assert pm.get_cached(cell.id) is cell
    finally:
        wilderness.reset()
        set_active_manager(None)
        await pm.close()


@pytest.mark.asyncio
async def test_reboot_reconciles_objects_with_dangled_locations(tmp_path):
    """R9's crash-path backstop: a persistent object whose stored location
    was an ephemeral room reloads dangling — a player-owned one lands in
    its owner's refuge; an unowned one is reaped, loudly. Nothing sits
    silently at location=None."""
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager, set_active_manager
    from realm.server.game import GameServer

    db = tmp_path / "wild.db"
    pm = PersistenceManager(db)
    await pm.initialize()
    set_active_manager(pm)
    try:
        start = GameObject(name="The Void", tags=["room", "start_room"])
        await pm.save(start)
        owner = GameObject(name="Alice", tags=["player"])
        owner.db.set("home", start.id)
        owner.location = start
        await pm.save(owner)
        ghost = GameObject(name="ghost cell", tags=["room", "ephemeral"])
        await pm.save(ghost)                     # never actually written
        sword = GameObject(name="a sword")
        sword.owner = owner
        sword.location = ghost
        await pm.save(sword)                     # row: location_id -> ghost
        rock = GameObject(name="a rock")
        rock.location = ghost
        await pm.save(rock)
        sword_id, rock_id, start_id = sword.id, rock.id, start.id
    finally:
        set_active_manager(None)
        await pm.close()

    pm2 = PersistenceManager(db)
    await pm2.initialize()
    set_active_manager(pm2)
    try:
        await pm2.load_all()
        server = GameServer.__new__(GameServer)
        server.persistence = pm2
        server._startup_room = pm2.get_cached(start_id)
        await server._reconcile_orphaned_players()

        sword2 = pm2.get_cached(sword_id)
        assert sword2 is not None
        assert sword2.location is pm2.get_cached(start_id)   # owner's home
        assert pm2.get_cached(rock_id) is None               # reaped
        assert await pm2.exists(rock_id) is False
    finally:
        set_active_manager(None)
        await pm2.close()


@pytest.mark.asyncio
async def test_reconcile_empties_a_dangling_container_before_reaping_it(tmp_path):
    """A player (or player property) that reloaded INSIDE a dangling
    unowned container is released before the container is deleted."""
    from realm.core.objects import GameObject
    from realm.persistence.manager import PersistenceManager, set_active_manager
    from realm.server.game import GameServer

    db = tmp_path / "nest.db"
    pm = PersistenceManager(db)
    await pm.initialize()
    set_active_manager(pm)
    try:
        start = GameObject(name="The Void", tags=["room", "start_room"])
        await pm.save(start)
        owner = GameObject(name="Alice", tags=["player"])
        owner.db.set("home", start.id)
        owner.location = start
        await pm.save(owner)
        ghost = GameObject(name="ghost cell", tags=["room", "ephemeral"])
        await pm.save(ghost)                     # never actually written
        wagon = GameObject(name="a wagon")       # unowned, in the ghost room
        wagon.location = ghost
        await pm.save(wagon)
        rider = GameObject(name="Bob", tags=["player"])
        rider.location = wagon                   # player INSIDE the wagon
        await pm.save(rider)
        sword = GameObject(name="a sword")       # owned, inside the wagon
        sword.owner = owner
        sword.location = wagon
        await pm.save(sword)
        ids = (start.id, wagon.id, rider.id, sword.id)
    finally:
        set_active_manager(None)
        await pm.close()

    start_id, wagon_id, rider_id, sword_id = ids
    pm2 = PersistenceManager(db)
    await pm2.initialize()
    set_active_manager(pm2)
    try:
        await pm2.load_all()
        server = GameServer.__new__(GameServer)
        server.persistence = pm2
        server._startup_room = pm2.get_cached(start_id)
        await server._reconcile_orphaned_players()

        start2 = pm2.get_cached(start_id)
        assert pm2.get_cached(rider_id).location is start2   # evacuated
        assert pm2.get_cached(sword_id).location is start2   # owner's home
        assert pm2.get_cached(wagon_id) is None              # then reaped
        assert await pm2.exists(wagon_id) is False
    finally:
        set_active_manager(None)
        await pm2.close()
