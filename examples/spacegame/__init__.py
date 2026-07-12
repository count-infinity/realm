"""
REALM Space Game - A GURPS-based space exploration game.

This is a reference implementation demonstrating REALM's features:
- GURPS 3d6 combat ruleset
- Softcode scripting on objects
- Event-driven behaviors
- Permission system
- OLC commands for building
"""

from examples.spacegame.equipment import create_equipment_prototypes
from examples.spacegame.ships import Spaceship
from examples.spacegame.world import create_world

# Character classes/skills are DATA now — the built-in ``gurps-scifi``
# content pack (realm/packs/gurps-scifi), not a bespoke SpaceCharacter
# class. Import it with ``realm pack import gurps-scifi`` or ``@pack``.

__all__ = [
    'create_world',
    'Spaceship',
    'create_equipment_prototypes',
]
