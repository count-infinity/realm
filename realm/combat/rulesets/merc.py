"""
Merc/Diku-lineage combat ruleset — THAC0 to-hit, descending armor class.

The model the DikuMUD -> Merc -> ROM family shares, and the one a converted
ROM area (see scripts/rom_import.py) wants to run on:

- **To hit**: roll d20; a hit needs ``d20 >= thac0 - armor_class``. Lower
  ``thac0`` (a better attacker, from the class/level table) and lower
  ``armor_class`` (a better-armored defender) both matter. Natural 20
  always hits, natural 1 always misses. This is descending AC — the
  opposite of the shipped D20 ruleset's ascending ``d20 >= AC``.
- **Damage**: weapon dice + a strength ``damroll``. Armor does **not**
  reduce damage here — in Diku, AC changes whether you are hit, not how
  hard. (Contrast GURPS DR / the ships shield model.)
- **Apply**: straight HP loss, honoring any softcode ``on_check`` ward or
  ruleset-agnostic resistance the engine already applies.

Expected combatant stats: ``thac0``, ``armor_class`` (lower is better),
``strength``, ``hp``/``max_hp``. Expected weapon attrs: ``damage_dice``
(e.g. ``"2d4"``), optional ``damage_type``, optional ``damroll`` bonus.
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Any

from realm.combat.ruleset import (
    AttackResult,
    DamageResult,
    DamageType,
    RollResult,
    Ruleset,
)

if TYPE_CHECKING:
    from realm.combat.combatant import Combatant


def _parse_dice(spec: str) -> tuple[int, int, int]:
    """``NdS+B`` -> (N, S, B). Falls back to (1, 4, 0)."""
    m = re.match(r"\s*(\d+)d(\d+)([+-]\d+)?\s*$", str(spec))
    if not m:
        return 1, 4, 0
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


class MercRuleset(Ruleset):
    """Diku/Merc/ROM-style d20 THAC0 combat."""

    name = "Merc System"
    description = "Diku/Merc/ROM d20 THAC0 vs descending armor class"
    version = "1.0"

    required_stats = ["thac0", "armor_class", "strength", "hp"]

    def _weapon_attr(self, weapon: Any | None, key: str, default: Any) -> Any:
        if weapon is None:
            return default
        db = getattr(weapon, "db", None)
        if db is not None:
            return db.get(key, default)
        return getattr(weapon, key, default)

    def _damroll(self, attacker: Combatant, weapon: Any | None) -> int:
        # Strength-based bonus to damage (Diku 'damroll'), plus any bonus the
        # weapon itself carries.
        strength = attacker.get_stat("strength", 13)
        str_bonus = max(0, (strength - 14) // 2)
        return str_bonus + int(self._weapon_attr(weapon, "damroll", 0) or 0)

    def roll_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
        weapon: Any | None = None,
        modifiers: dict[str, int] | None = None,
    ) -> AttackResult:
        modifiers = modifiers or {}
        d20 = random.randint(1, 20)
        crit = d20 == 20
        fumble = d20 == 1

        thac0 = attacker.get_stat("thac0", 20)
        ac = defender.get_stat("armor_class", 10)
        # Situational modifiers make the attacker MORE likely to hit, i.e.
        # they lower the number needed.
        need = thac0 - ac - sum(modifiers.values())

        if fumble:
            hit = False
        elif crit:
            hit = True
        else:
            hit = d20 >= need

        roll = RollResult(
            total=d20, dice=[d20], modifier=-sum(modifiers.values()),
            target=need, success=hit, critical=crit, fumble=fumble,
            description=f"d20({d20}) vs need {need} (THAC0 {thac0} - AC {ac})",
        )
        effects = ["Critical hit!"] if crit else \
            (["Fumble!"] if fumble else [])
        return AttackResult(hit=hit, roll=roll, critical_hit=crit,
                            critical_miss=fumble, margin=d20 - need,
                            effects=effects)

    def roll_damage(
        self,
        attacker: Combatant,
        defender: Combatant,
        attack_result: AttackResult,
        weapon: Any | None = None,
    ) -> DamageResult:
        spec = self._weapon_attr(weapon, "damage_dice", "1d4")
        n, s, b = _parse_dice(spec)
        if attack_result.critical_hit:
            n *= 2                                   # Diku crit: double dice
        dice = [random.randint(1, s) for _ in range(n)]
        damroll = self._damroll(attacker, weapon)
        total = max(1, sum(dice) + b + damroll)

        dtype_name = self._weapon_attr(weapon, "damage_type", "bludgeoning")
        try:
            dtype = DamageType(dtype_name)
        except ValueError:
            dtype = DamageType.PHYSICAL
        roll = RollResult(
            total=total, dice=dice, modifier=b + damroll,
            description=f"{n}d{s}({sum(dice)})+{b + damroll} = {total}")
        return DamageResult(total=total, damage_by_type={dtype: total},
                            roll=roll)

    def apply_damage(self, target: Combatant, damage: DamageResult) -> int:
        # Diku armor does not mitigate damage (that was the to-hit roll);
        # HP simply drops. Softcode on_check wards and any engine-level
        # resistance already ran before this.
        hp = target.get_stat("hp", 0)
        dealt = max(0, damage.total)
        target.set_stat("hp", hp - dealt)
        return dealt

    def is_defeated(self, combatant: Combatant) -> bool:
        """Defeated at 0 HP (Diku goes to negatives before true death, but
        0 ends the fight)."""
        return combatant.get_stat("hp", 0) <= 0
