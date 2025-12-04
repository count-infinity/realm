"""
D20 (D&D 5e-style) combat ruleset.

Roll d20 + modifier vs Armor Class.
- Natural 20 is a critical hit (double damage dice)
- Natural 1 is a critical miss
- Damage is weapon dice + strength/dexterity modifier

Expected stats on combatants:
- strength, dexterity, constitution (ability scores)
- armor_class (AC)
- hp, max_hp
- proficiency_bonus (optional, default 2)

Expected stats on weapons:
- damage_dice (e.g., "1d8", "2d6")
- damage_type (e.g., "slashing")
- finesse (bool, use dex instead of str)
- range (int, 1 for melee)
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Any

from realm.combat.ruleset import (
    Ruleset,
    RollResult,
    AttackResult,
    DamageResult,
    DamageType,
)

if TYPE_CHECKING:
    from realm.combat.combatant import Combatant


class D20Ruleset(Ruleset):
    """
    D&D 5e-style d20 combat system.

    Attack: d20 + ability modifier + proficiency vs AC
    Damage: weapon dice + ability modifier
    Critical: Natural 20 doubles damage dice
    """

    name = "D20 System"
    description = "D&D 5th Edition style d20 + modifier vs AC"
    version = "1.0"

    required_stats = ['strength', 'dexterity', 'armor_class', 'hp']

    def __init__(
        self,
        default_proficiency: int = 2,
        use_proficiency: bool = True,
        crit_multiplier: int = 2,
    ):
        """
        Initialize D20 ruleset.

        Args:
            default_proficiency: Default proficiency bonus
            use_proficiency: Whether to add proficiency to attacks
            crit_multiplier: Damage dice multiplier on crit (default 2)
        """
        self.default_proficiency = default_proficiency
        self.use_proficiency = use_proficiency
        self.crit_multiplier = crit_multiplier

    def get_ability_modifier(self, combatant: Combatant, ability: str) -> int:
        """
        Calculate D&D-style ability modifier.

        Modifier = (ability - 10) // 2
        """
        score = combatant.get_stat(ability, 10)
        return (score - 10) // 2

    def get_proficiency(self, combatant: Combatant) -> int:
        """Get proficiency bonus."""
        if not self.use_proficiency:
            return 0
        return combatant.get_stat('proficiency_bonus', self.default_proficiency)

    def roll_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
        weapon: Any | None = None,
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        """
        Roll d20 + modifiers vs AC.

        Modifiers:
        - Ability modifier (STR or DEX for finesse)
        - Proficiency bonus
        - Situational modifiers (advantage, flanking, etc.)
        """
        modifiers = modifiers or {}

        # Roll the d20
        d20 = random.randint(1, 20)

        # Check for critical
        is_crit = d20 == 20
        is_fumble = d20 == 1

        # Determine ability to use
        use_dex = False
        if weapon:
            if getattr(weapon, 'db', None):
                use_dex = weapon.db.get('finesse', False)
            else:
                use_dex = getattr(weapon, 'finesse', False)

        ability = 'dexterity' if use_dex else 'strength'
        ability_mod = self.get_ability_modifier(attacker, ability)

        # Calculate total modifier
        proficiency = self.get_proficiency(attacker)
        situational = sum(modifiers.values())
        total_modifier = ability_mod + proficiency + situational

        # Final attack roll
        attack_total = d20 + total_modifier

        # Get defender's AC
        armor_class = defender.get_stat('armor_class', 10)

        # Determine hit (natural 1 always misses, natural 20 always hits)
        if is_fumble:
            hit = False
        elif is_crit:
            hit = True
        else:
            hit = attack_total >= armor_class

        margin = attack_total - armor_class

        # Build roll result
        roll = RollResult(
            total=attack_total,
            dice=[d20],
            modifier=total_modifier,
            target=armor_class,
            success=hit,
            critical=is_crit,
            fumble=is_fumble,
            description=f"d20({d20})+{total_modifier} = {attack_total} vs AC {armor_class}",
        )

        effects = []
        if is_crit:
            effects.append("Critical hit!")
        if is_fumble:
            effects.append("Critical miss!")

        return AttackResult(
            hit=hit,
            roll=roll,
            critical_hit=is_crit,
            critical_miss=is_fumble,
            margin=margin,
            effects=effects,
        )

    def roll_damage(
        self,
        attacker: Combatant,
        defender: Combatant,
        attack_result: AttackResult,
        weapon: Any | None = None,
    ) -> DamageResult:
        """
        Roll weapon damage + ability modifier.

        Critical hits double the damage dice.
        """
        # Default damage if no weapon
        damage_dice = "1d4"
        damage_type = DamageType.BLUDGEONING

        if weapon:
            if getattr(weapon, 'db', None):
                damage_dice = weapon.db.get('damage_dice', "1d4")
                dtype = weapon.db.get('damage_type', 'bludgeoning')
            else:
                damage_dice = getattr(weapon, 'damage_dice', "1d4")
                dtype = getattr(weapon, 'damage_type', 'bludgeoning')
            try:
                damage_type = DamageType(dtype)
            except ValueError:
                damage_type = DamageType.PHYSICAL

        # Parse damage dice (e.g., "2d6", "1d8")
        num_dice, sides = self._parse_dice(damage_dice)

        # Double dice on crit
        if attack_result.critical_hit:
            num_dice *= self.crit_multiplier

        # Roll damage
        dice_results = [random.randint(1, sides) for _ in range(num_dice)]
        dice_total = sum(dice_results)

        # Add ability modifier
        use_dex = False
        if weapon:
            if getattr(weapon, 'db', None):
                use_dex = weapon.db.get('finesse', False)
            else:
                use_dex = getattr(weapon, 'finesse', False)

        ability = 'dexterity' if use_dex else 'strength'
        ability_mod = self.get_ability_modifier(attacker, ability)

        total_damage = max(1, dice_total + ability_mod)  # Minimum 1 damage

        roll = RollResult(
            total=total_damage,
            dice=dice_results,
            modifier=ability_mod,
            description=f"{num_dice}d{sides}({dice_total})+{ability_mod} = {total_damage}",
        )

        return DamageResult(
            total=total_damage,
            damage_by_type={damage_type: total_damage},
            roll=roll,
        )

    def apply_damage(
        self,
        target: Combatant,
        damage: DamageResult,
    ) -> int:
        """
        Apply damage considering resistances/vulnerabilities.
        """
        total_applied = 0
        resisted = 0

        for dtype, amount in damage.damage_by_type.items():
            multiplier = target.get_resistance(dtype.value)
            final_amount = int(amount * multiplier)
            resisted += amount - final_amount
            total_applied += final_amount

        # Apply damage to HP
        actual = target.take_damage(total_applied)

        return actual

    def is_defeated(self, combatant: Combatant) -> bool:
        """Check if combatant is at 0 HP."""
        return combatant.hp <= 0

    def roll_initiative(
        self,
        combatant: Combatant,
        modifiers: dict[str, int] | None = None,
    ) -> RollResult:
        """
        Roll initiative: d20 + DEX modifier.
        """
        modifiers = modifiers or {}

        d20 = random.randint(1, 20)
        dex_mod = self.get_ability_modifier(combatant, 'dexterity')
        situational = sum(modifiers.values())
        total = d20 + dex_mod + situational

        return RollResult(
            total=total,
            dice=[d20],
            modifier=dex_mod + situational,
            description=f"Initiative: d20({d20})+{dex_mod} = {total}",
        )

    def roll_saving_throw(
        self,
        combatant: Combatant,
        save_type: str,
        difficulty: int,
        modifiers: dict[str, int] | None = None,
    ) -> Any:
        """
        Roll a saving throw: d20 + ability modifier vs DC.

        save_type should be an ability name (strength, dexterity, etc.)
        """
        from realm.combat.ruleset import DefenseResult

        modifiers = modifiers or {}

        d20 = random.randint(1, 20)
        ability_mod = self.get_ability_modifier(combatant, save_type)
        situational = sum(modifiers.values())
        total = d20 + ability_mod + situational

        success = total >= difficulty

        roll = RollResult(
            total=total,
            dice=[d20],
            modifier=ability_mod + situational,
            target=difficulty,
            success=success,
            description=f"{save_type.title()} save: d20({d20})+{ability_mod} = {total} vs DC {difficulty}",
        )

        return DefenseResult(success=success, roll=roll)

    def _parse_dice(self, dice_str: str) -> tuple[int, int]:
        """Parse dice notation like '2d6' into (num, sides)."""
        match = re.match(r'(\d+)d(\d+)', dice_str.lower())
        if match:
            return int(match.group(1)), int(match.group(2))
        return 1, 4  # Default to 1d4
