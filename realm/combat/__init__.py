"""
Combat system for REALM.

Provides an abstract combat framework with swappable rulesets:
- Ruleset base class defines the interface for combat resolution
- Built-in rulesets: D20 (D&D style), GURPS (3d6 roll-under)
- Combatant wrapper provides consistent combat state
- Combat behaviors for NPCs (aggressive, defensive, etc.)

Usage:
    from realm.combat import CombatSystem, D20Ruleset

    combat = CombatSystem(ruleset=D20Ruleset())
    result = await combat.attack(attacker, defender)
"""

from realm.combat.ruleset import (
    Ruleset,
    RollResult,
    AttackResult,
    DamageResult,
    DamageType,
)
from realm.combat.combatant import Combatant, CombatState
from realm.combat.system import CombatSystem, get_combat_system, set_combat_system
from realm.combat.rulesets.d20 import D20Ruleset
from realm.combat.rulesets.gurps import GURPSRuleset

__all__ = [
    # Core
    "Ruleset",
    "RollResult",
    "AttackResult",
    "DamageResult",
    "DamageType",
    "Combatant",
    "CombatState",
    "CombatSystem",
    "get_combat_system",
    "set_combat_system",
    # Rulesets
    "D20Ruleset",
    "GURPSRuleset",
]
