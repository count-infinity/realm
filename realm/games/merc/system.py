"""
Merc/Diku-lineage game system — the rules a converted ROM area wants.

Pairs with :class:`realm.games.merc.ruleset.MercRuleset`. What makes it
Diku rather than the shipped GURPS/D20 packages:

- **Five attributes** — STR/INT/WIS/DEX/CON (Diku's, 3..25).
- **Percentile skills** — a skill is a learned 0..99 %, and a check is
  ``d100 <= skill%``; untrained skills default low, so you cannot pick a
  lock you were never taught.
- **Four classes** — mage / cleric / thief / warrior, each with a hit die,
  a THAC0 progression, and starting skills.
- **Level-based HP** — a fresh character has ROM's and Merc's 20 hit
  points, whatever its class; each level grants its class hit die (the
  expected roll) plus a constitution bonus. This is the one thing the
  point-buy GURPS/D20 packages do not do, and it is why this system
  overrides the award seam (see ``grant_award`` below).

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

from realm.core.defs import all_defs
from realm.core.objects import GameObject
from realm.core.pools import Pool, has_pool, pool_get, pool_max, pool_percent, set_pool
from realm.core.world import find_world
from realm.std.rules.checks import CheckResult, skill_level
from realm.std.rules.definitions import apply_class
from realm.std.rules.system import ChoiceStep, GameSystem, pool_lines

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
        "skills": {"melee": 40, "kick": 40, "bash": 30, "rescue": 30, "disarm": 20,
                   "parry": 30, "shield_block": 25, "dodge": 15, "second_attack": 25},
        "starting_weapon": {"name": "a short sword", "damage_dice": "1d6",
                            "damage_type": "slashing"},
        "titles": [(1, "Swordpupil"), (5, "Soldier"), (10, "Combatant"),
                   (15, "Swordmaster"), (20, "Knight"), (30, "Overlord"),
                   (40, "Warlord"), (50, "Hero")],
    },
    "barbarian": {
        "blurb": "a savage warrior: the biggest hit die, a brutal club, "
                 "no spells",
        "hit_die": 12, "thac0_rate": 1, "mana_per_level": 0,
        "stats": {"strength": 17, "constitution": 16},
        "skills": {"melee": 40, "kick": 45, "dodge": 20, "parry": 15,
                   "second_attack": 20},
        "starting_weapon": {"name": "a heavy wooden club", "damage_dice": "1d8",
                            "damage_type": "bludgeoning"},
        "titles": [(1, "Brute"), (5, "Raider"), (10, "Marauder"),
                   (15, "Berserker"), (20, "Reaver"), (30, "Warchief"),
                   (40, "Destroyer"), (50, "Hero")],
    },
    "thief": {
        "blurb": "a skirmisher: stealth, locks, and a wicked backstab",
        "hit_die": 6, "thac0_rate": 2, "mana_per_level": 0,
        "stats": {"dexterity": 16, "intelligence": 13},
        "skills": {"stealth": 45, "lockpicking": 40, "backstab": 30, "trip": 30,
                   "disarm": 20, "dodge": 30, "melee": 20},
        "starting_weapon": {"name": "a dagger", "damage_dice": "1d4",
                            "damage_type": "piercing"},
        "titles": [(1, "Pilferer"), (5, "Sneak"), (10, "Rogue"), (15, "Thief"),
                   (20, "Cut-Throat"), (30, "Master Thief"), (40, "Assassin"),
                   (50, "Hero")],
    },
    "cleric": {
        "blurb": "a divine caster: healing and protective prayers",
        "hit_die": 8, "thac0_rate": 2, "mana_per_level": 8,
        "stats": {"wisdom": 16, "strength": 13},
        "skills": {"heal": 40, "bless": 30, "melee": 15},
        "starting_weapon": {"name": "a wooden mace", "damage_dice": "1d6",
                            "damage_type": "bludgeoning"},
        "titles": [(1, "Believer"), (5, "Missionary"), (10, "Minister"),
                   (15, "Healer"), (20, "Patriarch"), (30, "Bishop"),
                   (40, "High Priest"), (50, "Hero")],
    },
    "mage": {
        "blurb": "an arcane caster: fragile, but the deadliest spells",
        "hit_die": 4, "thac0_rate": 3, "mana_per_level": 10,
        "stats": {"intelligence": 16, "dexterity": 13},
        "skills": {"magic_missile": 35, "detect_magic": 40, "stealth": 10},
        "starting_weapon": {"name": "a gnarled dagger", "damage_dice": "1d4",
                            "damage_type": "piercing"},
        "titles": [(1, "Apprentice of Magic"), (5, "Medium of Magic"),
                   (10, "Abjurer"), (15, "Creator"), (20, "Sorcerer"),
                   (30, "Archmage"), (40, "Elemental Master"), (50, "Hero")],
    },
}

#: Diku's wear locations and how many items each holds, in ROM's order.
MERC_WEAR_SLOTS: tuple[tuple[str, int], ...] = (
    ("light", 1), ("finger", 2), ("neck", 2), ("body", 1), ("head", 1),
    ("legs", 1), ("feet", 1), ("hands", 1), ("arms", 1), ("shield", 1),
    ("about", 1), ("waist", 1), ("wrist", 2), ("held", 1),
)

# Untrained percentile defaults: (governing attribute, flat penalty). A
# skill you were never taught rolls near zero.
BUILTIN_SKILL_DEFAULTS: dict[str, tuple[str, int]] = {
    "melee": ("strength", -30),
    "stealth": ("dexterity", -40),
    "lockpicking": ("dexterity", -80),   # untrainable without practice
    "heal": ("wisdom", -60),
    "observation": ("intelligence", -20),
    # ROM gives every class recall at 50%: the check a fighter makes to
    # pray their way out of a fight (MUD_PLAN 11.7).
    "recall": ("wisdom", 37),
}

#: Where a character's ``alignment`` stands, ROM's words for it (``score``).
ALIGNMENT_WORDS: tuple[tuple[int, str], ...] = (
    (900, "angelic"), (700, "saintly"), (350, "good"), (100, "kind"),
    (-100, "neutral"), (-350, "mean"), (-700, "evil"), (-900, "demonic"),
)

#: The pools hunger and thirst live in: not numbers on the sheet (``score``
#: says "You are hungry." instead).
NEED_POOLS = ("food", "water")

#: ``consider``: (most levels the target is above you, what is said), ROM's.
CONSIDER_LINES: tuple[tuple[int, str], ...] = (
    (-10, "You can kill {name} naked and weaponless."),
    (-5, "{name} is no match for you."),
    (-2, "{name} looks like an easy kill."),
    (1, "The perfect match!"),
    (4, "{name} says 'Do you feel lucky, punk?'."),
    (9, "{name} laughs at you mercilessly."),
)


def char_level(obj: GameObject) -> int:
    """``obj``'s level; 1 when it has none. Level 0 is a level (ROM's fido
    is level 0, a level below a new character), never read as 1."""
    level = obj.db.get("level")
    return 1 if level is None else int(level)


def alignment(obj: GameObject) -> int:
    """``obj``'s alignment, -1000 (evil) to 1000 (good); 0 when unset."""
    return max(-1000, min(1000, int(obj.db.get("alignment") or 0)))


