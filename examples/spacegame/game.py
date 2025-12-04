"""
Space Game main entry point.

Sets up and runs the GURPS-based space exploration game.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


async def setup_game() -> dict[str, any]:
    """
    Initialize the space game.

    Returns a dict with key game components:
    - 'repo': GameObjectRepository
    - 'combat': CombatSystem (GURPS)
    - 'event_bus': EventBus
    - 'world': Dict of key world objects
    """
    from realm.core.events import EventBus
    from realm.persistence.repository import GameObjectRepository
    from realm.combat.system import create_combat_system, set_combat_system

    from examples.spacegame.world import create_world
    from examples.spacegame.equipment import create_equipment_prototypes
    from examples.spacegame.ships import create_ship_prototypes

    # Initialize event bus
    event_bus = EventBus()

    # Initialize repository (in-memory for demo)
    repo = GameObjectRepository()

    # Create GURPS combat system
    combat = create_combat_system(
        ruleset_name="gurps",
        event_bus=event_bus,
        allow_active_defense=True,
    )
    set_combat_system(combat)

    # Create the world
    logger.info("Creating game world...")
    world = await create_world(repo)

    # Create equipment prototypes
    logger.info("Creating equipment prototypes...")
    equipment = await create_equipment_prototypes(repo)

    # Create ship prototypes
    logger.info("Creating ship prototypes...")
    ships = await create_ship_prototypes(repo)

    logger.info("Space game initialized!")

    return {
        "repo": repo,
        "combat": combat,
        "event_bus": event_bus,
        "world": world,
        "equipment": equipment,
        "ships": ships,
    }


async def create_player(
    repo,
    name: str,
    role_name: str = "pilot",
    location: GameObject | None = None,
) -> GameObject:
    """
    Create a new player character.

    Args:
        repo: GameObjectRepository
        name: Player name
        role_name: Character role (pilot, marine, engineer, medic, merchant, scout)
        location: Starting location (defaults to docking bay)

    Returns:
        The player's GameObject
    """
    from realm.core.objects import GameObject
    from examples.spacegame.characters import SpaceCharacter, CharacterRole

    # Map role name to enum
    role_map = {
        "pilot": CharacterRole.PILOT,
        "marine": CharacterRole.MARINE,
        "engineer": CharacterRole.ENGINEER,
        "medic": CharacterRole.MEDIC,
        "merchant": CharacterRole.MERCHANT,
        "scout": CharacterRole.SCOUT,
    }

    role = role_map.get(role_name.lower(), CharacterRole.PILOT)

    # Create player object
    player_id = f"player_{name.lower().replace(' ', '_')}"
    player = GameObject(id=player_id, name=name)

    # Initialize as space character
    SpaceCharacter.create(player, role, name)

    # Set location
    if location:
        player.location = location
        location.contents.append(player)

    await repo.save(player)
    return player


async def demo_combat(game_data: dict) -> None:
    """
    Run a demo combat encounter.

    Shows off the GURPS combat system.
    """
    from examples.spacegame.characters import SpaceCharacter
    from realm.combat.combatant import get_combatant

    repo = game_data["repo"]
    combat = game_data["combat"]
    world = game_data["world"]

    # Create a test player
    docking_bay = world["docking_bay"]
    player = await create_player(repo, "Test Pilot", "marine", docking_bay)

    # Create a hostile NPC
    from realm.core.objects import GameObject

    pirate = GameObject(id="npc_pirate", name="Space Pirate")
    pirate.add_tag("npc")
    pirate.add_tag("hostile")
    pirate.location = docking_bay
    docking_bay.contents.append(pirate)

    # GURPS stats for pirate
    pirate.db.strength = 11
    pirate.db.dexterity = 12
    pirate.db.intelligence = 9
    pirate.db.health = 11
    pirate.db.skill_melee = 12
    pirate.db.skill_ranged = 11
    pirate.db.hp = 11
    pirate.db.max_hp = 11
    pirate.db.damage_resistance = 1
    pirate.db.dodge = 9

    await repo.save(pirate)

    print("=" * 60)
    print("COMBAT DEMO: Marine vs Space Pirate")
    print("=" * 60)
    print()

    player_combatant = get_combatant(player)
    pirate_combatant = get_combatant(pirate)

    print(f"Player: {player.name}")
    print(f"  HP: {player_combatant.hp}/{player_combatant.max_hp}")
    print(f"  Skill: {player.db.get('skill_melee', 10)}")
    print()
    print(f"Enemy: {pirate.name}")
    print(f"  HP: {pirate_combatant.hp}/{pirate_combatant.max_hp}")
    print(f"  Skill: {pirate.db.get('skill_melee', 10)}")
    print()

    # Combat rounds
    round_num = 0
    while player_combatant.is_alive and pirate_combatant.is_alive:
        round_num += 1
        print(f"--- Round {round_num} ---")

        # Player attacks
        result = await combat.attack(player, pirate)
        if result.success:
            damage = result.damage_result.total if result.damage_result else 0
            print(f"{player.name} hits for {damage} damage!")
            if result.target_defeated:
                print(f"{pirate.name} is defeated!")
                break
        else:
            roll_desc = result.attack_result.roll.description if result.attack_result else "missed"
            print(f"{player.name} misses! ({roll_desc})")

        if not pirate_combatant.is_alive:
            break

        # Pirate attacks back
        result = await combat.attack(pirate, player)
        if result.success:
            damage = result.damage_result.total if result.damage_result else 0
            print(f"{pirate.name} hits for {damage} damage!")
            if result.target_defeated:
                print(f"{player.name} is defeated!")
                break
        else:
            roll_desc = result.attack_result.roll.description if result.attack_result else "missed"
            print(f"{pirate.name} misses! ({roll_desc})")

        # Status update
        print(f"HP - {player.name}: {player_combatant.hp}, {pirate.name}: {pirate_combatant.hp}")
        print()

        # Safety limit
        if round_num >= 20:
            print("Combat timeout!")
            break

    print()
    print("Combat ended!")


async def main():
    """Main entry point for the space game demo."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("  REALM Space Game - GURPS Combat Demo")
    print("=" * 60)
    print()

    # Setup game
    game_data = await setup_game()

    # Run combat demo
    await demo_combat(game_data)


if __name__ == "__main__":
    asyncio.run(main())
