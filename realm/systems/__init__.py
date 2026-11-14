"""
The built-in game systems: GURPS, D20, Merc.

A game system is a ``GameSystem`` subclass (``realm.std.rules.system``);
``GAME_SYSTEM`` in config.py names one by dotted import path
(``"realm.systems.GurpsSystem"``, ``"rules.GameRules"``), and the ``rules``
feature resolves it.
"""

from realm.systems.d20 import D20System
from realm.systems.gurps import GurpsSystem
from realm.systems.merc import MercSystem

__all__ = ["GurpsSystem", "D20System", "MercSystem"]
