"""
D20 game system: class-pick chargen, d20 ruleset.

Exists to prove the GameSystem seam swaps whole rules packages —
config `GAME_SYSTEM = "d20"` and nothing else changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.defs import all_defs
from realm.core.pools import set_pool
from realm.std.rules.checks import CheckResult, skill_level
from realm.std.rules.definitions import apply_class
from realm.std.rules.system import ChoiceStep, GameSystem, PointBuyMixin

if TYPE_CHECKING:
    from realm.core.objects import GameObject

CLASSES: dict[str, tuple[str, dict[str, int], dict[str, int]]] = {
    "fighter": ("strong front-liner",
                {'strength': 16, 'dexterity': 12, 'intelligence': 10, 'health': 14},
                {'melee': 14, 'athletics': 12}),
    "rogue": ("skulker and picker of locks",
              {'strength': 10, 'dexterity': 16, 'intelligence': 12, 'health': 12},
              {'stealth': 14, 'lockpicking': 14}),
    "sage": ("knows things",
             {'strength': 8, 'dexterity': 10, 'intelligence': 16, 'health': 10},
             {'observation': 14, 'lore': 14}),
}


# Built-in untrained skill defaults; skill_def objects merge over these.
BUILTIN_SKILL_DEFAULTS: dict[str, tuple[str, int]] = {
    "stealth": ("dexterity", -4),
    "lockpicking": ("dexterity", -4),
    "athletics": ("strength", -2),
    "observation": ("intelligence", -2),
    "lore": ("intelligence", -4),
    "melee": ("strength", -2),
}


class D20System(PointBuyMixin, GameSystem):
    """d20-flavored rules package, buying skills with character points
    (PointBuyMixin) at an escalating price. Skills and classes are data (see
    realm.std.rules.definitions): built-ins here, overridden by
    ``skill_def`` / ``class_def`` objects in the world."""

    system_id = "d20"
    ruleset_name = "d20"
    currency_name = "gold"

    def skill_defaults(self) -> dict[str, tuple[str, int]]:
        defaults = dict(BUILTIN_SKILL_DEFAULTS)
        defaults.update(all_defs("skill"))
        return defaults

    def resolve_check(self, obj, skill: str, modifier: int):
        """d20 + skill bonus vs DC 15 (roll-high). Under d20 a skill
        \"level\" is a bonus, not a target: a rogue with skill_stealth 6
        rolls d20+6. Natural 20 always succeeds, natural 1 always fails."""
        import random

        bonus = skill_level(obj, skill) + modifier
        d20 = random.randint(1, 20)
        total = d20 + bonus
        dc = 15
        success = d20 == 20 or (d20 != 1 and total >= dc)
        return CheckResult(success=success, margin=total - dc, roll=d20,
                           effective=total, skill=skill)

    def improve_cost(self, skill: str, current_level: int) -> int:
        # Escalating: higher levels cost more (D&D-ish training).
        return max(2, (current_level - 8) // 2)

    def _class_options(self) -> dict[str, tuple[str, dict, dict]]:
        # Built-ins, extended/overridden by class_def objects (data wins by
        # name) — same merge rule as skills.
        classes = dict(CLASSES)
        classes.update(all_defs("class"))
        return classes

    def chargen_steps(self):
        classes = self._class_options()

        def apply(player: GameObject, name: str) -> None:
            apply_class(player, classes[name], name, marker="character_class")

        return [ChoiceStep(
            "class",
            "Choose your class:",
            {name: blurb for name, (blurb, _s, _k) in classes.items()},
            apply,
        )]

    def finish_chargen(self, player: GameObject) -> str:
        health = int(player.db.get('health') or 10)
        dexterity = int(player.db.get('dexterity') or 10)
        set_pool(player, 'hp', health, max=health)
        # AC 10 + DEX modifier ((score-10)//2), D&D-style.
        player.db.armor_class = 10 + (dexterity - 10) // 2
        cls = player.db.get('character_class') or 'adventurer'
        return f"Your {cls} is ready for adventure."


__all__ = ["D20System", "CLASSES"]