def alignment_word(value: int) -> str:
    """ROM's word for an alignment: ``good``, ``neutral``, ``satanic``..."""
    return next((word for floor, word in ALIGNMENT_WORDS if value > floor), "satanic")


def is_good(obj: GameObject) -> bool:
    return alignment(obj) >= 350


def is_evil(obj: GameObject) -> bool:
    return alignment(obj) <= -350


#: Hit points at level 1, every class: ROM's and Merc's ``new_char``.
FIRST_LEVEL_HP = 20

#: Practices and training sessions a new character has: ROM's ``nanny``.
FIRST_PRACTICES = 5
FIRST_TRAINS = 3

#: ROM's ``do_outfit`` (``merc.h``): besides the weapon, a new character
#: wears the Mud School's war banner (``OBJ_VNUM_SCHOOL_BANNER``), vest and
#: shield, when a converted ``school.are`` put their prototypes in the world.
ROM_OUTFIT_VNUMS = (3716, 3703, 3704)

#: ROM's ``xp_compute``: below this level a kill pays ``10 / (level + 4)``
#: times as much (double at level 1), so a new character's first levels come
#: quickly.
LOW_LEVEL_BONUS_BELOW = 6


def _hit_die_expected(die: int) -> int:
    return round((1 + die) / 2)


