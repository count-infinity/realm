"""
GURPS 4e-lite game system: templates-first chargen, 3d6 roll-under.

Chargen is two ChoiceSteps (template, bonus skill) — fast enough to be
playable, structured so point-buy attribute steps can slot in later
without touching the flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.systems.base import ChoiceStep, GameSystem

if TYPE_CHECKING:
    from realm.core.objects import GameObject


# name -> (blurb, stats, skills)
TEMPLATES: dict[str, tuple[str, dict[str, int], dict[str, int]]] = {
    "soldier": (
        "tough and dangerous (ST 12, HT 12; melee, guns)",
        {'strength': 12, 'dexterity': 11, 'intelligence': 10, 'health': 12},
        {'melee': 12, 'guns': 12, 'first_aid': 10},
    ),
    "infiltrator": (
        "quick and quiet (DX 13; stealth, lockpicking, climbing)",
        {'strength': 10, 'dexterity': 13, 'intelligence': 11, 'health': 10},
        {'stealth': 13, 'lockpicking': 12, 'climbing': 12},
    ),
    "face": (
        "silver-tongued (IQ 13; fast_talk, persuasion, observation)",
        {'strength': 10, 'dexterity': 10, 'intelligence': 13, 'health': 10},
        {'fast_talk': 13, 'persuasion': 13, 'observation': 12},
    ),
    "technician": (
        "gadget-minded (IQ 12; electronics, computers, first_aid)",
        {'strength': 10, 'dexterity': 11, 'intelligence': 12, 'health': 10},
        {'electronics': 13, 'computers': 13, 'first_aid': 11},
    ),
}

BONUS_SKILLS = {
    "stealth": "move unseen",
    "melee": "hit things",
    "observation": "notice things",
    "first_aid": "patch people up",
    "fast_talk": "bend the truth",
}


def _apply_template(player: GameObject, name: str) -> None:
    _blurb, stats, skills = TEMPLATES[name]
    for stat, value in stats.items():
        player.db.set(stat, value)
    for skill, level in skills.items():
        player.db.set(f"skill_{skill}", level)
    player.db.template = name


def _apply_bonus_skill(player: GameObject, name: str) -> None:
    attr = f"skill_{name}"
    current = player.db.get(attr)
    if current is None:
        # New skill starts at DX or IQ (whichever the default keys off).
        base_attr, _mod = GurpsSystem().skill_defaults().get(
            name, ('dexterity', -5))
        current = int(player.db.get(base_attr) or 10)
        player.db.set(attr, current)
    else:
        player.db.set(attr, int(current) + 1)


class GurpsSystem(GameSystem):
    """GURPS 4e-lite: 3d6 roll-under, 4 CP per skill level."""

    system_id = "gurps"
    ruleset_name = "gurps"

    def skill_defaults(self) -> dict[str, tuple[str, int]]:
        return {
            "stealth": ("dexterity", -5),
            "climbing": ("dexterity", -5),
            "jumping": ("dexterity", -4),
            "lockpicking": ("dexterity", -5),
            "melee": ("dexterity", -4),
            "guns": ("dexterity", -4),
            "observation": ("intelligence", -5),
            "search": ("intelligence", -5),
            "electronics": ("intelligence", -5),
            "computers": ("intelligence", -4),
            "first_aid": ("intelligence", -4),
            "fast_talk": ("intelligence", -5),
            "persuasion": ("intelligence", -5),
            "detect_lies": ("intelligence", -6),
            "will": ("intelligence", 0),
        }

    def improve_cost(self, skill: str, current_level: int) -> int:
        return 4

    def chargen_steps(self):
        return [
            ChoiceStep(
                "template",
                "Pick your background:",
                {name: blurb for name, (blurb, _s, _k) in TEMPLATES.items()},
                _apply_template,
            ),
            ChoiceStep(
                "bonus skill",
                "Pick a bonus skill (new at attribute level, or +1 if trained):",
                dict(BONUS_SKILLS),
                _apply_bonus_skill,
            ),
        ]

    def finish_chargen(self, player: GameObject) -> str:
        # Derived stats, GURPS-style: HP from ST, dodge from DX-based speed.
        strength = int(player.db.get('strength') or 10)
        dexterity = int(player.db.get('dexterity') or 10)
        health = int(player.db.get('health') or 10)
        player.db.hp = strength
        player.db.max_hp = strength
        player.db.dodge = 7 + (dexterity + health) // 8
        template = player.db.get('template') or 'adventurer'
        return f"You are ready — a {template} walks into the world."


__all__ = ["GurpsSystem", "TEMPLATES", "BONUS_SKILLS"]
