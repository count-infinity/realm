"""
World queries (find_objects/@find/search_world + protected attrs) and
zones (masters, zone_property, trigger/event seams, XP multiplier).
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.core.propagation import get_engine, reset_engine
from realm.core.query import find_objects
from realm.core.zones import zone_masters, zone_property, zone_rooms
from realm.gateway.session import Session
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    reset_engine()


def make_world(pers):
    keep = GameObject("Keep", tags=["room", "zone:castle"])
    yard = GameObject("Yard", tags=["room", "zone:castle"])
    woods = GameObject("Woods", tags=["room", "zone:forest"])
    master = GameObject("Castle Zone", tags=["zone_master", "zone:castle"])
    master.db.xp_multiplier = 1.2
    sword = GameObject("iron sword", tags=["thing"], location=keep)
    sword.db.value = 50
    for o in (keep, yard, woods, master, sword):
        pers.add(o)
    return keep, yard, woods, master, sword


class TestFindObjects:

    def test_filters_compose(self):
        pers = MockPersistence()
        keep, _yard, _woods, master, sword = make_world(pers)
        objs = pers.all_cached()

        assert set(find_objects(objs, tag="zone:castle")) == {keep, _yard, master}
        assert find_objects(objs, tag="room", tags=["zone:castle"]) == [keep, _yard]
        assert find_objects(objs, attr="value", value=50) == [sword]
        assert find_objects(objs, attr="value", value=99) == []
        assert find_objects(objs, name_like="zone") == [master]
        assert len(find_objects(objs, tag="room", limit=2)) == 2


class TestZones:

    def test_masters_and_property(self):
        pers = MockPersistence()
        use_persistence(pers)
        keep, _y, woods, master, _s = make_world(pers)
        from realm.persistence.manager import set_active_manager
        set_active_manager(pers)
        try:
            assert zone_masters(keep) == [master]
            assert zone_masters(woods) == []
            assert zone_property(keep, "xp_multiplier", 1.0) == 1.2
            assert zone_property(woods, "xp_multiplier", 1.0) == 1.0
            assert {r.name for r in zone_rooms("castle")} == {"Keep", "Yard"}
        finally:
            set_active_manager(None)

    def test_overlapping_zones_max_wins(self):
        pers = MockPersistence()
        room = GameObject("Border", tags=["room", "zone:a", "zone:b"])
        m1 = GameObject("A", tags=["zone_master", "zone:a"])
        m1.db.xp_multiplier = 1.1
        m2 = GameObject("B", tags=["zone_master", "zone:b"])
        m2.db.xp_multiplier = 1.5
        for o in (room, m1, m2):
            pers.add(o)
        from realm.persistence.manager import set_active_manager
        set_active_manager(pers)
        try:
            assert zone_property(room, "xp_multiplier") == 1.5
        finally:
            set_active_manager(None)


@pytest.mark.asyncio
class TestZoneSeams:

    async def test_zone_wide_dollar_command(self):
        from realm.scripting.engine import ScriptEngine
        from realm.server.dispatcher import CommandContext

        pers = MockPersistence()
        keep, _y, _w, master, _s = make_world(pers)
        master.db.cmd_pray = "$pray:say The castle hears your prayer."
        from realm.persistence.manager import set_active_manager
        set_active_manager(pers)
        try:
            alice = GameObject("Alice", tags=["player"], location=keep)
            sess = Session(protocol="test", address="1.1.1.1")
            sess.link_player(alice)

            engine = ScriptEngine()
            get_engine().add_observer(engine.handle_action)
            ctx = CommandContext(session=sess, player=alice, raw_input="pray",
                                 command_name="pray", args="")
            handled = await engine.handle_unknown_command(ctx)
            assert handled is True
        finally:
            set_active_manager(None)

    async def test_master_witnesses_member_room_events(self):
        from realm.core.movement import move_through_exit
        from realm.scripting.engine import ScriptEngine

        pers = MockPersistence()
        keep, yard, _w, master, _s = make_world(pers)
        door = GameObject("gate", tags=["exit"], location=yard)
        door.db.destination_obj = keep
        master.db.on_enter = "remit(get('#' + '%l'), 'The castle stirs.')"
        master.db.on_enter = "set_attr(me, 'stirred', True)"
        from realm.persistence.manager import set_active_manager
        set_active_manager(pers)
        try:
            alice = GameObject("Alice", tags=["player"], location=yard)
            engine = ScriptEngine(persistence=pers)
            get_engine().add_observer(engine.handle_action)

            await move_through_exit(alice, keep, exit_obj=door)
            assert master.db.get("stirred") is True
        finally:
            set_active_manager(None)

    async def test_zone_xp_multiplier_applies(self):
        from realm.combat.manager import CombatManager, set_combat_manager
        from realm.combat.system import CombatSystem
        from realm.persistence.manager import set_active_manager
        from tests.test_combat_encounters import FixedRuleset

        pers = MockPersistence()
        keep, _y, _w, master, _s = make_world(pers)
        set_active_manager(pers)
        mgr = CombatManager(CombatSystem(ruleset=FixedRuleset()),
                            beat_min=4, beat_max=120, beat_default=15)
        set_combat_manager(mgr)
        try:
            alice = GameObject("Alice", tags=["player"], location=keep)
            ogre = GameObject("ogre", tags=["npc"], location=keep)
            ogre.db.points = 100  # base award 10 -> x1.2 = 12

            await mgr.handle_death(ogre, killer=alice)
            assert alice.db.get("character_points") == 12
        finally:
            mgr.stop_all()
            set_combat_manager(None)
            set_active_manager(None)


@pytest.mark.asyncio
class TestSoftcodeSurfaces:

    async def test_search_world_and_zone_sugar(self):
        from realm.persistence.manager import set_active_manager
        from realm.scripting.functions import ScriptFunctions

        pers = MockPersistence()
        keep, _y, _w, master, sword = make_world(pers)
        set_active_manager(pers)
        try:
            funcs = ScriptFunctions(executor=master, persistence=pers)
            assert sword in funcs.search_world(tag="thing")
            assert funcs.search_world(attr="value", value=50) == [sword]
            assert {r.name for r in funcs.zone_rooms("castle")} == {"Keep", "Yard"}
            assert funcs.zones_of(keep) == ["castle"]
        finally:
            set_active_manager(None)

    async def test_protected_attrs_hidden(self):
        from realm.scripting.functions import ScriptFunctions

        pers = MockPersistence()
        alice = GameObject("Alice", tags=["player"])
        alice.db.password = "scrypt$deadbeef$cafe"
        pers.add(alice)
        imp = GameObject("imp")
        funcs = ScriptFunctions(executor=imp, persistence=pers)

        assert funcs.get_attr(alice, "password") is None
        assert funcs.has_attr(alice, "password") is False
        assert funcs.search_world(attr="password") == []


@pytest.mark.asyncio
class TestZoneCommand:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_zone_add_master_and_rooms(self):
        from realm.commands.olc.softcode import cmd_zone
        from realm.persistence.manager import set_active_manager

        set_active_manager(self.persistence)
        try:
            room = GameObject("Keep", tags=["room"])
            bea = GameObject("Bea", tags=["player", "builder"], location=room)
            brain = GameObject("Castle Brain", location=room, owner=bea)
            self.persistence.add(room)
            self.persistence.add(brain)

            ctx = make_context(bea, left_args="here", right_args="castle")
            await cmd_zone(ctx)
            assert room.has_tag("zone:castle")

            ctx = make_context(bea, left_args="Castle Brain",
                               right_args="castle", switches=["master"])
            await cmd_zone(ctx)
            assert brain.has_tag("zone_master")
            assert zone_masters(room) == [brain]

            ctx = make_context(bea, args="castle", switches=["rooms"])
            await cmd_zone(ctx)
            assert any("Keep" in m for m in ctx.session.messages)
        finally:
            set_active_manager(None)


class TestTagValues:

    def test_namespaced_tag_reads(self):
        from realm.scripting.functions import ScriptFunctions

        room = GameObject("Keep", tags=["room", "zone:castle",
                                        "zone:haunted", "climate:coastal"])
        funcs = ScriptFunctions(executor=room)
        assert funcs.tag_value(room, "zone") == "castle"
        assert funcs.tag_values(room, "zone") == ["castle", "haunted"]
        assert funcs.tag_value(room, "climate:") == "coastal"  # colon ok
        assert funcs.tag_value(room, "faction") is None
        assert funcs.tag_values(None, "zone") == []
