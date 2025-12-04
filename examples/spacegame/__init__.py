"""
REALM Space Game - A GURPS-based space exploration game.

This is a reference implementation demonstrating REALM's features:
- GURPS 3d6 combat ruleset
- Softcode scripting on objects
- Event-driven behaviors
- Permission system
- OLC commands for building
"""

from examples.spacegame.world import create_world
from examples.spacegame.characters import SpaceCharacter
from examples.spacegame.ships import Spaceship
from examples.spacegame.equipment import create_equipment_prototypes

__all__ = [
    'create_world',
    'SpaceCharacter',
    'Spaceship',
    'create_equipment_prototypes',
]
