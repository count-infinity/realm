"""
Game systems: swappable rules packages (GURPS, D20, yours).

Importing this package registers the built-in systems.
"""

from realm.systems.base import (
    ChargenStep,
    ChoiceStep,
    GameSystem,
    GameSystemRegistry,
    get_game_system,
    set_game_system,
)
from realm.systems.d20 import D20System
from realm.systems.gurps import GurpsSystem

__all__ = [
    "ChargenStep",
    "ChoiceStep",
    "GameSystem",
    "GameSystemRegistry",
    "GurpsSystem",
    "D20System",
    "get_game_system",
    "set_game_system",
]
