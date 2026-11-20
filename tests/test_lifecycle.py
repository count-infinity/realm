"""
One destroy path (realm.core.ops.destroy, from KERNEL_PLAN 1.1).

``@destroy``, ``@nuke``, softcode ``destroy_obj()``, expiry reaping and the
load-time orphan sweep all funnel through ``ops.destroy`` so the policy
for players, owned property, ``safe`` objects and paired exits cannot drift
between them (KERNEL_PLAN step 1.1).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.objects import GameObject
from realm.core.ops import Refused, check_destroy, destroy
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


def admin(sim, room, name="Wizard"):
    p = sim.player(name, location=room)
    p.add_tag("admin")
    return p


def exits_of(room):
    return [o for o in room.contents if o.has_tag("exit")]


def live(sim, obj) -> bool:
    return sim.store.get_cached(obj.id) is not None


class TestDestroyCommand:

    async def test_player_in_destroyed_room_is_evacuated(self, sim):
        start = sim.room("Limbo")
        start.add_tag("start_room")
        here = sim.room("Workshop")
        doomed = sim.room("Doomed Hall")
        wiz = admin(sim, here)
        alice = sim.player("Alice", location=doomed)

        await sim.do(wiz, f"@destroy #{doomed.id}")

        assert not live(sim, doomed)
        assert live(sim, alice)
        assert alice.location is start

    async def test_owned_item_goes_to_refuge_unowned_npc_is_destroyed(self, sim):
        start = sim.room("Limbo")
        start.add_tag("start_room")
        here = sim.room("Workshop")
        alice_home = sim.room("Alice's Cottage")
        doomed = sim.room("Doomed Hall")
        wiz = admin(sim, here)
        alice = sim.player("Alice", location=here, home=alice_home.id)
        sword = sim.obj("sword", location=doomed)
        sword.owner = alice
        rat = sim.obj("rat", location=doomed, tags=["npc"])

        await sim.do(wiz, f"@destroy #{doomed.id}")

        assert sword.location is alice_home
        assert live(sim, sword)
        assert not live(sim, rat)

    async def test_destroy_refuses_safe(self, sim):
        here = sim.room("Workshop")
        wiz = admin(sim, here)
        statue = sim.obj("statue", location=here, tags=["safe"])

        await sim.do(wiz, "@destroy statue")

        assert live(sim, statue)
        assert any("protected" in line for line in sim.seen(wiz))

    async def test_nuke_removes_player_and_inventory(self, sim):
        here = sim.room("Workshop")
        wiz = admin(sim, here)
        vandal = sim.player("Vandal", location=here)
        loot = sim.obj("loot", location=vandal)
        loot.owner = vandal

        await sim.do(wiz, "@nuke Vandal")

        assert not live(sim, vandal)
        assert not live(sim, loot)
        assert loot.location is None


class TestSoftcodeDestroy:

    async def test_destroy_obj_refuses_safe(self, sim):
        here = sim.room("Workshop")
        wiz = admin(sim, here)
        statue = sim.obj("statue", location=here, tags=["safe"])
        statue.owner = wiz

        result, err = await sim.eval(wiz, f"result = destroy_obj('#{statue.id}')")

        assert err is None
        assert result is False
        assert live(sim, statue)

    async def test_destroy_obj_leaves_no_dangling_contents(self, sim):
        here = sim.room("Workshop")
        wiz = admin(sim, here)
        chest = sim.obj("chest", location=here)
        chest.owner = wiz
        coin = sim.obj("coin", location=chest)
        gem = sim.obj("gem", location=coin)

        result, err = await sim.eval(wiz, f"result = destroy_obj('#{chest.id}')")

        assert err is None and result is True
        assert not live(sim, chest)
        for obj in sim.store.all_cached():
            loc = obj.location
            assert loc is None or live(sim, loc), (
                f"{obj.name} sits in deleted {loc.name}")
        assert not live(sim, coin) and not live(sim, gem)

    async def test_destroy_obj_of_paired_exit_clears_partner(self, sim):
        here = sim.room("Workshop")
        wiz = admin(sim, here)
        await sim.do(wiz, "@dig The Vault = vault door, vault door")
        vault = sim.store.find_cached(name="The Vault")[0]
        side_a = exits_of(here)[0]
        side_b = exits_of(vault)[0]
        assert side_b.db.get("partner") == "#" + side_a.id

        result, err = await sim.eval(wiz, f"result = destroy_obj('#{side_a.id}')")

        assert err is None and result is True
        assert not live(sim, side_a)
        assert side_b.db.get("partner") is None


class TestDestroyObject:

    def test_check_destroy_refuses_player_and_safe(self):
        player = GameObject("Alice", tags=["player"])
        statue = GameObject("statue", tags=["safe"])
        with pytest.raises(Refused):
            check_destroy(None, player)
        with pytest.raises(Refused):
            check_destroy(None, statue)
        check_destroy(None, player, allow_player=True)

    async def test_returns_count_of_destroyed_contents(self, sim):
        here = sim.room("Workshop")
        chest = sim.obj("chest", location=here)
        sim.obj("coin", location=chest)
        sim.obj("gem", location=chest)

        assert await destroy(None, chest, sim.store) == 2


async def test_destroyed_room_keeps_player_row_on_sqlite(tmp_path, world):
    from realm.core.world import get_world
    from realm.persistence.manager import PersistenceManager

    pm = PersistenceManager(tmp_path / "world.db")
    await pm.initialize()
    get_world().store = pm
    try:
        start = GameObject("Limbo", tags=["room", "start_room"])
        doomed = GameObject("Doomed Hall", tags=["room"])
        alice = GameObject("Alice", tags=["player"], location=doomed)
        for obj in (start, doomed, alice):
            await pm.save(obj)

        await destroy(None, doomed, pm)
        await pm.flush()

        assert await pm.exists(alice.id)
        assert not await pm.exists(doomed.id)
        assert alice.location is start
    finally:
        await pm.close()


async def test_the_start_room_init_world_chose_survives_a_restart(tmp_path):
    """``init_world`` sets ``server.startup_room`` once, on the first boot.
    The choice is kept (the room is tagged ``start_room``), so after a
    restart new characters and the respawning dead still arrive there, not
    in a default void (Midgaard's Common Square was lost this way)."""
    from realm.server.game import GameServer

    async def init_world(server):
        square = GameObject("The Common Square", tags=["room"])
        await server.persistence.save(square)
        server.startup_room = square

    db = tmp_path / "town.db"
    for _boot in range(2):
        srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0,
                         init_world=init_world)
        await srv.start()
        try:
            assert srv.startup_room is not None
            assert srv.startup_room.name == "The Common Square"
            assert not srv.persistence.find_cached(name="The Void")
        finally:
            await srv.stop()


async def test_booting_on_the_default_void_with_rooms_about_warns(tmp_path, caplog):
    """A world saved before that fix booted on its default void ever after.
    Nothing can tell which room was meant, so the boot says so, loudly."""
    import logging

    from realm.server.game import GameServer

    db = tmp_path / "town.db"
    srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0)
    await srv.start()
    await srv.persistence.save(GameObject("The Common Square", tags=["room"]))
    await srv.stop()
    with caplog.at_level(logging.WARNING, logger="realm.server.world"):
        srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0)
        await srv.start()
        await srv.stop()
    assert any("start_room" in r.message and "The Void" in r.message
               for r in caplog.records if r.levelno == logging.WARNING)
    # A builder who dug out of the void (a scaffold's start) is not warned.
    srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0)
    await srv.start()
    void = srv.startup_room
    await srv.persistence.save(GameObject("north", location=void, tags=["exit"]))
    await srv.stop()
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="realm.server.world"):
        srv = GameServer(db_path=str(db), enable_telnet=False, tick_interval=0)
        await srv.start()
        await srv.stop()
    assert not any("start_room" in r.message for r in caplog.records)
