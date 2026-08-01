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

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.combat.combatant import Combatant

#: ``NdS+B`` — sides optional (GURPS ``2d+1``), anchored both ends.
_DICE_RE = re.compile(r"\s*(\d+)d(\d*)([+-]\d+)?\s*$")


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
    # How the damage was DELIVERED: True for enchanted weapons and spells.
    # Drives the broad-family key ladder in apply_type_resistance (an
    # enchanted blade bypasses 'physical' immunity, the SMAUG/ROM way).
    magical: bool = False


#: Specific types the broad ``physical`` family key covers (weapon-flavored
#: damage). ``physical`` itself is included for callers that type damage
#: broadly to begin with.
PHYSICAL_FAMILY = frozenset({
    DamageType.SLASHING.value, DamageType.PIERCING.value,
    DamageType.BLUDGEONING.value, DamageType.PHYSICAL.value,
})


def apply_type_resistance(
    damage_by_type: dict[DamageType, int],
    resistances: dict[str, float] | None,
    *,
    magical: bool = False,
) -> tuple[dict[DamageType, int], int]:
    """Scale typed damage by a creature's resistance multipliers.

    ``resistances`` maps a damage-type name (``DamageType`` value, e.g.
    ``"fire"``) to a *damage-taken multiplier*: ``0.0`` = immune, ``0.5`` =
    half (the Diku "resist" tier), ``1.5`` = the Diku "vuln" tier, ``0.85`` =
    15% resistance, ``1.0`` or absent = normal. It is a continuous knob, not
    three fixed tiers -- any non-negative float works, so 15% or 77%
    resistance is just ``0.85`` / ``0.23``.

    **Key ladder (most specific wins, one key per component):** the exact
    type key first; failing that, a broad *family* key by how the damage
    was DELIVERED — ``magical`` when the hit came from an enchanted weapon
    or a spell (``magical=True``), else ``physical`` for weapon-flavored
    types (:data:`PHYSICAL_FAMILY`). This is the synthesis of the SMAUG and
    CoffeeMud models (survey 2026-08-01): broad keys describe delivery, not
    type, so an exact-key-only lookup silently ignores ROM's IMM_WEAPON /
    IMM_MAGIC — and a mundane torch's fire is NOT gated by magic immunity.
    The magic-weapon bypass falls out naturally: an enchanted blade's hit
    is ``magical``, so a mob immune only to ``physical`` takes full damage.

    This is deliberately ruleset-agnostic: the *data* (what a creature
    resists) is a portable creature property, while each ruleset decides in
    its own ``apply_damage`` how this composes with flat armor/DR and in what
    order. ``DamageType.TRUE`` bypasses the table entirely.

    Returns ``(scaled_by_type, resisted)`` -- a new per-type dict and the net
    damage removed (negative if a vulnerability *added* damage).
    """
    if not resistances:
        return dict(damage_by_type), 0
    scaled: dict[DamageType, int] = {}
    resisted = 0
    for dtype, amount in damage_by_type.items():
        if dtype == DamageType.TRUE:
            scaled[dtype] = amount
            continue
        key = dtype.value if isinstance(dtype, DamageType) else dtype
        if key in resistances:
            mult = resistances[key]
        elif magical:
            mult = resistances.get('magical', 1.0)
        elif key in PHYSICAL_FAMILY:
            mult = resistances.get('physical', 1.0)
        else:
            mult = 1.0
        new_amount = max(0, round(amount * mult))
        resisted += amount - new_amount
        scaled[dtype] = new_amount
    return scaled, resisted


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

    # --- Maneuver vocabulary ---
    #
    # The encounter engine schedules whatever maneuvers the ruleset
    # publishes; rulesets extend the base vocabulary as DATA. Resolution
    # of ruleset-specific maneuvers happens in resolve_special_maneuver.

    def maneuvers(self) -> list:
        """The maneuvers combatants may queue. Extend in subclasses."""
        from realm.combat.maneuver import BASE_MANEUVERS
        return list(BASE_MANEUVERS)

    def get_maneuver(self, key_or_alias: str):
        """Look up a maneuver by key or alias (case-insensitive)."""
        wanted = key_or_alias.strip().lower()
        for maneuver in self.maneuvers():
            if maneuver.key == wanted or wanted in maneuver.aliases:
                return maneuver
        return None

    async def resolve_special_maneuver(
        self,
        combat_system,
        encounter,
        actor,
        action,
        target,
    ) -> bool:
        """
        Resolve a ruleset-specific maneuver (anything beyond the base
        attack/defend/flee/wait, which the CombatSystem handles).

        Returns True if handled.
        """
        return False

    # --- Shared helpers ---
    #
    # The three little rituals every ruleset repeated (weapon-property
    # shuffle, dice-spec parsing, damage-type coercion) live here once.

    @staticmethod
    def weapon_prop(weapon: Any | None, key: str, default: Any = None) -> Any:
        """A weapon property, wherever it lives.

        Live weapons carry properties in ``db``; test stubs and plain
        dataclasses carry them as attributes. None-safe.
        """
        if weapon is None:
            return default
        db = getattr(weapon, 'db', None)
        if db is not None:
            return db.get(key, default)
        return getattr(weapon, key, default)

    @staticmethod
    def weapon_is_magical(weapon: Any | None) -> bool:
        """Is this weapon enchanted? (the ``magic`` tag, or a truthy
        ``magic`` property on stubs). Drives the delivery axis of
        :func:`apply_type_resistance`."""
        if weapon is None:
            return False
        has_tag = getattr(weapon, 'has_tag', None)
        if callable(has_tag):
            return bool(has_tag('magic'))
        return bool(Ruleset.weapon_prop(weapon, 'magic', False))

    @staticmethod
    def parse_dice(spec: Any, *, default: tuple[int, int, int] = (1, 4, 0),
                   default_sides: int = 6) -> tuple[int, int, int]:
        """``NdS+B`` -> (N, S, B).

        Sides may be omitted (GURPS ``2d+1`` -> ``default_sides``); a spec
        that does not parse at all returns ``default``. Anchored: trailing
        garbage is a parse failure, not silently ignored.
        """
        m = _DICE_RE.match(str(spec or ""))
        if not m:
            return default
        n = int(m.group(1))
        sides = int(m.group(2)) if m.group(2) else default_sides
        bonus = int(m.group(3) or 0)
        return n, sides, bonus

    @staticmethod
    def coerce_damage_type(
        name: Any, fallback: DamageType = DamageType.PHYSICAL,
    ) -> DamageType:
        """A DamageType from a string, tolerating unknown names."""
        if isinstance(name, DamageType):
            return name
        try:
            return DamageType(str(name).lower())
        except ValueError:
            return fallback

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


    # --- Utility Methods ---


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
