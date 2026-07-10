"""
Tests for the space game example.
"""


import pytest

from realm.core.objects import GameObject
from realm.persistence.repository import GameObjectRepository


class TestSpaceCharacters:
    """Tests for space game character system."""

    def test_character_roles_defined(self):
        """All character roles should be defined."""
        from examples.spacegame.characters import TEMPLATES, CharacterRole

        for role in CharacterRole:
            assert role in TEMPLATES
            template = TEMPLATES[role]
            assert template.role == role
            assert template.description

    def test_character_creation(self):
        """Character creation should apply template stats."""
        from examples.spacegame.characters import CharacterRole, SpaceCharacter

        obj = GameObject(id="test_player", name="Test")
        SpaceCharacter.create(obj, CharacterRole.MARINE, "Test Marine")

        assert obj.name == "Test Marine"
        assert obj.has_tag("player")
        assert obj.has_tag("role:marine")

        # Marine template has higher strength/health
        assert obj.db.strength == 12
        assert obj.db.health == 12
        assert obj.db.get("skill_melee") == 13
        assert obj.db.get("skill_ranged") == 14

    def test_character_stats(self):
        """SpaceCharacter should expose stats correctly."""
        from examples.spacegame.characters import CharacterRole, SpaceCharacter

        obj = GameObject(id="test_player", name="Test")
        char = SpaceCharacter.create(obj, CharacterRole.PILOT)

        assert char.strength == 10  # Pilot default
        assert char.dexterity == 12  # Pilot bonus
        assert char.hp == char.max_hp
        assert char.credits == 500  # Starting credits

    def test_character_damage_and_healing(self):
        """Character should track damage and healing."""
        from examples.spacegame.characters import CharacterRole, SpaceCharacter

        obj = GameObject(id="test_player", name="Test")
        char = SpaceCharacter.create(obj, CharacterRole.MARINE)

        initial_hp = char.hp
        damage = char.take_damage(5)
        assert damage == 5
        assert char.hp == initial_hp - 5
        assert char.is_alive()

        healed = char.heal(3)
        assert healed == 3
        assert char.hp == initial_hp - 2

    def test_character_credits(self):
        """Character credits should be modifiable."""
        from examples.spacegame.characters import CharacterRole, SpaceCharacter

        obj = GameObject(id="test_player", name="Test")
        char = SpaceCharacter.create(obj, CharacterRole.MERCHANT)

        initial = char.credits
        new_balance = char.modify_credits(100)
        assert new_balance == initial + 100
        assert char.credits == new_balance

        # Can't go negative
        final = char.modify_credits(-99999)
        assert final == 0

    def test_character_status_string(self):
        """Status string should include key info."""
        from examples.spacegame.characters import CharacterRole, SpaceCharacter

        obj = GameObject(id="test_player", name="Test")
        char = SpaceCharacter.create(obj, CharacterRole.MEDIC)

        status = char.get_status_string()
        assert "Test" in status
        assert "medic" in status.lower()
        assert "HP:" in status
        assert "Credits:" in status


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

    @pytest.mark.asyncio
    async def test_character_combat(self):
        """Characters should be able to engage in combat."""
        from examples.spacegame.characters import CharacterRole, SpaceCharacter
        from realm.combat.system import create_combat_system

        combat = create_combat_system(ruleset_name="gurps")

        # Create two characters
        player = GameObject(id="player", name="Hero")
        SpaceCharacter.create(player, CharacterRole.MARINE)

        enemy = GameObject(id="enemy", name="Villain")
        enemy.db.strength = 10
        enemy.db.dexterity = 10
        enemy.db.skill_melee = 10
        enemy.db.hp = 10
        enemy.db.max_hp = 10
        enemy.db.dodge = 8

        # Perform attack
        result = await combat.attack(player, enemy)

        # Should have roll results
        assert result.attack_result is not None
        assert result.attack_result.roll is not None

        # Messages generated
        assert "attacker_msg" in result.messages


class TestGameSetup:
    """Tests for full game setup."""

    @pytest.mark.asyncio
    async def test_setup_game(self):
        """Full game setup should initialize all systems."""
        from examples.spacegame.game import setup_game

        game = await setup_game()

        assert "repo" in game
        assert "combat" in game
        assert "world" in game
        assert "equipment" in game
        assert "ships" in game

        # Combat should be GURPS
        assert game["combat"].ruleset.name == "GURPS 3d6"

    @pytest.mark.asyncio
    async def test_create_player(self):
        """Player creation should work with game world."""
        from examples.spacegame.game import create_player, setup_game

        game = await setup_game()
        docking_bay = game["world"]["docking_bay"]

        player = await create_player(
            game["repo"],
            "Test Player",
            "scout",
            docking_bay,
        )

        assert player.name == "Test Player"
        assert player.has_tag("role:scout")
        assert player.location == docking_bay
        assert player in docking_bay.contents
