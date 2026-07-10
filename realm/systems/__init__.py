"""
Game systems: swappable rules packages (GURPS, D20, yours).

``GAME_SYSTEM`` in config.py is a dotted import path to a GameSystem
subclass (e.g. ``"rules.GameRules"`` or ``"realm.systems.GurpsSystem"``),
resolved by :func:`resolve_game_system`.
"""

from realm.systems.base import (
    ChargenStep,
    ChoiceStep,
    GameSystem,
    get_game_system,
    resolve_game_system,
    set_game_system,
)
from realm.systems.d20 import D20System
from realm.systems.gurps import GurpsSystem

__all__ = [
    "ChargenStep",
    "ChoiceStep",
    "GameSystem",
    "GurpsSystem",
    "D20System",
    "get_game_system",
    "resolve_game_system",
    "set_game_system",
]