def _con_bonus(player: GameObject) -> int:
    return max(0, (int(player.db.get("constitution") or 13) - 14) // 2)


class MercSystem(GameSystem):
    """Diku/Merc/ROM-lite: percentile skills, four classes, XP leveling."""

    system_id = "merc"
    ruleset_name = "merc"
    currency_name = "gold"
    #: Decision D5: every Merc skill is practiced to a floor and then
    #: improves by use (the SMAUG hybrid).
    default_progression = "use"

    # --- progression ---

    def _class_name(self, obj: GameObject) -> str:
        return str(obj.db.get("character_class") or "")

    def _ability_gate(self, skill: str, cls: str) -> int | None:
        """The level the class may first use the ability named ``skill``
        at, when an ability_def of that name lists the class."""
        from realm.core.defs import def_kinds, def_objects
        if "ability" not in def_kinds():
            return None
        adef = def_objects("ability").get(skill) or def_objects("ability").get(
            skill.replace("_", " "))
        if adef is None or cls not in (adef.db.get("classes") or []):
            return None
        return int(adef.db.get("level") or 1)

    def class_skills(self, obj: GameObject) -> list[str]:
        """The class's starting skills, and every ability_def it may use."""
        from realm.core.defs import def_kinds, def_objects
        cls = self._class_name(obj)
        spec = self._classes().get(cls, {})
        names = list(spec.get("skills", {}))
        if "ability" in def_kinds():
            for adef in def_objects("ability").values():
                key = "_".join(adef.name.lower().split())
                if cls in (adef.db.get("classes") or []) and key not in names:
                    names.append(key)
        return names

    def skill_cap(self, obj: GameObject, skill: str) -> int | None:
        """SMAUG's class maximum: the skill definition's ``class_caps`` for
        this class; else 95 for a class skill once the character reaches
        its level gate and 75 before it, and 75 for a skill outside the
        class."""
        from realm.std.rules.progression import skill_def
        cls = self._class_name(obj)
        sdef = skill_def(skill)
        caps = sdef.db.get("class_caps") if sdef is not None else None
        if isinstance(caps, dict) and cls in caps:
            return int(caps[cls])
        if skill not in self.class_skills(obj):
            return 75
        gate = self._ability_gate(skill, cls) or 1
        return 95 if char_level(obj) >= gate else 75

    def check_was_open(self, result: Any) -> bool:
        """A percentile roll at 0% could not succeed and at 100% could not fail."""
        return 0 < int(result.effective) < 100

    def stat_max(self, obj: GameObject, stat: str) -> int | None:
        """18, or 20 for a class's prime characteristics."""
        spec = self._classes().get(self._class_name(obj), {})
        return 20 if stat in spec.get("stats", {}) else 18

    # --- baseline & skills ---

    def pools(self) -> list[Pool]:
        """Diku's three: hit points, mana and movement; and hunger and
        thirst as ``food`` and ``water`` (Decision D6: CoffeeMud's, run by
        the ``needs`` feature), which do not refill on their own."""
        return [Pool("hp"), Pool("mana"), Pool("move"),
                Pool("food", regen=False), Pool("water", regen=False)]

    def baseline_stats(self) -> dict[str, Any]:
        return {
            "strength": 13, "intelligence": 13, "wisdom": 13,
            "dexterity": 13, "constitution": 13,
            "level": 1, "xp": 0, "practices": 0,
            "hp": 20, "max_hp": 20, "mana": 100, "max_mana": 100,
            "move": 100, "max_move": 100,
            "thac0": 20, "armor_class": 10, "alignment": 0,
        }

    def skill_defaults(self) -> dict[str, tuple[str, int]]:
        defaults = dict(BUILTIN_SKILL_DEFAULTS)
        defaults.update(all_defs("skill"))
        return defaults

    def resolve_check(self, obj: GameObject, skill: str, modifier: int):
        """Percentile: roll d100, succeed on ``<= skill% + modifier``."""
        pct = max(0, min(99, skill_level(obj, skill) + modifier))
        d100 = random.randint(1, 100)
        success = d100 <= pct
        return CheckResult(success=success, margin=pct - d100, roll=d100,
                           effective=pct, skill=skill)

    # --- creation ---

    def _classes(self) -> dict[str, dict[str, Any]]:
        return MERC_CLASSES

    def chargen_steps(self):
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
        # Level 1: ROM's and Merc's 20 hit points for every class; the class
        # hit die tells from level 2 on.
        set_pool(player, 'hp', FIRST_LEVEL_HP, max=FIRST_LEVEL_HP)
        # ROM's nanny: practices and training sessions to start with.
        player.db.practices = FIRST_PRACTICES
        player.db.trains = FIRST_TRAINS
        player.db.thac0 = 20
        player.db.max_mana = 100 + spec["mana_per_level"]
        player.db.mana = player.db.max_mana
        self.recompute_ac(player)
        return f"Your {cls} steps into the world, ready to earn their name."

    async def outfit_new_character(self, player: GameObject,
                                   persistence: Any) -> None:
        """Hand the new character its class starting weapon, wielded, and,
        as ROM's ``do_outfit`` does, the school's banner, vest and shield
        (``ROM_OUTFIT_VNUMS``) worn, when the world has their prototypes."""
        await self._outfit_weapon(player, persistence)
        await self._outfit_school_gear(player, persistence)
        self.recompute_ac(player)

    async def _outfit_school_gear(self, player: GameObject, persistence: Any) -> None:
        from realm.core.ops.objects import clone
        if persistence is None:
            return
        given = []
        for vnum in ROM_OUTFIT_VNUMS:
            proto = persistence.get_cached(f"rom_obj_{vnum}")
            slot = proto.db.get("slot") if proto is not None else None
            if slot is None or any(o.has_tag("worn") and o.db.get("slot") == slot
                                   for o in player.contents):
                continue
            item = clone(None, proto, location=player).value
            item.remove_tag("prototype")
            item.add_tag("worn")
            item.db.value = 0                    # ROM: obj->cost = 0
            item.owner = player
            await persistence.save(item)
            given.append(item.name)
        if given:
            player.msg("You have been equipped by the Mud School: "
                       + ", ".join(given) + ".")

    async def _outfit_weapon(self, player: GameObject, persistence: Any) -> None:

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
        if weapon.get("damage_type"):
            item.db.set("damage_type", str(weapon["damage_type"]))
        item.owner = player
        if persistence is not None:
            await persistence.save(item)
        player.msg(f"You grip {weapon['name']}, ready for trouble.")

    def recompute_ac(self, player: GameObject) -> int:
        """Armor class from dexterity and worn armor (lower is better).

        Sums ``ac_apply`` over items the character wears (tagged ``worn``).
        Call this whenever gear
        changes; the wear command is the natural integration point."""
        dex = int(player.db.get("dexterity") or 13)
        ac = 10 - max(0, (dex - 14) // 2)
        for item in player.contents:
            if item.has_tag("worn"):
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
        target_level = char_level(target)
        chance = max(5, min(95, 50 + 5 * (target_level - int(level))))
        return random.randint(1, 100) <= chance

    # --- advancement (XP + level): add-on methods, NOT the ABC ---

    def death_award(self, victim: GameObject,
                    killer: GameObject | None = None) -> int:
        """A kill's worth in EXPERIENCE, Diku-style.

        The ABC default (``points // 10``) is character-point scaling — on
        an XP system it starves the level curve (a level-1 fido would pay
        10 XP against a 1000-XP level: a hundred dogs per level). Here the
        victim's ``points`` (the importer mints ``level * 100``) is the
        base, bent by the level difference the classic Diku way: prey
        above your level pays a premium, grey-con prey pays a pittance.
        (What each member is paid, with ROM's low-level bonus, is
        ``share_award``'s.)
        """
        base = int(victim.db.get("points") or 100)
        if killer is not None:
            diff = char_level(victim) - char_level(killer)
            base = round(base * max(0.05, min(2.0, 1.0 + 0.15 * diff)))
        return max(1, base)

    def grant_award(self, player: GameObject, amount: int) -> None:
        """The shared deposit seam, overridden for XP. A kill's reward
        banks as experience and may immediately push one or more levels."""
        player.db.xp = int(player.db.get("xp") or 0) + int(amount)
        player.msg(f"You gain {amount} experience.")
        self.advance_level(player)

    def spendable_award(self, player: GameObject) -> int | None:
        """Experience toward the next level: giving it away never costs a
        level (it is kept as progress, as ``on_death`` treats it)."""
        return int(player.db.get("xp") or 0)

    def spend_award(self, player: GameObject, amount: int) -> None:
        player.db.xp = max(0, int(player.db.get("xp") or 0) - int(amount))

    def share_award(self, award: int,
                    members: list[GameObject]) -> list[tuple[GameObject, int]]:
        """ROM's ``group_gain``: each member's share is the award times their
        level over the levels of everyone sharing it; and ROM's
        ``xp_compute`` pays a member below level 6 ``10 / (level + 4)``
        times its share (double at level 1), so first levels come quickly."""
        levels = [max(1, char_level(m)) for m in members]   # a divisor
        total = sum(levels)
        shares = []
        for member, level in zip(members, levels, strict=True):
            share = max(1, int(award) * level // total)
            if char_level(member) < LOW_LEVEL_BONUS_BELOW:
                share = 10 * share // (max(0, char_level(member)) + 4)
            shares.append((member, share))
        return shares

    def on_kill(self, member: GameObject, victim: GameObject) -> None:
        """Merc's alignment shift: killing what is far more evil than you
        makes you better, far more good makes you worse, anything else
        draws you a quarter of the way to neutral. Then whatever the new
        alignment cannot wear zaps off."""
        if not member.is_player:
            return
        mine = alignment(member)
        gap = mine - alignment(victim)
        if gap > 500:
            mine = min(mine + int((gap - 500) / 4), 1000)
        elif gap < -500:
            mine = max(mine + int((gap + 500) / 4), -1000)
        else:
            mine -= int(mine / 4)
        member.db.alignment = mine
        for item in list(member.contents):
            if (item.has_tag("worn") or item.has_tag("wielded")) \
                    and self.repels(member, item):
                self.zap(member, item)

    def repels(self, player: GameObject, item: GameObject) -> bool:
        """ROM's ``ITEM_ANTI_GOOD``/``_EVIL``/``_NEUTRAL``, as the tags
        ``anti_good``, ``anti_evil`` and ``anti_neutral``."""
        if is_good(player):
            return item.has_tag("anti_good")
        if is_evil(player):
            return item.has_tag("anti_evil")
        return item.has_tag("anti_neutral")

    def zap(self, player: GameObject, item: GameObject) -> None:
        super().zap(player, item)
        self.recompute_ac(player)

    def wear_refusal(self, player: GameObject, item: GameObject) -> str | None:
        """An item's ``level`` is the least a character must be to use it."""
        need = int(item.db.get("level") or 0)
        if player.is_player and need > char_level(player):
            return f"You must be level {need} to use {item.name}."
        return None

    def companion_limit(self, character: GameObject) -> int:
        """Diku has no charisma: one follower, and one more each ten levels."""
        return 1 + char_level(character) // 10

    def consider(self, viewer: GameObject, target: GameObject) -> str | None:
        """ROM's ``consider``: how the target's level compares to yours."""
        diff = char_level(target) - char_level(viewer)
        line = next((text for most, text in CONSIDER_LINES if diff <= most),
                    "Death will thank you for your gift.")
        line = line.format(name=target.get_display_name(viewer))
        return line[:1].upper() + line[1:]

    def who_title(self, player: GameObject) -> str | None:
        """``the Swordpupil (1 warrior)``: the class's title for the
        character's level band (a class's ``titles``), its level and class."""
        cls = self._class_name(player)
        spec = self._classes().get(cls)
        if spec is None:
            return None
        level = char_level(player)
        title = None
        for floor, name in spec.get("titles") or []:
            if level >= int(floor):
                title = name
        shown = f"({level} {cls})"
        return f"the {title} {shown}" if title else shown

    def after_recall(self, player: GameObject, *, from_combat: bool) -> None:
        """Recall spends half the ``move`` pool; out of a fight it also
        costs 25 experience (ROM)."""
        if has_pool(player, "move"):
            set_pool(player, "move", int(pool_get(player, "move") or 0) // 2)
        if from_combat:
            lost = min(25, int(player.db.get("xp") or 0))
            player.db.xp = int(player.db.get("xp") or 0) - lost
            player.msg(f"You recall from combat! You lose {lost} experience.")

    def level_cap(self) -> int:
        """``LEVEL_CAP`` (the ``merc`` feature's setting), 50 without it."""
        world = find_world()
        return int(world.setting("LEVEL_CAP", 50)) if world is not None else 50

    def regen(self, obj: GameObject, pool_name: str) -> int:
        """Diku's gain per tick, standing (ROM ``hit_gain``, ``mana_gain``,
        ``move_gain`` before the position divisor): hit points by
        constitution and level, mana by the better of intelligence and
        wisdom, movement by dexterity, all with level."""
        level = char_level(obj)

        def stat(name: str) -> int:
            return int(obj.db.get(name) or 13)

        if pool_name == "hp":
            return max(1, (stat("constitution") - 3 + level // 2) // 4)
        if pool_name == "mana":
            return max(1, (max(stat("intelligence"), stat("wisdom")) + level) // 4)
        if pool_name == "move":
            return max(1, (stat("dexterity") + level) // 4)
        return super().regen(obj, pool_name)

    def on_death(self, player: GameObject, killer: GameObject | None = None) -> None:
        """Lose a quarter of a level's experience. Experience is kept as
        progress toward the next level, so the loss stops at zero and never
        costs a level."""
        level = char_level(player)
        xp = int(player.db.get("xp") or 0)
        lost = min(xp, self.xp_to_next(level) // 4)
        player.db.xp = xp - lost
        if lost:
            player.msg(f"You lose {lost} experience.")

    def xp_to_next(self, level: int) -> int:
        """Experience needed to reach the next level from ``level``."""
        return 1000 * level

    def score_lines(self, player: GameObject) -> list[str]:
        """The Diku score sheet: level and XP, combat numbers, equipment."""
        level = char_level(player)
        xp = int(player.db.get("xp") or 0)
        cls = str(player.db.get("character_class") or "warrior")
        lines = [
            f"You are {player.name}, a level {level} {cls}.",
            f"Experience: {xp} / {self.xp_to_next(level)} to level {level + 1}",
            pool_lines(player, exclude=NEED_POOLS),
            f"THAC0: {player.db.get('thac0')}   "
            f"AC: {player.db.get('armor_class')}",
            f"Alignment: {alignment(player)} ({alignment_word(alignment(player))})",
        ]
        wielded = [o for o in player.contents if o.has_tag('wielded')]
        worn = [o for o in player.contents if o.has_tag('worn')]
        if wielded:
            lines.append(f"Wielding: {wielded[0].name}")
        if worn:
            lines.append("Wearing:  " + ", ".join(o.name for o in worn))
        practices = int(player.db.get("practices") or 0)
        trains = int(player.db.get("trains") or 0)
        if practices or trains:
            lines.append(f"Practices: {practices}   Training sessions: {trains}")
        # Diku's conditions, said rather than counted: at a quarter or less.
        for pool, line in (("food", "You are hungry."), ("water", "You are thirsty.")):
            percent = pool_percent(player, pool)
            if percent is not None and percent <= 25:
                lines.append(line)
        return lines

    def wear_slots(self) -> list[tuple[str, int]]:
        """Diku's wear locations (ROM ``WEAR_*``), in its ``equipment`` order."""
        return list(MERC_WEAR_SLOTS)

    def format_skill(self, skill: str, level: int) -> str:
        return f"{level}%"

    def advance_level(self, player: GameObject) -> None:
        cls = str(player.db.get("character_class") or "warrior")
        spec = self._classes().get(cls, self._classes()["warrior"])
        cap = self.level_cap()
        while True:
            level = char_level(player)
            xp = int(player.db.get("xp") or 0)
            need = self.xp_to_next(level)
            if xp < need or level >= cap:
                break
            player.db.xp = xp - need
            player.db.level = level + 1
            gain = max(1, _hit_die_expected(spec["hit_die"]) + _con_bonus(player))
            set_pool(player, 'hp', int(pool_get(player, 'hp') or 0) + gain,
                     max=int(pool_max(player, 'hp') or 0) + gain)
            mana = int(spec["mana_per_level"])
            if mana:
                player.db.max_mana = int(player.db.get("max_mana") or 0) + mana
                player.db.mana = int(player.db.get("mana") or 0) + mana
            # THAC0 improves one point every ``thac0_rate`` levels.
            thac0 = int(player.db.get("thac0") or 20)
            player.db.thac0 = 20 - (level // spec["thac0_rate"])
            practices = max(1, (int(player.db.get("intelligence") or 13) - 11) // 2)
            player.db.practices = int(player.db.get("practices") or 0) + practices
            player.db.trains = int(player.db.get("trains") or 0) + 1
            # ROM's advance_level: the level, then what it brought.
            gains = [f"{gain} hit point{'s' if gain != 1 else ''}"]
            if mana:
                gains.append(f"{mana} mana")
            gains.append(f"{practices} practice{'s' if practices != 1 else ''}")
            gains.append("1 training session")
            line = f"You gain {', '.join(gains[:-1])} and {gains[-1]}."
            if int(player.db.thac0) < thac0:
                line += f" Your THAC0 is now {player.db.thac0}."
            player.msg(f"You raise a level!!  You are now level {level + 1}.")
            player.msg(line)


__all__ = ["MercSystem", "MERC_CLASSES", "BUILTIN_SKILL_DEFAULTS", "ALIGNMENT_WORDS",
           "CONSIDER_LINES", "alignment", "alignment_word", "is_good", "is_evil"]
