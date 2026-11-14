"""
Combatant wrapper for combat system.

Provides a consistent interface for combat stats regardless of
the underlying GameObject structure. This allows rulesets to
work with any object that has the required attributes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from realm.core.pools import (
    PoolChange,
    damage_pool,
    harm,
    is_spent,
    mend,
    pool_get,
    pool_max,
    pool_percent,
    vital_pool,
)

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
        #: pool changes made through this wrapper, not yet settled
        self.changes: list[PoolChange] = []

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

    # --- Pools (realm.core.pools) ---

    @property
    def vital(self) -> int:
        """The vital pool's value (``hp`` for a character, ``hull`` for a
        ship whose shields take damage first); 0 without one."""
        name = vital_pool(self._obj)
        return 0 if name is None else int(pool_get(self._obj, name) or 0)

    @property
    def vital_max(self) -> int:
        """The vital pool's maximum, or its value when unbounded."""
        name = vital_pool(self._obj)
        if name is None:
            return 0
        maximum = pool_max(self._obj, name)
        return self.vital if maximum is None else maximum

    @property
    def vital_percent(self) -> float:
        """How much of the vital pool is left before it is spent, as a
        fraction (1.0 fresh, 0.0 spent; an up pool counts what remains below
        its max). An unbounded pool with something in it is 1.0."""
        name = vital_pool(self._obj)
        if name is None:
            return 0.0
        percent = pool_percent(self._obj, name)
        if percent is None:
            return 1.0 if self.vital > 0 else 0.0
        return percent / 100

    @property
    def vital_spent(self) -> bool:
        """The vital pool is spent: out of the fight, and (through combat's
        observer on ``pool:on_spent``) down. To fall later, a game lowers
        the pool's ``spent_at``."""
        return is_spent(self._obj, vital_pool(self._obj))

    def take_damage(self, amount: int, *, soak: bool = False) -> int:
        """Harm the damage pool (spilling down its overflow chain). The
        change waits in ``changes`` until the caller settles it. Returns the
        total the pools took."""
        name = damage_pool(self._obj)
        if amount <= 0 or name is None:
            return 0
        change = harm(self._obj, name, amount, soak=soak)
        self.changes.append(change)
        return change.total_applied

    def heal(self, amount: int) -> int:
        """Mend the damage pool. Returns the amount mended."""
        name = damage_pool(self._obj)
        if amount <= 0 or name is None:
            return 0
        change = mend(self._obj, name, amount)
        self.changes.append(change)
        return change.applied

    def drain_changes(self) -> list[PoolChange]:
        """The unsettled pool changes, oldest first; clears them."""
        out, self.changes = self.changes, []
        return out

    # --- Equipment ---

    # --- Utility ---

    def __repr__(self) -> str:
        return (f"<Combatant {self.name} vital:{self.vital}/{self.vital_max} "
                f"state:{self.state.name}>")

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
