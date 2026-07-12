"""
Tests for the space game example.
"""

import json
from pathlib import Path

import pytest

import realm.behaviors  # noqa: F401  (register the behavior kit for from_dict)
import realm.combat.behaviors  # noqa: F401
from realm.core.objects import GameObject
from realm.persistence.repository import GameObjectRepository
from realm.persistence.worldio import import_objects
from realm.testing import Simulator

_STATION = (Path(__file__).resolve().parent.parent
            / "examples" / "spacegame" / "data" / "areas" / "station.json")


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
        from examples.spacegame.ships import ShipClass, Spaceship

        repo = GameObjectRepository()
        ship = await Spaceship.create(repo, ShipClass.FIGHTER, "Red Five")

        assert ship.obj.name == "Red Five"
        assert ship.obj.has_tag("ship")
        assert ship.obj.has_tag("ship_class:fighter")
        assert ship.hull > 0
        assert ship.max_shields > 0

    @pytest.mark.asyncio
    async def test_ship_damage(self):
        """Ships should handle damage correctly."""
        from examples.spacegame.ships import ShipClass, Spaceship

        repo = GameObjectRepository()
        ship = await Spaceship.create(repo, ShipClass.CORVETTE, "Test Ship")

        initial_shields = ship.shields
        initial_hull = ship.hull
        armor = ship.armor

        # Damage absorbed by shields first
        result = ship.take_damage(10)
        assert result["shields_damage"] == 10
        assert result["hull_damage"] == 0
        assert ship.shields == initial_shields - 10

        # Deplete shields
        ship.obj.db.shields = 5
        result = ship.take_damage(20)
        assert result["shields_damage"] == 5
        # Remaining 15 - armor goes to hull
        expected_hull_damage = max(0, 15 - armor)
        assert result["hull_damage"] == expected_hull_damage
        assert ship.hull == initial_hull - expected_hull_damage

    @pytest.mark.asyncio
    async def test_ship_repair(self):
        """Ships should be repairable."""
        from examples.spacegame.ships import ShipClass, Spaceship

        repo = GameObjectRepository()
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
        from examples.spacegame.ships import ShipClass, Spaceship

        repo = GameObjectRepository()
        ship = await Spaceship.create(repo, ShipClass.CRUISER, "Battlestar")

        status = ship.get_status_string()
        assert "Battlestar" in status
        assert "Hull:" in status
        assert "Shields:" in status
        assert "Operational" in status  # Full HP


class TestEquipment:
    """Tests for equipment system."""

    def test_weapon_templates(self):
        """Weapon templates should have combat stats."""
        from examples.spacegame.equipment import WEAPONS

        for weapon_id, template in WEAPONS.items():
            assert template.damage_dice
            assert template.damage_type
            assert template.skill_type in ("melee", "ranged")
            assert template.cost > 0

    def test_armor_templates(self):
        """Armor templates should have DR."""
        from examples.spacegame.equipment import ARMOR

        for armor_id, template in ARMOR.items():
            assert template.damage_resistance > 0
            assert template.cost > 0

    @pytest.mark.asyncio
    async def test_create_equipment_prototypes(self):
        """Should create all equipment prototypes."""
        from examples.spacegame.equipment import (
            ARMOR,
            GEAR,
            WEAPONS,
            create_equipment_prototypes,
        )

        repo = GameObjectRepository()
        prototypes = await create_equipment_prototypes(repo)

        # All templates should have prototypes
        all_templates = {**WEAPONS, **ARMOR, **GEAR}
        assert len(prototypes) == len(all_templates)

        for proto in prototypes.values():
            assert proto.has_tag("prototype")
            assert proto.has_tag("equipment")

    @pytest.mark.asyncio
    async def test_create_equipment_instance(self):
        """Should create equipment instances from templates."""
        from examples.spacegame.equipment import create_equipment_instance

        repo = GameObjectRepository()
        owner = GameObject(id="test_owner", name="Owner")

        weapon = await create_equipment_instance(repo, "sidearm", owner)
        assert weapon is not None
        assert weapon.name == "Laser Pistol"
        assert weapon.has_tag("equipment")
        assert not weapon.has_tag("prototype")
        assert weapon.owner == owner
        assert weapon in owner.contents

        # Invalid template
        invalid = await create_equipment_instance(repo, "nonexistent")
        assert invalid is None


class TestWorld:
    """Tests for world creation."""

    @pytest.mark.asyncio
    async def test_create_world(self):
        """World creation should build station."""
        from examples.spacegame.world import create_world

        repo = GameObjectRepository()
        world = await create_world(repo)

        # Key locations exist
        assert "docking_bay" in world
        assert "promenade" in world
        assert "cantina" in world
        assert "medbay" in world
        assert "command" in world

        # Rooms have proper tags
        assert world["docking_bay"].has_tag("room")
        assert world["docking_bay"].has_tag("zone:station_alpha")

    @pytest.mark.asyncio
    async def test_world_exits(self):
        """Rooms should have exits connecting them."""
        from examples.spacegame.world import create_world

        repo = GameObjectRepository()
        world = await create_world(repo)

        # Docking bay should have exit north to promenade
        docking = world["docking_bay"]
        exits = [o for o in docking.contents if o.has_tag("exit")]
        assert len(exits) > 0

        north_exit = None
        for e in exits:
            if e.name == "north":
                north_exit = e
                break

        assert north_exit is not None
        assert north_exit.db.destination == "room_promenade"

    @pytest.mark.asyncio
    async def test_world_npcs(self):
        """World should have NPCs with behaviors."""
        from examples.spacegame.world import create_world

        repo = GameObjectRepository()
        world = await create_world(repo)

        # Bartender in cantina
        assert "bartender" in world
        bartender = world["bartender"]
        assert bartender.has_tag("npc")
        assert bartender.has_tag("shopkeeper")
        assert bartender.location == world["cantina"]

        # Bartender should have GURPS stats
        assert bartender.db.get("strength") is not None
        assert bartender.db.get("skill_melee") is not None

        # Softcode commands
        assert bartender.db.get("cmd_greet") is not None


class TestCombatIntegration:
    """Integration tests for combat with space game."""

    @pytest.mark.asyncio
    async def test_gurps_combat_setup(self):
        """GURPS combat system should be configurable."""
        from realm.combat.system import create_combat_system

        combat = create_combat_system(
            ruleset_name="gurps",
            allow_active_defense=True,
        )

        assert combat.ruleset.name == "GURPS 3d6"
