"""
Tests for the space game example.
"""

import json
from pathlib import Path

import pytest

import realm.std.combat.behaviors  # noqa: F401
from realm.persistence.memory import MemoryStore
from realm.persistence.worldio import import_objects
from realm.testing import Simulator

_STATION = (Path(__file__).resolve().parent.parent
            / "realm" / "examples" / "spacegame" / "data" / "areas" / "station.json")


@pytest.mark.asyncio
class TestStationArea:
    """The spacegame world is now DATA — an importable area file (init_world
    imports it instead of building line-by-line). This is the round-trip."""

    async def _import(self, sim):
        data = json.loads(_STATION.read_text())
        return await import_objects(data, sim.store, preserve_ids=True)

    async def test_area_reconstitutes_the_world(self):
        sim = Simulator()
        try:
            created = await self._import(sim)
            by_name = {o.name: o for o in created}
            # Rooms + the start room the area carries.
            assert "Docking Bay Alpha-1" in by_name
            assert any(o.has_tag("start_room") for o in created)
            # Exit connectivity survived (docking bay has a working north exit).
            dock = by_name["Docking Bay Alpha-1"]
            north = next(o for o in dock.contents
                        if o.has_tag("exit") and o.name == "north")
            assert north.db.get("destination_obj") or north.db.get("destination")
        finally:
            sim.close()

    async def test_npc_softcode_and_behaviors_survive(self):
        sim = Simulator()
        try:
            created = await self._import(sim)
            by_name = {o.name: o for o in created}
            # Bartender keeps its $-command softcode.
            assert by_name["Zeke the Bartender"].db.get("cmd_greet")
            # The guard keeps its Guard behavior.
            guard = by_name["Security Officer Chen"]
            assert any(type(b).__name__ == "GuardBehavior"
                       for b in guard.get_behaviors())
        finally:
            sim.close()

    async def test_nexagen_zone_present(self):
        sim = Simulator()
        try:
            created = await self._import(sim)
            assert any(o.has_tag("zone:nexagen") for o in created)
        finally:
            sim.close()

    async def test_softcode_absolute_id_references_resolve(self):
        # The blackout panel's softcode references rooms by absolute id;
        # preserve_ids keeps them valid (a fresh-id clone would break them).
        sim = Simulator()
        try:
            await self._import(sim)
            assert sim.store.get_cached("nexagen_floor46") is not None
            assert sim.store.get_cached("nexagen_stair_high") is not None
        finally:
            sim.close()


class TestSpaceships:
    """Tests for spaceship system."""

    @pytest.mark.asyncio
    async def test_ship_creation(self):
        """Ships should be created from templates."""
        from realm.examples.spacegame.ships import ShipClass, Spaceship

        repo = MemoryStore()
        ship = await Spaceship.create(repo, ShipClass.FIGHTER, "Red Five")

        assert ship.obj.name == "Red Five"
        assert ship.obj.has_tag("ship")
        assert ship.obj.has_tag("ship_class:fighter")
        assert ship.hull > 0
        assert ship.max_shields > 0

    @pytest.mark.asyncio
    async def test_ship_damage(self):
        """Ships should handle damage correctly."""
        from realm.examples.spacegame.ships import ShipClass, Spaceship

        repo = MemoryStore()
        ship = await Spaceship.create(repo, ShipClass.CORVETTE, "Test Ship")

        initial_shields = ship.shields
        initial_hull = ship.hull
        armor = ship.armor

        # Damage absorbed by shields first
        change = ship.take_damage(10)
        assert change.pool == "shields" and change.applied == 10
        assert change.spilled is None
        assert ship.shields == initial_shields - 10

        # Deplete shields: the rest spills into the hull, less its armor
        ship.obj.db.shields = 5
        change = ship.take_damage(20)
        assert change.applied == 5
        hull = change.spilled
        assert hull.pool == "hull" and hull.soaked == min(armor, 15)
        expected_hull_damage = max(0, 15 - armor)
        assert hull.applied == expected_hull_damage
        assert ship.hull == initial_hull - expected_hull_damage

    @pytest.mark.asyncio
    async def test_stock_damage_reaches_a_ship(self):
        """A ship's health is pools, so softcode damage() (and every other
        stock source of harm) needs no ship code; a spent hull fires its
        ON_SPENT and leaves the wreck in place (when_spent none)."""
        from realm.examples.spacegame.ships import ShipClass, Spaceship
        from realm.testing import Simulator

        with Simulator() as sim:
            bay = sim.room("Docking Bay")
            ship = await Spaceship.create(sim.store, ShipClass.FIGHTER, "Red Five")
            ship.obj.location = bay
            ship.obj.db.on_spent = "if adata('pool') == 'hull': set_attr(me, 'wrecked', 1)"
            mine = sim.obj("mine", location=bay)
            await sim.eval(mine, "damage(get('Red Five'), 30)")
            assert ship.shields == 0 and ship.hull == 30 - (10 - 2)
            assert ship.is_operational
            await sim.eval(mine, "damage(get('Red Five'), 99)")
            assert ship.hull == 0 and not ship.is_operational
            assert ship.obj.db.wrecked == 1
            assert ship.obj.location is bay
            assert "hp" not in ship.obj.db.all()

    @pytest.mark.asyncio
    async def test_ship_repair(self):
        """Ships should be repairable."""
        from realm.examples.spacegame.ships import ShipClass, Spaceship

        repo = MemoryStore()
        ship = await Spaceship.create(repo, ShipClass.FREIGHTER, "Cargo One")

        ship.obj.db.hull = 30  # Damaged
        ship.obj.db.shields = 0

        hull_repaired = ship.repair_hull(20)
        assert hull_repaired == 20
        assert ship.hull == 50

        shields_recharged = ship.recharge_shields(50)
        assert shields_recharged <= ship.max_shields

    @pytest.mark.asyncio
    async def test_ship_status(self):
        """Ship status should reflect current state."""
        from realm.examples.spacegame.ships import ShipClass, Spaceship

        repo = MemoryStore()
        ship = await Spaceship.create(repo, ShipClass.CRUISER, "Battlestar")

        status = ship.get_status_string()
        assert "Battlestar" in status
        assert "Hull:" in status
        assert "Shields:" in status
        assert "Operational" in status  # Full HP


class TestCombatIntegration:
    """Integration tests for combat with space game."""

    @pytest.mark.asyncio
    async def test_gurps_combat_setup(self):
        """GURPS combat system should be configurable."""
        from realm.std.combat.system import create_combat_system

        combat = create_combat_system(
            ruleset_name="gurps",
            allow_active_defense=True,
        )

        assert combat.ruleset.name == "GURPS 3d6"
