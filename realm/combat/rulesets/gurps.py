"""
GURPS-style 3d6 roll-under combat ruleset.

Roll 3d6 under your skill to hit.
- Roll of 3-4 is a critical success
- Roll of 17-18 is a critical failure
- Damage is based on weapon + strength

Expected stats on combatants:
- skill_melee, skill_ranged (skill levels, typically 10-15)
- strength, dexterity, health (attributes, typically 10)
- hp, max_hp
- damage_resistance (DR, reduces damage)
- dodge, parry, block (active defenses)

Expected stats on weapons:
- damage_dice (e.g., "1d+2" meaning 1d6+2)
- damage_type (e.g., "cutting", "impaling")
- skill_type ("melee" or "ranged")
- reach (for melee) or range (for ranged)
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Any

from realm.combat.ruleset import (
    AttackResult,
    DamageResult,
    DamageType,
    DefenseResult,
    RollResult,
    Ruleset,
)

if TYPE_CHECKING:
    from realm.combat.combatant import Combatant


# GURPS damage type multipliers
GURPS_DAMAGE_MULTIPLIERS = {
    'cutting': 1.5,  # Cut does x1.5 after DR
    'impaling': 2.0,  # Imp does x2 after DR
    'crushing': 1.0,  # Crush does x1
    'piercing': 1.0,  # Pi does x1
    'burning': 1.0,
}


class GURPSRuleset(Ruleset):
    """
    GURPS-style 3d6 roll-under combat system.

    Attack: Roll 3d6 <= skill level to hit
    Defense: Active defense (dodge, parry, block)
    Damage: Weapon dice + strength bonus - DR, then type multiplier
    """

    name = "GURPS 3d6"
    description = "GURPS-style 3d6 roll-under skill system"
    version = "1.0"

    required_stats = ['skill_melee', 'strength', 'hp', 'dodge']

    def __init__(
        self,
        allow_active_defense: bool = True,
        critical_success_threshold: int = 4,
        critical_failure_threshold: int = 17,
    ):
        """
        Initialize GURPS ruleset.

        Args:
            allow_active_defense: Whether defenders can dodge/parry/block
            critical_success_threshold: Roll this or less for crit success
            critical_failure_threshold: Roll this or more for crit failure
        """
        self.allow_active_defense = allow_active_defense
        self.crit_success = critical_success_threshold
        self.crit_failure = critical_failure_threshold

    def roll_3d6(self) -> tuple[int, list[int]]:
        """Roll 3d6 and return (total, dice)."""
        dice = [random.randint(1, 6) for _ in range(3)]
        return sum(dice), dice

    def is_critical_success(self, roll: int, skill: int) -> bool:
        """
        Check for critical success.

        Critical if:
        - Roll of 3-4 always
        - Roll of 5 if skill >= 15
        - Roll of 6 if skill >= 16
        """
        if roll <= 4:
            return True
        if roll == 5 and skill >= 15:
            return True
        if roll == 6 and skill >= 16:
            return True
        return False

    def is_critical_failure(self, roll: int, skill: int) -> bool:
        """
        Check for critical failure.

        Critical failure if:
        - Roll of 18 always
        - Roll of 17 if skill <= 15
        - Roll >= skill + 10
        """
        if roll == 18:
            return True
        if roll == 17 and skill <= 15:
            return True
        if roll >= skill + 10:
            return True
        return False

    def get_skill(self, combatant: Combatant, skill_type: str = "melee") -> int:
        """Get skill level for attack type."""
        if skill_type == "ranged":
            return combatant.get_stat('skill_ranged', 10)
        return combatant.get_stat('skill_melee', 10)

    def get_strength_bonus(self, combatant: Combatant) -> int:
        """
        Calculate thrust/swing damage bonus from strength.

        Simplified: (ST - 10) // 2 for thrust, (ST - 10) // 2 + 1 for swing
        """
        st = combatant.get_stat('strength', 10)
        return (st - 10) // 2

    def roll_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
        weapon: Any | None = None,
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        """
        Roll 3d6 vs skill level.

        Success if roll <= effective skill.
        """
        modifiers = modifiers or {}

        # Determine skill type
        skill_type = "melee"
        if weapon:
            if getattr(weapon, 'db', None):
                skill_type = weapon.db.get('skill_type', 'melee')
            else:
                skill_type = getattr(weapon, 'skill_type', 'melee')

        # Get base skill
        base_skill = self.get_skill(attacker, skill_type)

        # Apply modifiers
        situational = sum(modifiers.values())
        effective_skill = base_skill + situational

        # Roll 3d6
        roll_total, dice = self.roll_3d6()

        # Check for success/failure
        hit = roll_total <= effective_skill
        is_crit = self.is_critical_success(roll_total, effective_skill)
        is_fumble = self.is_critical_failure(roll_total, effective_skill)

        # Critical success always hits, critical failure always misses
        if is_crit:
            hit = True
        if is_fumble:
            hit = False

        margin = effective_skill - roll_total  # Positive = good

        roll = RollResult(
            total=roll_total,
            dice=dice,
            target=effective_skill,
            success=hit,
            critical=is_crit,
            fumble=is_fumble,
            description=f"3d6({roll_total}) vs skill {effective_skill}",
        )

        effects = []
        if is_crit:
            effects.append("Critical success!")
        if is_fumble:
            effects.append("Critical failure!")

        return AttackResult(
            hit=hit,
            roll=roll,
            critical_hit=is_crit,
            critical_miss=is_fumble,
            margin=margin,
            effects=effects,
        )

    def roll_defense(
        self,
        defender: Combatant,
        attack_type: str = "physical",
        modifiers: dict[str, int] | None = None,
    ) -> DefenseResult:
        """
        Roll active defense (dodge, parry, or block).

        Uses the best available defense.
        """
        if not self.allow_active_defense:
            return DefenseResult(
                success=False,
                roll=RollResult(total=0, dice=[]),
            )

        modifiers = modifiers or {}

        # Get defense values
        dodge = defender.get_stat('dodge', 8)
        parry = defender.get_stat('parry', 0)
        block = defender.get_stat('block', 0)

        # Use best defense
        best_defense = max(dodge, parry, block)
        defense_name = "Dodge"
        if parry > dodge and parry >= block:
            defense_name = "Parry"
        elif block > dodge:
            defense_name = "Block"

        # Apply modifiers
        situational = sum(modifiers.values())
        effective_defense = best_defense + situational

        # Roll 3d6
        roll_total, dice = self.roll_3d6()

        # Success if roll <= defense
        success = roll_total <= effective_defense

        roll = RollResult(
            total=roll_total,
            dice=dice,
            target=effective_defense,
            success=success,
            description=f"{defense_name}: 3d6({roll_total}) vs {effective_defense}",
        )

        return DefenseResult(success=success, roll=roll)

    def roll_damage(
        self,
        attacker: Combatant,
        defender: Combatant,
        attack_result: AttackResult,
        weapon: Any | None = None,
    ) -> DamageResult:
        """
        Roll damage dice + strength bonus.

        GURPS damage is typically noted as "1d+2" meaning 1d6+2.
        """
        # Default damage
        damage_dice = "1d"
        damage_type_str = "crushing"

        if weapon:
            if getattr(weapon, 'db', None):
                damage_dice = weapon.db.get('damage_dice', "1d")
                damage_type_str = weapon.db.get('damage_type', 'crushing')
            else:
                damage_dice = getattr(weapon, 'damage_dice', "1d")
                damage_type_str = getattr(weapon, 'damage_type', 'crushing')

        # Parse GURPS damage notation (e.g., "1d+2", "2d-1", "1d")
        num_dice, modifier = self._parse_gurps_dice(damage_dice)

        # Add strength bonus
        str_bonus = self.get_strength_bonus(attacker)
        total_modifier = modifier + str_bonus

        # Roll damage
        dice_results = [random.randint(1, 6) for _ in range(num_dice)]
        dice_total = sum(dice_results)
        raw_damage = max(0, dice_total + total_modifier)

        # Map damage type
        try:
            damage_type = DamageType(damage_type_str)
        except ValueError:
            damage_type = DamageType.PHYSICAL

        roll = RollResult(
            total=raw_damage,
            dice=dice_results,
            modifier=total_modifier,
            description=f"{num_dice}d6({dice_total})+{total_modifier} = {raw_damage} {damage_type_str}",
        )

        return DamageResult(
            total=raw_damage,
            damage_by_type={damage_type: raw_damage},
            roll=roll,
        )

    def apply_damage(
        self,
        target: Combatant,
        damage: DamageResult,
    ) -> int:
        """
        Apply damage with DR and damage type multipliers.

        GURPS damage calculation:
        1. Subtract DR from damage
        2. Apply damage type multiplier (cutting x1.5, impaling x2)
        3. Reduce HP
        """
        dr = target.get_stat('damage_resistance', 0)
        total_applied = 0

        for dtype, amount in damage.damage_by_type.items():
            # Subtract DR
            after_dr = max(0, amount - dr)

            # Apply type multiplier
            multiplier = GURPS_DAMAGE_MULTIPLIERS.get(dtype.value, 1.0)
            final_damage = int(after_dr * multiplier)

            total_applied += final_damage

        # Apply to HP
        actual = target.take_damage(total_applied)
        return actual

    def is_defeated(self, combatant: Combatant) -> bool:
        """
        Check if combatant is incapacitated.

        In GURPS, you're incapacitated at 0 HP but not dead until -HP.
        """
        return combatant.hp <= 0

    def roll_initiative(
        self,
        combatant: Combatant,
        modifiers: dict[str, int] | None = None,
    ) -> RollResult:
        """
        GURPS initiative is based on Basic Speed.

        Basic Speed = (DX + HT) / 4
        Higher goes first (no roll needed, but we add some randomness).
        """
        modifiers = modifiers or {}

        dx = combatant.get_stat('dexterity', 10)
        ht = combatant.get_stat('health', 10)
        basic_speed = (dx + ht) / 4

        # Add small random factor
        random_factor = random.random()

        # Initiative = Basic Speed + random tiebreaker
        total = int(basic_speed * 100 + random_factor * 10)

        return RollResult(
            total=total,
            dice=[],
            description=f"Initiative: Basic Speed {basic_speed:.2f}",
        )

    def roll_saving_throw(
        self,
        combatant: Combatant,
        save_type: str,
        difficulty: int,
        modifiers: dict[str, int] | None = None,
    ) -> DefenseResult:
        """
        Roll a resistance check: 3d6 vs attribute.

        save_type should be HT, Will, etc.
        difficulty modifies the target number.
        """
        modifiers = modifiers or {}

        # Map save types to stats
        stat_map = {
            'health': 'health',
            'ht': 'health',
            'will': 'will',
            'iq': 'intelligence',
            'fright': 'will',
        }
        stat = stat_map.get(save_type.lower(), save_type)
        base = combatant.get_stat(stat, 10)

        # Apply difficulty as penalty
        effective = base - difficulty + sum(modifiers.values())

        roll_total, dice = self.roll_3d6()
        success = roll_total <= effective

        roll = RollResult(
            total=roll_total,
            dice=dice,
            target=effective,
            success=success,
            description=f"{save_type} check: 3d6({roll_total}) vs {effective}",
        )

        return DefenseResult(success=success, roll=roll)

    def _parse_gurps_dice(self, dice_str: str) -> tuple[int, int]:
        """
        Parse GURPS damage notation.

        Examples: "1d", "1d+2", "2d-1", "1d6+3"
        """
        dice_str = dice_str.lower().strip()

        # Match patterns like "2d6+3" or "1d-1" or "1d"
        match = re.match(r'(\d+)d(?:6)?([+-]\d+)?', dice_str)
        if match:
            num_dice = int(match.group(1))
            modifier = int(match.group(2)) if match.group(2) else 0
            return num_dice, modifier

        return 1, 0  # Default to 1d6+0
