"""
Merc/Diku-lineage game system — the rules a converted ROM area wants.

Pairs with :class:`realm.combat.rulesets.merc.MercRuleset`. What makes it
Diku rather than the shipped GURPS/D20 packages:

- **Five attributes** — STR/INT/WIS/DEX/CON (Diku's, 3..25).
- **Percentile skills** — a skill is a learned 0..99 %, and a check is
  ``d100 <= skill%``; untrained skills default low, so you cannot pick a
  lock you were never taught.
- **Four classes** — mage / cleric / thief / warrior, each with a hit die,
  a THAC0 progression, and starting skills.
- **Level-based HP** — a fresh character gets its class hit die; each level
  grants another (its expected roll) plus a constitution bonus. This is
  the one thing the point-buy GURPS/D20 packages do not do, and it is why
  this system overrides the award seam (see ``grant_award`` below).

**Advancement is XP-and-level here, not point-buy CP.** The GameSystem ABC
stays model-neutral: it exposes one seam, ``grant_award(player, amount)``,
that both models share (a kill deposits a reward). The default writes
``character_points``; this system overrides it to bank XP and auto-level.
Everything level-specific — the XP curve, ``advance_level`` — lives here as
add-on methods, not in the ABC. So CP systems and XP systems coexist by
each owning their own advancement, sharing only the deposit.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from realm.systems.base import ChoiceStep, GameSystem

if TYPE_CHECKING:
    from realm.core.objects import GameObject

# name -> (blurb, hit_die, thac0_rate, mana_per_level, stat_bumps, skills)
# thac0_rate = character levels per 1 point of THAC0 improvement (lower is
# a faster fighter). Skills are starting percentages.
MERC_CLASSES: dict[str, dict[str, Any]] = {
    "warrior": {
        "blurb": "a front-line fighter: best hit die and THAC0, no spells",
        "hit_die": 10, "thac0_rate": 1, "mana_per_level": 0,
        "stats": {"strength": 16, "constitution": 15},
        "skills": {"melee": 40, "shield_block": 25, "rescue": 20},
        "starting_weapon": {"name": "a short sword", "damage_dice": "1d6"},
    },
    "barbarian": {
        "blurb": "a savage warrior: the biggest hit die, a brutal club, "
                 "no spells",
        "hit_die": 12, "thac0_rate": 1, "mana_per_level": 0,
        "stats": {"strength": 17, "constitution": 16},
        "skills": {"melee": 40, "dodge": 20, "rescue": 15},
        "starting_weapon": {"name": "a heavy wooden club", "damage_dice": "1d8"},
    },
    "thief": {
        "blurb": "a skirmisher: stealth, locks, and a wicked backstab",
        "hit_die": 6, "thac0_rate": 2, "mana_per_level": 0,
        "stats": {"dexterity": 16, "intelligence": 13},
        "skills": {"stealth": 45, "lockpicking": 40, "backstab": 30,
                   "melee": 20},
        "starting_weapon": {"name": "a dagger", "damage_dice": "1d4"},
    },
    "cleric": {
        "blurb": "a divine caster: healing and protective prayers",
        "hit_die": 8, "thac0_rate": 2, "mana_per_level": 8,
        "stats": {"wisdom": 16, "strength": 13},
        "skills": {"heal": 40, "bless": 30, "melee": 15},
        "starting_weapon": {"name": "a wooden mace", "damage_dice": "1d6"},
    },
    "mage": {
        "blurb": "an arcane caster: fragile, but the deadliest spells",
        "hit_die": 4, "thac0_rate": 3, "mana_per_level": 10,
        "stats": {"intelligence": 16, "dexterity": 13},
        "skills": {"magic_missile": 35, "detect_magic": 40, "stealth": 10},
        "starting_weapon": {"name": "a gnarled dagger", "damage_dice": "1d4"},
    },
}

# Untrained percentile defaults: (governing attribute, flat penalty). A
# skill you were never taught rolls near zero.
BUILTIN_SKILL_DEFAULTS: dict[str, tuple[str, int]] = {
    "melee": ("strength", -30),
    "stealth": ("dexterity", -40),
    "lockpicking": ("dexterity", -80),   # untrainable without practice
    "heal": ("wisdom", -60),
    "observation": ("intelligence", -20),
}


def _hit_die_expected(die: int) -> int:
    return round((1 + die) / 2)


def _con_bonus(player: GameObject) -> int:
    return max(0, (int(player.db.get("constitution") or 13) - 14) // 2)


class MercSystem(GameSystem):
    """Diku/Merc/ROM-lite: percentile skills, four classes, XP leveling."""

    system_id = "merc"
    ruleset_name = "merc"
    currency_name = "gold"

    # --- baseline & skills ---

    def baseline_stats(self) -> dict[str, Any]:
        return {
            "strength": 13, "intelligence": 13, "wisdom": 13,
            "dexterity": 13, "constitution": 13,
            "level": 1, "xp": 0, "practices": 0,
            "hp": 20, "max_hp": 20, "mana": 100, "max_mana": 100,
            "thac0": 20, "armor_class": 10,
        }

    def skill_defaults(self) -> dict[str, tuple[str, int]]:
        from realm.systems.definitions import read_skill_defs
        defaults = dict(BUILTIN_SKILL_DEFAULTS)
        defaults.update(read_skill_defs())
        return defaults

    def resolve_check(self, obj: GameObject, skill: str, modifier: int):
        """Percentile: roll d100, succeed on ``<= skill% + modifier``."""
        from realm.core.checks import CheckResult, skill_level
        pct = max(0, min(99, skill_level(obj, skill) + modifier))
        d100 = random.randint(1, 100)
        success = d100 <= pct
        return CheckResult(success=success, margin=pct - d100, roll=d100,
                           effective=pct, skill=skill)

    # --- creation ---

    def _classes(self) -> dict[str, dict[str, Any]]:
        return MERC_CLASSES

    def chargen_steps(self):
        from realm.systems.definitions import apply_class
        classes = self._classes()

        def apply(player: GameObject, name: str) -> None:
            spec = classes[name]
            apply_class(player, (spec["blurb"], spec["stats"], spec["skills"]),
                        name, marker="character_class")

        return [ChoiceStep(
            "class", "Choose your class:",
            {name: c["blurb"] for name, c in classes.items()}, apply)]

    def finish_chargen(self, player: GameObject) -> str:
        cls = str(player.db.get("character_class") or "warrior")
        spec = self._classes().get(cls, self._classes()["warrior"])
        # Level 1: full hit die + con bonus (Diku gives max HP at first level).
        hp = spec["hit_die"] + _con_bonus(player)
        player.db.hp = hp
        player.db.max_hp = hp
        player.db.thac0 = 20
        player.db.max_mana = 100 + spec["mana_per_level"]
        player.db.mana = player.db.max_mana
        self.recompute_ac(player)
        return f"Your {cls} steps into the world, ready to earn their name."

    async def outfit_new_character(self, player: GameObject,
                                   persistence: Any) -> None:
        """Hand the new character its class starting weapon, wielded."""
        from realm.core.objects import GameObject

        cls = str(player.db.get("character_class") or "warrior")
        spec = self._classes().get(cls, self._classes()["warrior"])
        weapon = spec.get("starting_weapon")
        if not weapon:
            return
        dice = str(weapon.get("damage_dice", "1d4"))
        item = GameObject(name=str(weapon["name"]),
                          tags=["thing", "weapon", "wieldable", "wielded"],
                          location=player)
        item.db.set("damage_dice", dice)
        item.db.set("damage", dice)
        item.owner = player
        if persistence is not None:
            await persistence.save(item)
        player.msg(f"You grip {weapon['name']}, ready for trouble.")
        self.recompute_ac(player)

    def recompute_ac(self, player: GameObject) -> int:
        """Armor class from dexterity and worn armor (lower is better).

        Sums ``ac_apply`` over items the character wears (an item tagged
        ``worn`` or carrying a ``worn`` attr). Call this whenever gear
        changes; the wear command is the natural integration point."""
        dex = int(player.db.get("dexterity") or 13)
        ac = 10 - max(0, (dex - 14) // 2)
        for item in player.contents:
            if item.has_tag("worn") or item.db.get("worn"):
                ac -= int(item.db.get("ac_apply") or 0)
        player.db.armor_class = ac
        return ac

    def on_equipment_change(self, player: GameObject) -> None:
        """Diku AC is worn-gear-derived; re-derive on every wear/remove."""
        self.recompute_ac(player)

    def saving_throw(self, target: GameObject, level: int) -> bool:
        """Diku save vs spell: level differential swings the d100 chance
        5%/level around an even 50, clamped to 5..95 so nothing is a
        certainty either way."""
        target_level = int(target.db.get("level") or 1)
        chance = max(5, min(95, 50 + 5 * (target_level - int(level))))
        return random.randint(1, 100) <= chance

    # --- advancement (XP + level): add-on methods, NOT the ABC ---

    def grant_award(self, player: GameObject, amount: int) -> None:
        """The shared deposit seam, overridden for XP. A kill's reward
        banks as experience and may immediately push one or more levels."""
        player.db.xp = int(player.db.get("xp") or 0) + int(amount)
        player.msg(f"You gain {amount} experience.")
        self.advance_level(player)

    def xp_to_next(self, level: int) -> int:
        """Experience needed to reach the next level from ``level``."""
        return 1000 * level

    def advance_level(self, player: GameObject) -> None:
        cls = str(player.db.get("character_class") or "warrior")
        spec = self._classes().get(cls, self._classes()["warrior"])
        while True:
            level = int(player.db.get("level") or 1)
            xp = int(player.db.get("xp") or 0)
            need = self.xp_to_next(level)
            if xp < need:
                break
            player.db.xp = xp - need
            player.db.level = level + 1
            gain = max(1, _hit_die_expected(spec["hit_die"]) + _con_bonus(player))
            player.db.max_hp = int(player.db.get("max_hp") or 0) + gain
            player.db.hp = int(player.db.get("hp") or 0) + gain
            if spec["mana_per_level"]:
                player.db.max_mana = int(player.db.get("max_mana") or 0) \
                    + spec["mana_per_level"]
                player.db.mana = int(player.db.get("mana") or 0) \
                    + spec["mana_per_level"]
            # THAC0 improves one point every ``thac0_rate`` levels.
            player.db.thac0 = 20 - (level // spec["thac0_rate"])
            practices = max(1, (int(player.db.get("intelligence") or 13) - 11) // 2)
            player.db.practices = int(player.db.get("practices") or 0) + practices
            player.msg(f"You advance to level {level + 1}! (+{gain} HP)")


__all__ = ["MercSystem", "MERC_CLASSES", "BUILTIN_SKILL_DEFAULTS"]
