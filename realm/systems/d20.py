"""
D20 game system: class-pick chargen, d20 ruleset.

Exists to prove the GameSystem seam swaps whole rules packages —
config `GAME_SYSTEM = "d20"` and nothing else changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.systems.base import ChoiceStep, GameSystem, GameSystemRegistry

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


def _apply_class(player: GameObject, name: str) -> None:
    _blurb, stats, skills = CLASSES[name]
    for stat, value in stats.items():
        player.db.set(stat, value)
    for skill, level in skills.items():
        player.db.set(f"skill_{skill}", level)
    player.db.character_class = name


@GameSystemRegistry.register
class D20System(GameSystem):
    """d20-flavored rules package."""

    system_id = "d20"
    ruleset_name = "d20"
    currency_name = "gold"

    def skill_defaults(self) -> dict[str, tuple[str, int]]:
        return {
            "stealth": ("dexterity", -4),
            "lockpicking": ("dexterity", -4),
            "athletics": ("strength", -2),
            "observation": ("intelligence", -2),
            "lore": ("intelligence", -4),
            "melee": ("strength", -2),
        }

    def improve_cost(self, skill: str, current_level: int) -> int:
        # Escalating: higher levels cost more (D&D-ish training).
        return max(2, (current_level - 8) // 2)

    def chargen_steps(self):
        return [ChoiceStep(
            "class",
            "Choose your class:",
            {name: blurb for name, (blurb, _s, _k) in CLASSES.items()},
            _apply_class,
        )]

    def finish_chargen(self, player: GameObject) -> str:
        health = int(player.db.get('health') or 10)
        player.db.hp = health
        player.db.max_hp = health
        cls = player.db.get('character_class') or 'adventurer'
        return f"Your {cls} is ready for adventure."


__all__ = ["D20System", "CLASSES"]
