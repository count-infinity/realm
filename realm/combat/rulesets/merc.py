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
- **Apply**: HP loss after a damage-type ``resistances`` pass. Diku has no
  flat DR, so the only mitigation is the per-type multiplier (immune 0.0,
  resist 0.5, vuln 1.5, or any float) read from the target's ``resistances``
  attr — the same portable creature property the ROM importer emits from
  imm/res/vuln flags. Softcode ``on_check`` wards still run before this.

Expected combatant stats: ``thac0``, ``armor_class`` (lower is better),
``strength``, ``hp``/``max_hp``. Expected weapon attrs: ``damage_dice``
(e.g. ``"2d4"``), optional ``damage_type``, optional ``damroll`` bonus.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from realm.combat.ruleset import (
    AttackResult,
    DamageResult,
    RollResult,
    Ruleset,
    apply_type_resistance,
)

if TYPE_CHECKING:
    from realm.combat.combatant import Combatant


class MercRuleset(Ruleset):
    """Diku/Merc/ROM-style d20 THAC0 combat."""

    name = "Merc System"
    description = "Diku/Merc/ROM d20 THAC0 vs descending armor class"
    version = "1.0"

    required_stats = ["thac0", "armor_class", "strength", "hp"]

    def _damroll(self, attacker: Combatant, weapon: Any | None) -> int:
        # Strength-based bonus to damage (Diku 'damroll'), plus any bonus the
        # weapon itself carries.
        strength = attacker.get_stat("strength", 13)
        str_bonus = max(0, (strength - 14) // 2)
        return str_bonus + int(self.weapon_prop(weapon, "damroll", 0) or 0)

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
        # A wielded weapon's dice, else the attacker's own natural-attack
        # dice (imported Diku mobs carry their own ``damage_dice``), else 1d4.
        spec = self.weapon_prop(weapon, "damage_dice", None)
        if spec is None:
            spec = getattr(attacker, "_obj", None) and \
                attacker._obj.db.get("damage_dice")
        n, s, b = self.parse_dice(spec or "1d4")
        if attack_result.critical_hit:
            n *= 2                                   # Diku crit: double dice
        dice = [random.randint(1, s) for _ in range(n)]
        damroll = self._damroll(attacker, weapon)
        total = max(1, sum(dice) + b + damroll)

        dtype_name = self.weapon_prop(weapon, "damage_type", "bludgeoning")
        dtype = self.coerce_damage_type(dtype_name)
        roll = RollResult(
            total=total, dice=dice, modifier=b + damroll,
            description=f"{n}d{s}({sum(dice)})+{b + damroll} = {total}")
        return DamageResult(total=total, damage_by_type={dtype: total},
                            roll=roll)

    def apply_damage(self, target: Combatant, damage: DamageResult) -> int:
        # Diku armor does not mitigate damage (that was the to-hit roll), but
        # a creature's damage-type resistances do: scale each typed component
        # by the target's ``resistances`` multipliers, then HP simply drops.
        # Softcode on_check wards already ran before this.
        resist = self._resistances(target)
        if resist and damage.damage_by_type:
            scaled, resisted = apply_type_resistance(damage.damage_by_type,
                                                     resist)
            damage.damage_by_type = scaled
            damage.total = sum(scaled.values())
            damage.resisted = resisted
        hp = target.get_stat("hp", 0)
        dealt = max(0, damage.total)
        target.set_stat("hp", hp - dealt)
        return dealt

    def _resistances(self, combatant: Combatant) -> dict[str, float] | None:
        """The target's damage-type multiplier map, if it carries one."""
        obj = getattr(combatant, "_obj", None)
        db = getattr(obj, "db", None)
        if db is not None:
            r = db.get("resistances")
            if isinstance(r, dict):
                return r
        return None

    def is_defeated(self, combatant: Combatant) -> bool:
        """Defeated at 0 HP (Diku goes to negatives before true death, but
        0 ends the fight)."""
        return combatant.get_stat("hp", 0) <= 0
