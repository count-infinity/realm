"""
Combatant wrapper for combat system.

Provides a consistent interface for combat stats regardless of
the underlying GameObject structure. This allows rulesets to
work with any object that has the required attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class CombatState(Enum):
    """Combat state for a combatant."""

    IDLE = auto()  # Not in combat
    COMBAT = auto()  # In active combat
    FLEEING = auto()  # Trying to escape
    DEFEATED = auto()  # Knocked out/dead
    DEAD = auto()  # Permanently dead


@dataclass
class Combatant:
    """
    Wrapper around a GameObject for combat purposes.

    Provides a consistent interface for:
    - Combat stats (HP, attack, defense, etc.)
    - Status effects
    - Combat state tracking
    - Stat modifiers from equipment/buffs

    The actual stat names and meanings depend on the ruleset.
    This class just provides the access mechanism.
    """

    def __init__(self, obj: GameObject):
        self._obj = obj
        self._state = CombatState.IDLE
        self._combat_modifiers: dict[str, int] = {}
        self._target: Combatant | None = None

    @property
    def obj(self) -> GameObject:
        """The underlying GameObject."""
        return self._obj

    @property
    def id(self) -> str:
        """Object ID."""
        return self._obj.id

    @property
    def name(self) -> str:
        """Display name."""
        return self._obj.name

    @property
    def state(self) -> CombatState:
        """Current combat state."""
        return self._state

    @state.setter
    def state(self, value: CombatState) -> None:
        self._state = value

    @property
    def target(self) -> Combatant | None:
        """Current combat target."""
        return self._target

    @target.setter
    def target(self, value: Combatant | None) -> None:
        self._target = value

    @property
    def is_in_combat(self) -> bool:
        """Check if actively in combat."""
        return self._state in (CombatState.COMBAT, CombatState.FLEEING)

    @property
    def is_alive(self) -> bool:
        """Check if combatant is still alive."""
        return self._state not in (CombatState.DEFEATED, CombatState.DEAD)

    # --- Stat Access ---

    def get_stat(self, name: str, default: int = 0) -> int:
        """
        Get a combat stat value.

        Checks in order:
        1. Temporary combat modifiers
        2. Object's db attributes
        3. Default value

        Args:
            name: Stat name (e.g., 'strength', 'hp', 'armor_class')
            default: Default value if not found

        Returns:
            The stat value
        """
        # Check for temporary modifier
        if name in self._combat_modifiers:
            base = self._obj.db.get(name, default)
            return base + self._combat_modifiers[name]

        # Check object attributes
        value = self._obj.db.get(name, None)
        if value is not None:
            return int(value)

        return default

    def set_stat(self, name: str, value: int) -> None:
        """
        Set a combat stat value on the underlying object.

        Args:
            name: Stat name
            value: New value
        """
        self._obj.db.set(name, value)

    def modify_stat(self, name: str, delta: int) -> int:
        """
        Modify a stat by a delta.

        Args:
            name: Stat name
            delta: Amount to add (negative to subtract)

        Returns:
            New stat value
        """
        current = self.get_stat(name, 0)
        new_value = current + delta
        self.set_stat(name, new_value)
        return new_value

    def add_modifier(self, stat: str, amount: int, source: str = "") -> None:
        """
        Add a temporary modifier to a stat.

        Args:
            stat: Stat name to modify
            amount: Modifier amount
            source: What's providing this modifier (for tracking)
        """
        current = self._combat_modifiers.get(stat, 0)
        self._combat_modifiers[stat] = current + amount

    def remove_modifier(self, stat: str, amount: int) -> None:
        """Remove a temporary modifier."""
        if stat in self._combat_modifiers:
            self._combat_modifiers[stat] -= amount
            if self._combat_modifiers[stat] == 0:
                del self._combat_modifiers[stat]

    def clear_modifiers(self) -> None:
        """Clear all temporary modifiers."""
        self._combat_modifiers.clear()

    # --- HP Management ---

    @property
    def hp(self) -> int:
        """Current hit points."""
        return self.get_stat('hp', 0)

    @hp.setter
    def hp(self, value: int) -> None:
        self.set_stat('hp', value)

    @property
    def max_hp(self) -> int:
        """Maximum hit points."""
        return self.get_stat('max_hp', self.get_stat('hp', 10))

    @property
    def hp_percent(self) -> float:
        """HP as a percentage of max."""
        max_hp = self.max_hp
        if max_hp <= 0:
            return 0.0
        return self.hp / max_hp

    def take_damage(self, amount: int) -> int:
        """
        Take damage, reducing HP.

        Args:
            amount: Damage to take (positive)

        Returns:
            Actual damage taken
        """
        if amount <= 0:
            return 0

        old_hp = self.hp
        new_hp = max(0, old_hp - amount)
        self.hp = new_hp

        actual_damage = old_hp - new_hp
        return actual_damage

    def heal(self, amount: int) -> int:
        """
        Heal, restoring HP.

        Args:
            amount: Amount to heal (positive)

        Returns:
            Actual amount healed
        """
        if amount <= 0:
            return 0

        old_hp = self.hp
        max_hp = self.max_hp
        new_hp = min(max_hp, old_hp + amount)
        self.hp = new_hp

        actual_healing = new_hp - old_hp
        return actual_healing

    # --- Resistances/Vulnerabilities ---

    def get_resistance(self, damage_type: str) -> float:
        """
        Get resistance multiplier for a damage type.

        Returns:
            Multiplier (0.5 = half damage, 2.0 = double damage, 0 = immune)
        """
        # Check for immunity
        immunities = self._obj.db.get('immunities', [])
        if damage_type in immunities:
            return 0.0

        # Check for resistance
        resistances = self._obj.db.get('resistances', [])
        if damage_type in resistances:
            return 0.5

        # Check for vulnerability
        vulnerabilities = self._obj.db.get('vulnerabilities', [])
        if damage_type in vulnerabilities:
            return 2.0

        return 1.0

    # --- Equipment ---

    def get_weapon(self) -> Any | None:
        """Get the equipped weapon."""
        weapon_id = self._obj.db.get('equipped_weapon')
        if weapon_id:
            # Look for weapon in inventory
            for item in self._obj.contents:
                if item.id == weapon_id:
                    return item
        return None

    def get_armor(self) -> Any | None:
        """Get the equipped armor."""
        armor_id = self._obj.db.get('equipped_armor')
        if armor_id:
            for item in self._obj.contents:
                if item.id == armor_id:
                    return item
        return None

    # --- Utility ---

    def __repr__(self) -> str:
        return f"<Combatant {self.name} HP:{self.hp}/{self.max_hp} state:{self.state.name}>"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Combatant):
            return self._obj.id == other._obj.id
        return False

    def __hash__(self) -> int:
        return hash(self._obj.id)


# Cache of combatant wrappers
_combatant_cache: dict[str, Combatant] = {}


def get_combatant(obj: GameObject) -> Combatant:
    """
    Get or create a Combatant wrapper for a GameObject.

    Caches combatants by object ID for consistency.
    """
    if obj.id not in _combatant_cache:
        _combatant_cache[obj.id] = Combatant(obj)
    return _combatant_cache[obj.id]


def clear_combatant_cache() -> None:
    """Clear the combatant cache (for testing/cleanup)."""
    _combatant_cache.clear()
