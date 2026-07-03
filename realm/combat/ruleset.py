"""
Abstract ruleset interface for combat systems.

Rulesets define HOW combat is resolved:
- How attacks are rolled (d20+mod vs AC, 3d6 roll-under skill, etc.)
- How damage is calculated
- How defense/armor works
- What stats are used

This allows the same combat framework to work with D&D, GURPS,
or custom systems by swapping the ruleset.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.combat.combatant import Combatant


class DamageType(str, Enum):
    """Standard damage types that rulesets can use."""

    # Physical
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"

    # Elemental
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    ACID = "acid"

    # Other
    POISON = "poison"
    PSYCHIC = "psychic"
    RADIANT = "radiant"
    NECROTIC = "necrotic"
    FORCE = "force"

    # Generic
    PHYSICAL = "physical"
    MAGICAL = "magical"
    TRUE = "true"  # Ignores all resistance


@dataclass
class RollResult:
    """
    Result of a dice roll.

    Captures the roll details for display and logging.
    """

    total: int  # Final result after modifiers
    dice: list[int]  # Individual die results
    modifier: int = 0  # Applied modifier
    target: int | None = None  # Target number (if any)
    success: bool = True  # Did the roll succeed?
    critical: bool = False  # Critical success/failure?
    fumble: bool = False  # Critical failure?
    description: str = ""  # Human-readable description

    def __str__(self) -> str:
        if self.description:
            return self.description
        dice_str = "+".join(str(d) for d in self.dice)
        if self.modifier:
            sign = "+" if self.modifier > 0 else ""
            return f"[{dice_str}]{sign}{self.modifier} = {self.total}"
        return f"[{dice_str}] = {self.total}"


@dataclass
class AttackResult:
    """
    Result of an attack roll.

    Contains all information about whether an attack hits.
    """

    hit: bool  # Did the attack connect?
    roll: RollResult  # The attack roll details
    critical_hit: bool = False  # Critical hit?
    critical_miss: bool = False  # Critical miss/fumble?
    margin: int = 0  # How much did we beat/miss the target by?
    effects: list[str] = field(default_factory=list)  # Special effects triggered

    @property
    def success(self) -> bool:
        return self.hit


@dataclass
class DamageResult:
    """
    Result of damage calculation.

    Contains damage amounts by type after resistance/vulnerability.
    """

    total: int  # Total damage dealt
    damage_by_type: dict[DamageType, int] = field(default_factory=dict)
    roll: RollResult | None = None  # Damage roll details
    resisted: int = 0  # Amount resisted/absorbed
    effects: list[str] = field(default_factory=list)  # Effects from damage


@dataclass
class DefenseResult:
    """Result of a defense/saving throw."""

    success: bool
    roll: RollResult
    damage_reduced: int = 0
    effects: list[str] = field(default_factory=list)


class Ruleset(ABC):
    """
    Abstract base class for combat rulesets.

    Implement this class to define how combat works in your game.
    Each method corresponds to a step in combat resolution.

    Example rulesets:
    - D20Ruleset: D&D-style d20+mod vs AC
    - GURPSRuleset: 3d6 roll-under skill
    - PercentileRuleset: d100 roll-under
    """

    # Ruleset metadata
    name: str = "Base Ruleset"
    description: str = "Abstract base ruleset"
    version: str = "1.0"

    # Stat names this ruleset uses (for validation)
    required_stats: list[str] = []

    # --- Core Resolution Methods ---

    @abstractmethod
    def roll_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
        weapon: Any | None = None,
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        """
        Roll to determine if an attack hits.

        Args:
            attacker: The attacking combatant
            defender: The defending combatant
            weapon: Optional weapon being used
            modifiers: Situational modifiers (flanking, cover, etc.)

        Returns:
            AttackResult with hit/miss and roll details
        """
        pass

    @abstractmethod
    def roll_damage(
        self,
        attacker: Combatant,
        defender: Combatant,
        attack_result: AttackResult,
        weapon: Any | None = None,
    ) -> DamageResult:
        """
        Roll damage for a successful attack.

        Args:
            attacker: The attacking combatant
            defender: The defending combatant
            attack_result: The attack roll result (for crits, etc.)
            weapon: Optional weapon being used

        Returns:
            DamageResult with damage amounts
        """
        pass

    @abstractmethod
    def apply_damage(
        self,
        target: Combatant,
        damage: DamageResult,
    ) -> int:
        """
        Apply damage to a combatant.

        Handles resistances, vulnerabilities, and HP reduction.

        Args:
            target: The combatant taking damage
            damage: The damage to apply

        Returns:
            Actual damage dealt after resistances
        """
        pass

    @abstractmethod
    def is_defeated(self, combatant: Combatant) -> bool:
        """
        Check if a combatant is defeated (dead, unconscious, etc.).

        Args:
            combatant: The combatant to check

        Returns:
            True if combatant can no longer fight
        """
        pass

    # --- Optional Methods (override as needed) ---

    def roll_initiative(
        self,
        combatant: Combatant,
        modifiers: dict[str, int] | None = None,
    ) -> RollResult:
        """
        Roll initiative for combat order.

        Default: Random 1-20. Override for system-specific initiative.
        """
        import random
        roll = random.randint(1, 20)
        return RollResult(
            total=roll,
            dice=[roll],
            description=f"Initiative: {roll}",
        )

    def roll_defense(
        self,
        defender: Combatant,
        attack_type: str = "physical",
        modifiers: dict[str, int] | None = None,
    ) -> DefenseResult:
        """
        Roll an active defense (dodge, parry, block).

        Default: No active defense. Override for systems that use them.
        """
        return DefenseResult(
            success=False,
            roll=RollResult(total=0, dice=[]),
        )

    def roll_saving_throw(
        self,
        combatant: Combatant,
        save_type: str,
        difficulty: int,
        modifiers: dict[str, int] | None = None,
    ) -> DefenseResult:
        """
        Roll a saving throw against an effect.

        Default: 50% chance. Override for system-specific saves.
        """
        import random
        roll = random.randint(1, 20)
        success = roll >= 10
        return DefenseResult(
            success=success,
            roll=RollResult(
                total=roll,
                dice=[roll],
                target=10,
                success=success,
            ),
        )

    def calculate_healing(
        self,
        healer: Combatant | None,
        target: Combatant,
        base_amount: int,
    ) -> int:
        """
        Calculate healing amount.

        Default: Return base amount. Override for healing modifiers.
        """
        return base_amount

    def get_attack_range(
        self,
        attacker: Combatant,
        weapon: Any | None = None,
    ) -> int:
        """
        Get the attack range for a weapon/ability.

        Default: 1 (melee). Override for ranged calculations.
        """
        if weapon:
            return getattr(weapon, 'range', 1)
        return 1

    # --- Utility Methods ---

    def roll_dice(self, num: int, sides: int, modifier: int = 0) -> RollResult:
        """
        Roll dice with a modifier.

        Args:
            num: Number of dice
            sides: Sides per die
            modifier: Added to total

        Returns:
            RollResult with individual dice and total
        """
        import random
        dice = [random.randint(1, sides) for _ in range(num)]
        total = sum(dice) + modifier
        return RollResult(
            total=total,
            dice=dice,
            modifier=modifier,
        )

    def get_stat(
        self,
        combatant: Combatant,
        stat_name: str,
        default: int = 0,
    ) -> int:
        """
        Get a stat value from a combatant.

        Args:
            combatant: The combatant
            stat_name: Name of the stat
            default: Default if stat not found

        Returns:
            The stat value
        """
        return combatant.get_stat(stat_name, default)

    def get_modifier(
        self,
        combatant: Combatant,
        stat_name: str,
    ) -> int:
        """
        Get a modifier derived from a stat.

        Default: (stat - 10) // 2 (D&D style)
        Override for different modifier calculations.
        """
        stat = self.get_stat(combatant, stat_name, 10)
        return (stat - 10) // 2

    def format_attack_message(
        self,
        attacker: Combatant,
        defender: Combatant,
        attack_result: AttackResult,
        damage_result: DamageResult | None = None,
    ) -> dict[str, str]:
        """
        Format combat messages for display.

        Returns dict with keys:
        - attacker_msg: What the attacker sees
        - defender_msg: What the defender sees
        - others_msg: What bystanders see

        Override for custom message formatting.
        """
        attacker_name = attacker.name
        defender_name = defender.name

        if attack_result.hit:
            if damage_result:
                attacker_msg = f"You hit {defender_name} for {damage_result.total} damage!"
                defender_msg = f"{attacker_name} hits you for {damage_result.total} damage!"
                others_msg = f"{attacker_name} hits {defender_name}!"
            else:
                attacker_msg = f"You hit {defender_name}!"
                defender_msg = f"{attacker_name} hits you!"
                others_msg = f"{attacker_name} hits {defender_name}!"

            if attack_result.critical_hit:
                attacker_msg = "CRITICAL! " + attacker_msg
                defender_msg = "CRITICAL! " + defender_msg
                others_msg = "CRITICAL! " + others_msg
        else:
            attacker_msg = f"You miss {defender_name}."
            defender_msg = f"{attacker_name} misses you."
            others_msg = f"{attacker_name} misses {defender_name}."

            if attack_result.critical_miss:
                attacker_msg = "You fumble! " + attacker_msg

        return {
            "attacker_msg": attacker_msg,
            "defender_msg": defender_msg,
            "others_msg": others_msg,
        }
