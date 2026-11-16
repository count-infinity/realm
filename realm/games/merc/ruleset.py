"""
Merc/Diku-lineage combat ruleset — THAC0 to-hit, descending armor class.

The model the DikuMUD -> Merc -> ROM family shares, and the one a converted
ROM area (see ``realm import-rom``) wants to run on:

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

- **Passive defenses** (ROM ``check_dodge``/``check_parry``/
  ``check_shield_block``): a hit that lands still has to get past the
  defender's ``dodge``, then ``parry`` (wielding a weapon), then
  ``shield_block`` (wearing a shield): each is one skill check, at half
  the skill (a fifth plus 3 for the shield) shifted by the level
  difference, rolled through ``check()`` like any skill.
- **Extra attacks**: a warrior's ``second_attack`` (half the skill) and
  then ``third_attack`` (a quarter) are more swings in the same round.

Expected combatant stats: ``thac0``, ``armor_class`` (lower is better),
``strength``, ``hp``/``max_hp``. Expected weapon attrs: ``damage_dice``
(e.g. ``"2d4"``), optional ``damage_type``, optional ``damroll`` bonus.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from realm.std.combat.ruleset import (
    AttackResult,
    DamageResult,
    RollResult,
    Ruleset,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.std.combat.combatant import Combatant

#: ROM's passive defenses, in the order they are tried: (skill, the share of
#: the skill that is the chance, a flat bonus, what the defender needs).
DEFENSES: tuple[tuple[str, float, int, str | None], ...] = (
    ("dodge", 0.5, 0, None),
    ("parry", 0.5, 0, "weapon"),
    ("shield_block", 0.2, 3, "shield"),
)

#: How each defense reads: (defender, attacker, room), with {a} and {d}.
DEFENSE_MESSAGES: dict[str, tuple[str, str, str]] = {
    "dodge": ("You dodge {a}'s attack.", "{d} dodges your attack.",
              "{d} dodges {a}'s attack."),
    "parry": ("You parry {a}'s attack.", "{d} parries your attack.",
              "{d} parries {a}'s attack."),
    "shield_block": ("You block {a}'s attack with your shield.",
                     "{d} blocks your attack with a shield.",
                     "{d} blocks {a}'s attack with a shield."),
}


def _trained(obj: GameObject, skill: str) -> int:
    return int(obj.db.get(f"skill_{skill}") or 0)


def _level(obj: GameObject) -> int:
    return int(obj.db.get("level") or 1)


def _chance_check(obj: GameObject, skill: str, chance: int) -> bool:
    """A check of ``skill`` whose percentile target is ``chance``."""
    from realm.std.rules.checks import check
    return check(obj, skill, chance - _trained(obj, skill)).success


def passive_defense(attacker: GameObject, defender: GameObject) -> str | None:
    """The defense that turns this hit aside, or None."""
    for skill, share, bonus, needs in DEFENSES:
        level = _trained(defender, skill)
        if level <= 0:
            continue
        if needs == "weapon" and not any(o.has_tag("wielded") for o in defender.contents):
            continue
        if needs == "shield" and not any(o.has_tag("worn") and o.db.get("slot") == "shield"
                                         for o in defender.contents):
            continue
        chance = int(level * share) + bonus + _level(defender) - _level(attacker)
        if chance > 0 and _chance_check(defender, skill, chance):
            return skill
    return None


class MercRuleset(Ruleset):
    """Diku/Merc/ROM-style d20 THAC0 combat."""

    name = "Merc System"
    description = "Diku/Merc/ROM d20 THAC0 vs descending armor class"
    version = "1.0"

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
        if hit:
            defense = passive_defense(attacker.obj, defender.obj)
            if defense is not None:
                hit, crit = False, False
                roll.success = False
                effects = [defense]
        return AttackResult(hit=hit, roll=roll, critical_hit=crit,
                            critical_miss=fumble, margin=d20 - need,
                            effects=effects)

    def format_attack_message(self, attacker, defender, attack_result, damage_result=None):
        """A hit turned aside reads as the defense that did it."""
        defense = next((e for e in attack_result.effects if e in DEFENSE_MESSAGES), None)
        if attack_result.hit or defense is None:
            return super().format_attack_message(attacker, defender, attack_result,
                                                 damage_result)
        mine, theirs, room = DEFENSE_MESSAGES[defense]
        names = {"a": attacker.name, "d": defender.name}
        return {"defender_msg": mine.format(**names),
                "attacker_msg": theirs.format(**names),
                "others_msg": room.format(**names)}

    def extra_attacks(self, attacker: Any) -> int:
        """ROM ``multi_hit``: a second attack at half the skill, and only
        then a third at a quarter."""
        extra = 0
        for skill, share in (("second_attack", 0.5), ("third_attack", 0.25)):
            level = _trained(attacker, skill)
            if level <= 0 or not _chance_check(attacker, skill, max(1, int(level * share))):
                break
            extra += 1
        return extra

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
                            roll=roll,
                            magical=self.weapon_is_magical(weapon))

    def apply_damage(self, target: Combatant, damage: DamageResult) -> int:
        # Diku armor does not mitigate damage (that was the to-hit roll), but
        # a creature's damage-type resistances do: scale each typed component
        # by the target's ``resistances`` multipliers, then the damage pool
        # simply drops.
        # Broad family keys (physical/magical) apply by DELIVERY — an
        # enchanted blade bypasses weapon immunity (ROM's magic weapons).
        # Softcode on_check wards already ran before this.
        self.scale_resistances(target, damage)
        return self.write_damage(target, max(0, damage.total))
